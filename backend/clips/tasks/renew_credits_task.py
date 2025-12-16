"""
Task para renovação mensal de créditos.
Padrão Fan-out: Dispatch (mestre) + Workers (individuais).
Execução: Celery Beat todo dia às 00:01.
Idempotência: Verificação de ciclo de 20 dias + transação atômica.
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import Organization, CreditTransaction

logger = logging.getLogger(__name__)


@shared_task
def dispatch_daily_renewals_task() -> dict:
    """
    TASK MESTRE (Rodar via Celery Beat todo dia às 00:01).
    
    Função:
    1. Identifica quais organizações fazem 'aniversário' de assinatura hoje.
    2. Dispara uma task individual para cada uma.
    3. Rápida e escalável (não processa créditos, apenas dispara).
    """
    today = timezone.now().date()
    logger.info(f"[DISPATCH] Iniciando dispatch de renovações para {today}")

    try:
        # Busca organizações ativas
        active_orgs = Organization.objects.filter(
            subscription__status="active"
        ).select_related("subscription")
        
        count = 0
        for org in active_orgs:
            # Lógica de Aniversário:
            # Verifica se o dia de hoje == dia de início da assinatura
            subscription_start = org.subscription.created_at.date()
            
            if subscription_start.day == today.day:
                # Dispara task individual para renovação
                renew_organization_credits_task.delay(str(org.organization_id))
                count += 1
                logger.debug(f"[DISPATCH] Disparada renovação para org {org.organization_id}")
        
        logger.info(f"[DISPATCH] Disparadas {count} tarefas de renovação.")
        return {
            "status": "success",
            "dispatched_count": count,
            "timestamp": timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[DISPATCH] Erro ao disparar renovações: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": timezone.now().isoformat()
        }


@shared_task(bind=True, max_retries=3)
def renew_organization_credits_task(self, organization_id: str) -> dict:
    """
    TASK TRABALHADORA.
    Renova créditos de UMA organização de forma atômica e segura.
    
    Segurança:
    - transaction.atomic(): Garante atomicidade (tudo ou nada).
    - select_for_update(): Bloqueia a linha para evitar race conditions.
    - Verificação de ciclo de 20 dias: Idempotência contra duplicação.
    """
    try:
        with transaction.atomic():
            # Bloqueia a linha da organização para evitar race condition
            org = Organization.objects.select_for_update().get(
                organization_id=organization_id
            )
            
            # --- VERIFICAÇÃO DE SEGURANÇA (Idempotência Mensal) ---
            # Verifica se já houve renovação nos últimos 20 dias (margem segura para mês)
            last_month = timezone.now() - timedelta(days=20)
            
            already_renewed = CreditTransaction.objects.filter(
                organization_id=org.organization_id,
                type="monthly_renewal",
                created_at__gte=last_month
            ).exists()

            if already_renewed:
                logger.warning(
                    f"[RENEW] Org {org.organization_id} já renovou créditos "
                    f"nos últimos 20 dias. Ignorando."
                )
                return {
                    "status": "skipped",
                    "reason": "already_renewed_recently",
                    "org": str(org.organization_id)
                }

            # Obtém plano
            plan = org.subscription.plan if hasattr(org, "subscription") else None
            monthly_credits = _get_monthly_credits_for_plan(plan)

            if monthly_credits <= 0:
                logger.warning(
                    f"[RENEW] Org {org.organization_id} plano {plan} "
                    f"não tem créditos configurados."
                )
                return {
                    "status": "skipped",
                    "reason": "no_credits_for_plan",
                    "org": str(org.organization_id)
                }

            # --- RENOVAÇÃO ATÔMICA ---
            previous_balance = org.credits_available
            
            # Acumula créditos (não reseta)
            org.credits_available += monthly_credits
            org.save()

            # Registra transação (dentro da mesma transação atômica)
            CreditTransaction.objects.create(
                organization_id=org.organization_id,
                amount=monthly_credits,
                type="monthly_renewal",
                reason=f"Renovação Mensal - Plano {plan.capitalize()}",
                balance_before=previous_balance,
                balance_after=org.credits_available,
            )

            logger.info(
                f"[RENEW] Renovado: {org.organization_id} "
                f"(+{monthly_credits}). Novo saldo: {org.credits_available}"
            )
            
            # TODO: Disparar envio de e-mail assíncrono
            # send_renewal_email_task.delay(str(org.organization_id), monthly_credits)

            return {
                "status": "success",
                "org": str(org.organization_id),
                "added": monthly_credits,
                "new_balance": org.credits_available,
                "timestamp": timezone.now().isoformat()
            }

    except Organization.DoesNotExist:
        logger.error(f"[RENEW] Org {organization_id} não encontrada.")
        return {
            "status": "failed",
            "error": "Organization not found",
            "org": organization_id
        }
    except Exception as e:
        logger.error(
            f"[RENEW] Erro ao renovar {organization_id}: {e}",
            exc_info=True
        )
        # Retry em caso de erro de banco de dados/lock
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        
        return {
            "status": "failed",
            "error": str(e),
            "org": organization_id,
            "retries_exhausted": True
        }


def _get_monthly_credits_for_plan(plan: str) -> int:
    """
    Configuração centralizada de créditos por plano.
    Busca de settings.py para facilitar mudanças sem alterar código.
    """
    PLAN_CREDITS = getattr(settings, "PLAN_CREDITS", {
        "starter": 300,
        "pro": 1000,
        "business": 5000,
    })
    return PLAN_CREDITS.get(plan.lower() if plan else "", 0)


# Alias para compatibilidade com imports antigos
renew_credits_task = dispatch_daily_renewals_task
