"""
Serviço para gerenciar e disparar webhooks customizados.
"""

import json
import hmac
import hashlib
import requests
from typing import Dict, Any, List
from datetime import datetime, timedelta

from ..models import Webhook


class WebhookService:
    """Serviço para gerenciar webhooks."""

    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = [1, 3, 5]  # segundos
    TIMEOUT = 30

    @staticmethod
    def create_webhook(
        organization_id: str,
        url: str,
        events: List[str],
        secret: str = None
    ) -> Dict[str, Any]:
        """
        Cria um novo webhook.
        
        Args:
            organization_id: ID da organização
            url: URL do webhook
            events: Lista de eventos a disparar
            secret: Secret para validação HMAC (gerado se não fornecido)
        
        Returns:
            Dicionário com dados do webhook criado
        """
        try:
            if not secret:
                secret = hashlib.sha256(
                    f"{organization_id}{datetime.now().isoformat()}".encode()
                ).hexdigest()[:32]
            
            webhook = Webhook.objects.create(
                organization_id=organization_id,
                url=url,
                events=events,
                secret=secret,
                is_active=True
            )
            
            return {
                "webhook_id": str(webhook.webhook_id),
                "url": webhook.url,
                "events": webhook.events,
                "is_active": webhook.is_active,
                "created_at": webhook.created_at.isoformat(),
            }
        except Exception as e:
            print(f"Erro ao criar webhook: {e}")
            return {}

    @staticmethod
    def trigger_webhook(
        organization_id: str,
        event: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Dispara webhooks para um evento específico.
        
        Args:
            organization_id: ID da organização
            event: Nome do evento
            data: Dados do evento
        
        Returns:
            True se disparado com sucesso
        """
        try:
            webhooks = Webhook.objects.filter(
                organization_id=organization_id,
                is_active=True
            )
            
            for webhook in webhooks:
                if event not in webhook.events:
                    continue
                
                # Dispara webhook com retry
                WebhookService._dispatch_with_retry(webhook, event, data)
            
            return True
        except Exception as e:
            print(f"Erro ao disparar webhook: {e}")
            return False

    @staticmethod
    def _dispatch_with_retry(webhook: Webhook, event: str, data: Dict[str, Any]) -> bool:
        """
        Dispara webhook com retry automático.
        
        Args:
            webhook: Objeto Webhook
            event: Nome do evento
            data: Dados do evento
        
        Returns:
            True se disparado com sucesso
        """
        payload = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "organization_id": str(webhook.organization_id),
            "data": data,
        }
        
        # Gera assinatura HMAC
        payload_json = json.dumps(payload)
        signature = hmac.new(
            webhook.secret.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        payload["signature"] = f"sha256={signature}"
        
        # Retry com backoff exponencial
        for attempt in range(WebhookService.RETRY_ATTEMPTS):
            try:
                response = requests.post(
                    webhook.url,
                    json=payload,
                    timeout=WebhookService.TIMEOUT,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [200, 201, 202]:
                    # Atualiza last_triggered_at
                    webhook.last_triggered_at = datetime.now()
                    webhook.save()
                    return True
                
            except requests.RequestException as e:
                print(f"Tentativa {attempt + 1} falhou: {e}")
                
                if attempt < WebhookService.RETRY_ATTEMPTS - 1:
                    import time
                    time.sleep(WebhookService.RETRY_BACKOFF[attempt])
        
        return False

    @staticmethod
    def list_webhooks(organization_id: str) -> List[Dict[str, Any]]:
        """
        Lista webhooks de uma organização.
        
        Args:
            organization_id: ID da organização
        
        Returns:
            Lista de webhooks
        """
        try:
            webhooks = Webhook.objects.filter(
                organization_id=organization_id,
                is_active=True
            ).order_by("-created_at")
            
            return [
                {
                    "webhook_id": str(webhook.webhook_id),
                    "url": webhook.url,
                    "events": webhook.events,
                    "is_active": webhook.is_active,
                    "created_at": webhook.created_at.isoformat(),
                    "last_triggered_at": webhook.last_triggered_at.isoformat() if webhook.last_triggered_at else None,
                }
                for webhook in webhooks
            ]
        except Exception as e:
            print(f"Erro ao listar webhooks: {e}")
            return []

    @staticmethod
    def delete_webhook(webhook_id: str) -> bool:
        """
        Deleta um webhook (soft delete).
        
        Args:
            webhook_id: ID do webhook
        
        Returns:
            True se deletado com sucesso
        """
        try:
            webhook = Webhook.objects.get(webhook_id=webhook_id)
            webhook.is_active = False
            webhook.save()
            return True
        except Webhook.DoesNotExist:
            return False
        except Exception as e:
            print(f"Erro ao deletar webhook: {e}")
            return False

    @staticmethod
    def test_webhook(webhook_id: str) -> bool:
        """
        Testa um webhook disparando um evento de teste.
        
        Args:
            webhook_id: ID do webhook
        
        Returns:
            True se teste bem-sucedido
        """
        try:
            webhook = Webhook.objects.get(webhook_id=webhook_id)
            
            test_data = {
                "test": True,
                "message": "Este é um evento de teste"
            }
            
            return WebhookService._dispatch_with_retry(webhook, "test", test_data)
        except Webhook.DoesNotExist:
            return False
        except Exception as e:
            print(f"Erro ao testar webhook: {e}")
            return False
