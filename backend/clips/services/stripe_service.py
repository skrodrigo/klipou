"""
Serviço de integração com Stripe para billing.
"""

from django.conf import settings


class StripeService:
    """Serviço para operações com Stripe."""

    def __init__(self):
        try:
            import stripe
            stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
            self.stripe = stripe
        except ImportError:
            raise Exception("Stripe not installed")

    def create_customer(self, organization_name: str, email: str) -> str:
        """Cria cliente no Stripe."""
        try:
            customer = self.stripe.Customer.create(
                name=organization_name,
                email=email,
            )
            return customer.id
        except Exception as e:
            raise Exception(f"Erro ao criar cliente Stripe: {e}")

    def create_subscription(self, customer_id: str, plan_id: str) -> dict:
        """Cria assinatura no Stripe."""
        try:
            subscription = self.stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
            )
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
            }
        except Exception as e:
            raise Exception(f"Erro ao criar assinatura: {e}")

    def update_subscription(self, subscription_id: str, plan_id: str) -> dict:
        """Atualiza assinatura (upgrade/downgrade)."""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            
            # Atualiza item da assinatura
            self.stripe.SubscriptionItem.modify(
                subscription.items.data[0].id,
                price=plan_id,
            )
            
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
            }
        except Exception as e:
            raise Exception(f"Erro ao atualizar assinatura: {e}")

    def cancel_subscription(self, subscription_id: str) -> dict:
        """Cancela assinatura."""
        try:
            subscription = self.stripe.Subscription.delete(subscription_id)
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "canceled_at": subscription.canceled_at,
            }
        except Exception as e:
            raise Exception(f"Erro ao cancelar assinatura: {e}")

    def get_subscription(self, subscription_id: str) -> dict:
        """Obtém detalhes de assinatura."""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "plan": subscription.items.data[0].plan.nickname,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
            }
        except Exception as e:
            raise Exception(f"Erro ao obter assinatura: {e}")

    def create_payment_intent(self, customer_id: str, amount: int, currency: str = "usd") -> dict:
        """Cria intent de pagamento."""
        try:
            intent = self.stripe.PaymentIntent.create(
                customer=customer_id,
                amount=amount,
                currency=currency,
                automatic_payment_methods={"enabled": True},
            )
            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
            }
        except Exception as e:
            raise Exception(f"Erro ao criar payment intent: {e}")

    def get_payment_intent(self, payment_intent_id: str) -> dict:
        """Obtém detalhes de payment intent."""
        try:
            intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "payment_intent_id": intent.id,
                "status": intent.status,
                "amount": intent.amount,
                "currency": intent.currency,
            }
        except Exception as e:
            raise Exception(f"Erro ao obter payment intent: {e}")

    def list_invoices(self, customer_id: str, limit: int = 10) -> list:
        """Lista faturas de um cliente."""
        try:
            invoices = self.stripe.Invoice.list(
                customer=customer_id,
                limit=limit,
            )
            return [
                {
                    "invoice_id": inv.id,
                    "amount": inv.amount_paid,
                    "status": inv.status,
                    "created": inv.created,
                    "paid": inv.paid,
                }
                for inv in invoices.data
            ]
        except Exception as e:
            raise Exception(f"Erro ao listar faturas: {e}")
