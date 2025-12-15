"""
Webhook handler para eventos do Stripe.
"""

import json
import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from ..models import Organization, Subscription, CreditTransaction


@csrf_exempt
@api_view(["POST"])
def stripe_webhook(request):
    """
    Webhook do Stripe para eventos de pagamento e assinatura.
    
    Eventos tratados:
    - payment_intent.succeeded - Pagamento bem-sucedido
    - payment_intent.payment_failed - Pagamento falhou
    - customer.subscription.created - Assinatura criada
    - customer.subscription.updated - Assinatura atualizada
    - customer.subscription.deleted - Assinatura cancelada
    - invoice.payment_succeeded - Fatura paga
    - invoice.payment_failed - Fatura não paga
    """
    try:
        import stripe
    except ImportError:
        return Response(
            {"error": "Stripe not installed"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
    
    if not stripe.api_key:
        return Response(
            {"error": "Stripe not configured"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Obtém webhook secret
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not webhook_secret:
        return Response(
            {"error": "Webhook secret not configured"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Valida assinatura do webhook
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    if not sig_header:
        return Response(
            {"error": "Missing signature header"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        event = stripe.Webhook.construct_event(
            request.body,
            sig_header,
            webhook_secret,
        )
    except ValueError as e:
        return Response(
            {"error": f"Invalid payload: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except stripe.error.SignatureVerificationError as e:
        return Response(
            {"error": f"Invalid signature: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Processa eventos
    event_type = event["type"]

    try:
        if event_type == "payment_intent.succeeded":
            _handle_payment_succeeded(event["data"]["object"])

        elif event_type == "payment_intent.payment_failed":
            _handle_payment_failed(event["data"]["object"])

        elif event_type == "customer.subscription.created":
            _handle_subscription_created(event["data"]["object"])

        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(event["data"]["object"])

        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(event["data"]["object"])

        elif event_type == "invoice.payment_succeeded":
            _handle_invoice_paid(event["data"]["object"])

        elif event_type == "invoice.payment_failed":
            _handle_invoice_failed(event["data"]["object"])

        return Response(
            {"status": "success"},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        print(f"Erro ao processar webhook Stripe: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _handle_payment_succeeded(payment_intent):
    """Trata pagamento bem-sucedido."""
    customer_id = payment_intent.get("customer")
    amount = payment_intent.get("amount") / 100  # Converte centavos para dólares

    try:
        org = Organization.objects.get(stripe_customer_id=customer_id)
        
        # Adiciona créditos comprados
        credits_purchased = int(amount / 0.1)  # Aproximação: $0.10 por crédito
        org.credits_available += credits_purchased
        org.credits_purchased += credits_purchased
        org.save()

        # Registra transação
        CreditTransaction.objects.create(
            organization=org,
            amount=-credits_purchased,  # Negativo = compra
            type="purchase",
            reason=f"Compra de créditos - ${amount:.2f}",
            balance_after=org.credits_available,
        )

    except Organization.DoesNotExist:
        print(f"Organização não encontrada para customer {customer_id}")


def _handle_payment_failed(payment_intent):
    """Trata falha de pagamento."""
    customer_id = payment_intent.get("customer")
    
    try:
        org = Organization.objects.get(stripe_customer_id=customer_id)
        # Notificar usuário sobre falha de pagamento
        print(f"Falha de pagamento para organização {org.id}")
        # TODO: Enviar email de notificação
    except Organization.DoesNotExist:
        pass


def _handle_subscription_created(subscription):
    """Trata criação de assinatura."""
    customer_id = subscription.get("customer")
    stripe_subscription_id = subscription.get("id")
    plan_name = subscription["items"]["data"][0]["plan"]["nickname"]
    
    try:
        org = Organization.objects.get(stripe_customer_id=customer_id)
        
        # Cria subscription
        Subscription.objects.create(
            organization=org,
            stripe_subscription_id=stripe_subscription_id,
            plan=_map_plan_name(plan_name),
            status="active",
            current_period_start=subscription.get("current_period_start"),
            current_period_end=subscription.get("current_period_end"),
        )
        
        # Atualiza organização
        org.plan = _map_plan_name(plan_name)
        org.save()

    except Organization.DoesNotExist:
        print(f"Organização não encontrada para customer {customer_id}")


def _handle_subscription_updated(subscription):
    """Trata atualização de assinatura."""
    stripe_subscription_id = subscription.get("id")
    plan_name = subscription["items"]["data"][0]["plan"]["nickname"]
    
    try:
        sub = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        sub.plan = _map_plan_name(plan_name)
        sub.status = subscription.get("status")
        sub.current_period_start = subscription.get("current_period_start")
        sub.current_period_end = subscription.get("current_period_end")
        sub.save()
        
        # Atualiza organização
        sub.organization.plan = _map_plan_name(plan_name)
        sub.organization.save()

    except Subscription.DoesNotExist:
        print(f"Assinatura não encontrada: {stripe_subscription_id}")


def _handle_subscription_deleted(subscription):
    """Trata cancelamento de assinatura."""
    stripe_subscription_id = subscription.get("id")
    
    try:
        sub = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        sub.status = "canceled"
        sub.canceled_at = subscription.get("canceled_at")
        sub.save()

    except Subscription.DoesNotExist:
        pass


def _handle_invoice_paid(invoice):
    """Trata fatura paga."""
    customer_id = invoice.get("customer")
    amount = invoice.get("amount_paid") / 100
    
    try:
        org = Organization.objects.get(stripe_customer_id=customer_id)
        print(f"Fatura paga para organização {org.id}: ${amount:.2f}")
        # TODO: Registrar evento de billing
    except Organization.DoesNotExist:
        pass


def _handle_invoice_failed(invoice):
    """Trata fatura não paga."""
    customer_id = invoice.get("customer")
    
    try:
        org = Organization.objects.get(stripe_customer_id=customer_id)
        print(f"Fatura não paga para organização {org.id}")
        # TODO: Enviar email de aviso
    except Organization.DoesNotExist:
        pass


def _map_plan_name(stripe_plan_name: str) -> str:
    """Mapeia nome do plano do Stripe para nome interno."""
    mapping = {
        "Starter": "starter",
        "Pro": "pro",
        "Business": "business",
    }
    return mapping.get(stripe_plan_name, "starter")
