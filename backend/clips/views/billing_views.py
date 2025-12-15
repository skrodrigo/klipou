"""
Views para gerenciamento de billing e planos.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Organization, Subscription, CreditTransaction
from ..services.stripe_service import StripeService


PLANS = {
    "starter": {
        "name": "Starter",
        "price_usd": 29,
        "price_brl": 145,
        "credits_monthly": 300,
        "max_jobs_concurrent": 3,
        "max_clips_per_job": 50,
        "max_team_members": 1,
        "max_storage_gb": 100,
    },
    "pro": {
        "name": "Pro",
        "price_usd": 79,
        "price_brl": 395,
        "credits_monthly": 1000,
        "max_jobs_concurrent": 10,
        "max_clips_per_job": 200,
        "max_team_members": 5,
        "max_storage_gb": 500,
    },
    "business": {
        "name": "Business",
        "price_usd": 199,
        "price_brl": 995,
        "credits_monthly": 5000,
        "max_jobs_concurrent": None,  # Ilimitado
        "max_clips_per_job": 500,
        "max_team_members": 50,
        "max_storage_gb": None,  # Ilimitado
    },
}

CREDIT_PACKAGES = {
    "small": {"credits": 100, "price_usd": 9, "price_brl": 45},
    "medium": {"credits": 500, "price_usd": 39, "price_brl": 195},
    "large": {"credits": 1000, "price_usd": 69, "price_brl": 345},
    "mega": {"credits": 5000, "price_usd": 299, "price_brl": 1495},
}


@api_view(["GET"])
def list_plans(request):
    """
    Lista todos os planos disponíveis.
    """
    try:
        return Response(
            {
                "plans": PLANS,
                "currency": "USD",
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def upgrade_plan(request, organization_id):
    """
    Faz upgrade de plano para uma organização.
    
    Body:
    {
        "new_plan": "pro|business",
        "organization_id": "uuid"
    }
    """
    try:
        new_plan = request.data.get("new_plan")
        
        if not new_plan or new_plan not in PLANS:
            return Response(
                {"error": f"Plano inválido. Válidos: {', '.join(PLANS.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        org = Organization.objects.get(organization_id=organization_id)
        
        if org.plan == new_plan:
            return Response(
                {"error": "Organização já está neste plano"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        old_plan = org.plan
        org.plan = new_plan
        org.credits_monthly = PLANS[new_plan]["credits_monthly"]
        org.save()
        
        # TODO: Implementar cobrança pró-rata via Stripe
        
        return Response(
            {
                "organization_id": str(organization_id),
                "old_plan": old_plan,
                "new_plan": new_plan,
                "status": "upgraded",
            },
            status=status.HTTP_200_OK,
        )
    
    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def downgrade_plan(request, organization_id):
    """
    Faz downgrade de plano para uma organização (aplicado no próximo ciclo).
    
    Body:
    {
        "new_plan": "starter|pro",
        "organization_id": "uuid"
    }
    """
    try:
        new_plan = request.data.get("new_plan")
        
        if not new_plan or new_plan not in PLANS:
            return Response(
                {"error": f"Plano inválido. Válidos: {', '.join(PLANS.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        org = Organization.objects.get(organization_id=organization_id)
        
        if org.plan == new_plan:
            return Response(
                {"error": "Organização já está neste plano"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # TODO: Implementar downgrade agendado para próximo ciclo
        
        return Response(
            {
                "organization_id": str(organization_id),
                "current_plan": org.plan,
                "downgrade_plan": new_plan,
                "status": "scheduled_for_next_cycle",
            },
            status=status.HTTP_200_OK,
        )
    
    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def cancel_subscription(request, organization_id):
    """
    Cancela a assinatura de uma organização.
    
    Body:
    {
        "organization_id": "uuid"
    }
    """
    try:
        org = Organization.objects.get(organization_id=organization_id)
        
        # TODO: Implementar cancelamento via Stripe
        
        return Response(
            {
                "organization_id": str(organization_id),
                "status": "cancellation_scheduled",
                "message": "Assinatura será cancelada no final do ciclo",
            },
            status=status.HTTP_200_OK,
        )
    
    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_billing_history(request, organization_id):
    """
    Obtém histórico de billing de uma organização.
    
    Query params:
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    """
    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        
        transactions = CreditTransaction.objects.filter(
            organization_id=organization_id
        ).order_by("-created_at")[offset : offset + limit]
        
        return Response(
            {
                "organization_id": str(organization_id),
                "transactions": [
                    {
                        "transaction_id": str(t.transaction_id),
                        "amount": t.amount,
                        "type": t.type,
                        "reason": t.reason,
                        "balance_after": t.balance_after,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in transactions
                ],
                "total": CreditTransaction.objects.filter(
                    organization_id=organization_id
                ).count(),
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def purchase_credits(request):
    """
    Compra créditos avulsos.
    
    Body:
    {
        "organization_id": "uuid",
        "package": "small|medium|large|mega"
    }
    """
    try:
        organization_id = request.data.get("organization_id")
        package = request.data.get("package")
        
        if not organization_id or not package:
            return Response(
                {"error": "organization_id e package são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if package not in CREDIT_PACKAGES:
            return Response(
                {"error": f"Pacote inválido. Válidos: {', '.join(CREDIT_PACKAGES.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        org = Organization.objects.get(organization_id=organization_id)
        package_data = CREDIT_PACKAGES[package]
        
        # TODO: Implementar pagamento via Stripe
        # Por enquanto, apenas registra a intenção
        
        return Response(
            {
                "organization_id": str(organization_id),
                "package": package,
                "credits": package_data["credits"],
                "price_usd": package_data["price_usd"],
                "status": "payment_required",
                "payment_url": "https://stripe.com/pay/...",  # TODO: Gerar URL de pagamento
            },
            status=status.HTTP_201_CREATED,
        )
    
    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
