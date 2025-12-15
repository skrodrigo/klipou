"""
Serviço para gerenciar billing, planos e assinaturas.
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from ..models import Organization, Subscription, CreditTransaction, BillingEvent


class BillingService:
    """Serviço para gerenciar billing."""

    PLANS = {
        "starter": {
            "name": "Starter",
            "price_usd": 29,
            "price_brl": 145,
            "credits_monthly": 300,
        },
        "pro": {
            "name": "Pro",
            "price_usd": 79,
            "price_brl": 395,
            "credits_monthly": 1000,
        },
        "business": {
            "name": "Business",
            "price_usd": 199,
            "price_brl": 995,
            "credits_monthly": 5000,
        },
    }

    @staticmethod
    def upgrade_plan(organization_id: str, new_plan: str) -> Dict[str, Any]:
        """
        Faz upgrade de plano.
        
        Args:
            organization_id: ID da organização
            new_plan: Novo plano
        
        Returns:
            Dicionário com resultado do upgrade
        """
        try:
            org = Organization.objects.get(organization_id=organization_id)
            old_plan = org.plan
            
            if old_plan == new_plan:
                return {"error": "Organização já está neste plano"}
            
            org.plan = new_plan
            org.credits_monthly = BillingService.PLANS[new_plan]["credits_monthly"]
            org.save()
            
            # Registra evento
            BillingEvent.objects.create(
                organization_id=organization_id,
                type="upgrade",
                old_plan=old_plan,
                new_plan=new_plan,
                amount=BillingService.PLANS[new_plan]["price_usd"]
            )
            
            return {
                "organization_id": str(organization_id),
                "old_plan": old_plan,
                "new_plan": new_plan,
                "status": "upgraded",
            }
        except Organization.DoesNotExist:
            return {"error": "Organização não encontrada"}
        except Exception as e:
            print(f"Erro ao fazer upgrade: {e}")
            return {"error": str(e)}

    @staticmethod
    def downgrade_plan(organization_id: str, new_plan: str) -> Dict[str, Any]:
        """
        Faz downgrade de plano (aplicado no próximo ciclo).
        
        Args:
            organization_id: ID da organização
            new_plan: Novo plano
        
        Returns:
            Dicionário com resultado do downgrade
        """
        try:
            org = Organization.objects.get(organization_id=organization_id)
            old_plan = org.plan
            
            if old_plan == new_plan:
                return {"error": "Organização já está neste plano"}
            
            # TODO: Implementar downgrade agendado para próximo ciclo
            
            # Registra evento
            BillingEvent.objects.create(
                organization_id=organization_id,
                type="downgrade",
                old_plan=old_plan,
                new_plan=new_plan
            )
            
            return {
                "organization_id": str(organization_id),
                "current_plan": old_plan,
                "downgrade_plan": new_plan,
                "status": "scheduled_for_next_cycle",
            }
        except Organization.DoesNotExist:
            return {"error": "Organização não encontrada"}
        except Exception as e:
            print(f"Erro ao fazer downgrade: {e}")
            return {"error": str(e)}

    @staticmethod
    def cancel_subscription(organization_id: str) -> Dict[str, Any]:
        """
        Cancela assinatura de uma organização.
        
        Args:
            organization_id: ID da organização
        
        Returns:
            Dicionário com resultado do cancelamento
        """
        try:
            org = Organization.objects.get(organization_id=organization_id)
            
            # TODO: Implementar cancelamento via Stripe
            
            # Registra evento
            BillingEvent.objects.create(
                organization_id=organization_id,
                type="subscription_canceled"
            )
            
            return {
                "organization_id": str(organization_id),
                "status": "cancellation_scheduled",
                "message": "Assinatura será cancelada no final do ciclo",
            }
        except Organization.DoesNotExist:
            return {"error": "Organização não encontrada"}
        except Exception as e:
            print(f"Erro ao cancelar assinatura: {e}")
            return {"error": str(e)}

    @staticmethod
    def renew_monthly_credits(organization_id: str) -> Dict[str, Any]:
        """
        Renova créditos mensais de uma organização.
        
        Args:
            organization_id: ID da organização
        
        Returns:
            Dicionário com resultado da renovação
        """
        try:
            org = Organization.objects.get(organization_id=organization_id)
            
            # Adiciona créditos mensais
            credits_to_add = BillingService.PLANS[org.plan]["credits_monthly"]
            org.credits_available += credits_to_add
            org.save()
            
            # Registra transação
            CreditTransaction.objects.create(
                organization_id=organization_id,
                amount=credits_to_add,
                type="monthly_renewal",
                reason=f"Monthly renewal for {org.plan} plan",
                balance_after=org.credits_available
            )
            
            # Registra evento
            BillingEvent.objects.create(
                organization_id=organization_id,
                type="renewal",
                amount=BillingService.PLANS[org.plan]["price_usd"]
            )
            
            return {
                "organization_id": str(organization_id),
                "credits_added": credits_to_add,
                "credits_available": org.credits_available,
                "status": "renewed",
            }
        except Organization.DoesNotExist:
            return {"error": "Organização não encontrada"}
        except Exception as e:
            print(f"Erro ao renovar créditos: {e}")
            return {"error": str(e)}

    @staticmethod
    def handle_payment_failure(organization_id: str) -> Dict[str, Any]:
        """
        Trata falha de pagamento.
        
        Args:
            organization_id: ID da organização
        
        Returns:
            Dicionário com resultado
        """
        try:
            org = Organization.objects.get(organization_id=organization_id)
            
            # TODO: Implementar grace period e retry automático
            
            # Registra evento
            BillingEvent.objects.create(
                organization_id=organization_id,
                type="payment_failed"
            )
            
            return {
                "organization_id": str(organization_id),
                "status": "payment_failed",
                "grace_period_days": 3,
            }
        except Organization.DoesNotExist:
            return {"error": "Organização não encontrada"}
        except Exception as e:
            print(f"Erro ao tratar falha de pagamento: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_billing_history(organization_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Obtém histórico de billing de uma organização.
        
        Args:
            organization_id: ID da organização
            limit: Número máximo de resultados
        
        Returns:
            Dicionário com histórico
        """
        try:
            transactions = CreditTransaction.objects.filter(
                organization_id=organization_id
            ).order_by("-created_at")[:limit]
            
            return {
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
            }
        except Exception as e:
            print(f"Erro ao obter histórico de billing: {e}")
            return {"error": str(e)}
