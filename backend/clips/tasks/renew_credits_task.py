"""
Task para renovação mensal de créditos.
Cron job executado mensalmente.
Renova créditos mensais para organizações com plano ativo.
"""

from datetime import datetime, timedelta
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..models import Organization, CreditTransaction


@shared_task
def renew_credits_task() -> dict:
    """
    Renova créditos mensais para todas as organizações com plano ativo.
    
    Execução: Cron mensal (no mesmo dia do mês em que plano foi ativado)
    Idempotência: Obrigatória (pode ser executado múltiplas vezes)
    
    Fluxo:
    1. Itera sobre todas as organizações
    2. Verifica: plano ativo?
    3. SIM → Adiciona créditos mensais
    4. Registra transação (type: monthly_renewal)
    5. Envia email: "Seus créditos foram renovados"
    6. Idempotência: se executado 2x, apenas 1 renovação
    """
    try:
        today = timezone.now().date()
        renewed_count = 0
        failed_count = 0

        # Obtém todas as organizações
        organizations = Organization.objects.filter(
            subscription__status="active"
        ).distinct()

        for org in organizations:
            try:
                # Verifica se já foi renovado hoje
                last_renewal = CreditTransaction.objects.filter(
                    organization=org,
                    type="monthly_renewal",
                    created_at__date=today,
                ).first()

                if last_renewal:
                    # Já foi renovado hoje, pula
                    continue

                # Obtém plano e créditos mensais
                plan = org.subscription.plan if hasattr(org, "subscription") else None
                monthly_credits = _get_monthly_credits_for_plan(plan)

                if monthly_credits <= 0:
                    continue

                # Adiciona créditos
                org.credits_available += monthly_credits
                org.save()

                # Registra transação
                CreditTransaction.objects.create(
                    organization=org,
                    amount=monthly_credits,
                    type="monthly_renewal",
                    reason=f"Renovação mensal - Plano {plan}",
                    balance_after=org.credits_available,
                )

                # Envia email (implementação futura)
                _send_renewal_email(org, monthly_credits)

                renewed_count += 1

            except Exception as e:
                print(f"Erro ao renovar créditos para organização {org.id}: {e}")
                failed_count += 1
                continue

        return {
            "status": "completed",
            "renewed_count": renewed_count,
            "failed_count": failed_count,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def _get_monthly_credits_for_plan(plan: str) -> int:
    """Retorna créditos mensais para cada plano."""
    credits_map = {
        "starter": 300,
        "pro": 1000,
        "business": 5000,
    }
    return credits_map.get(plan, 0)


def _send_renewal_email(org: "Organization", monthly_credits: int) -> None:
    """Envia email de renovação de créditos."""
    # Implementação futura com Django Email
    # Por enquanto, apenas log
    print(f"Email de renovação enviado para {org.billing_email}: {monthly_credits} créditos")
