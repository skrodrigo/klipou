"""
Serviço de envio de emails.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


class EmailService:
    """Serviço para envio de emails."""

    @staticmethod
    def send_job_completed(organization_email: str, job_id: str, clips_count: int) -> bool:
        """Envia email de conclusão de job."""
        try:
            subject = "Seus clips estão prontos! 🎬"
            context = {
                "job_id": job_id,
                "clips_count": clips_count,
            }
            html_message = render_to_string("emails/job_completed.html", context)
            
            send_mail(
                subject,
                f"Seu job {job_id} foi concluído com {clips_count} clips.",
                settings.DEFAULT_FROM_EMAIL,
                [organization_email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Erro ao enviar email de conclusão: {e}")
            return False

    @staticmethod
    def send_job_failed(organization_email: str, job_id: str, error_message: str) -> bool:
        """Envia email de falha de job."""
        try:
            subject = "Seu job falhou ❌"
            context = {
                "job_id": job_id,
                "error_message": error_message,
            }
            html_message = render_to_string("emails/job_failed.html", context)
            
            send_mail(
                subject,
                f"Seu job {job_id} falhou: {error_message}",
                settings.DEFAULT_FROM_EMAIL,
                [organization_email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Erro ao enviar email de falha: {e}")
            return False

    @staticmethod
    def send_credits_renewed(organization_email: str, credits: int) -> bool:
        """Envia email de renovação de créditos."""
        try:
            subject = "Seus créditos foram renovados! 💳"
            context = {
                "credits": credits,
            }
            html_message = render_to_string("emails/credits_renewed.html", context)
            
            send_mail(
                subject,
                f"Seus créditos foram renovados: {credits} créditos adicionados.",
                settings.DEFAULT_FROM_EMAIL,
                [organization_email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Erro ao enviar email de renovação: {e}")
            return False

    @staticmethod
    def send_payment_failed(organization_email: str, amount: float) -> bool:
        """Envia email de falha de pagamento."""
        try:
            subject = "Falha no pagamento ⚠️"
            context = {
                "amount": amount,
            }
            html_message = render_to_string("emails/payment_failed.html", context)
            
            send_mail(
                subject,
                f"Falha ao processar pagamento de ${amount:.2f}. Tente novamente.",
                settings.DEFAULT_FROM_EMAIL,
                [organization_email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Erro ao enviar email de falha de pagamento: {e}")
            return False

    @staticmethod
    def send_team_invitation(email: str, organization_name: str, invite_link: str) -> bool:
        """Envia email de convite para membro da equipe."""
        try:
            subject = f"Você foi convidado para {organization_name}"
            context = {
                "organization_name": organization_name,
                "invite_link": invite_link,
            }
            html_message = render_to_string("emails/team_invitation.html", context)
            
            send_mail(
                subject,
                f"Você foi convidado para se juntar a {organization_name}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Erro ao enviar email de convite: {e}")
            return False
