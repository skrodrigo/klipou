"""
Views para gerenciamento de webhooks customizados.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Webhook
from ..services.webhook_service import WebhookService


@api_view(["POST"])
def create_webhook(request):
    """
    Cria um novo webhook.
    
    Body:
    {
        "organization_id": "uuid",
        "url": "https://example.com/webhook",
        "events": ["job_completed", "job_failed"]
    }
    """
    try:
        organization_id = request.data.get("organization_id")
        url = request.data.get("url")
        events = request.data.get("events", [])
        
        if not organization_id or not url or not events:
            return Response(
                {"error": "organization_id, url e events são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida eventos
        valid_events = ["job_started", "job_completed", "job_failed", "clip_ready", "post_published"]
        for event in events:
            if event not in valid_events:
                return Response(
                    {"error": f"Evento inválido: {event}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        webhook_data = WebhookService.create_webhook(
            organization_id=organization_id,
            url=url,
            events=events
        )
        
        if not webhook_data:
            return Response(
                {"error": "Erro ao criar webhook"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return Response(webhook_data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def list_webhooks(request, organization_id):
    """
    Lista webhooks de uma organização.
    """
    try:
        webhooks = WebhookService.list_webhooks(organization_id)
        
        return Response(
            {
                "organization_id": str(organization_id),
                "webhooks": webhooks,
                "total": len(webhooks),
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def delete_webhook(request, webhook_id):
    """
    Deleta um webhook.
    """
    try:
        success = WebhookService.delete_webhook(webhook_id)
        
        if not success:
            return Response(
                {"error": "Webhook não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(
            {
                "webhook_id": str(webhook_id),
                "status": "deleted",
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def test_webhook(request, webhook_id):
    """
    Testa um webhook disparando um evento de teste.
    """
    try:
        success = WebhookService.test_webhook(webhook_id)
        
        if not success:
            return Response(
                {"error": "Falha ao testar webhook"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return Response(
            {
                "webhook_id": str(webhook_id),
                "status": "test_sent",
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
