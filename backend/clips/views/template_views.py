"""
Views para gerenciamento de templates visuais.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Template
from ..services.template_service import TemplateService


@api_view(["GET"])
def list_templates(request):
    """
    Lista todos os templates.
    
    Query params:
    - type: filtrar por tipo (overlay, bar, effect, text_style)
    """
    try:
        type_filter = request.query_params.get("type")
        
        templates = TemplateService.list_templates(type=type_filter)
        
        return Response(
            {
                "templates": templates,
                "total": len(templates),
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def create_template(request):
    """
    Cria um novo template.
    
    Body:
    {
        "name": "Pro Style",
        "type": "overlay|bar|effect|text_style",
        "ffmpeg_filter": "[0:v]scale=1280:720[out]",
        "preview_url": "https://example.com/preview.jpg"
    }
    """
    try:
        name = request.data.get("name")
        type_template = request.data.get("type")
        ffmpeg_filter = request.data.get("ffmpeg_filter")
        preview_url = request.data.get("preview_url")
        
        if not name or not type_template or not ffmpeg_filter:
            return Response(
                {"error": "name, type e ffmpeg_filter são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida tipo
        valid_types = ["overlay", "bar", "effect", "text_style"]
        if type_template not in valid_types:
            return Response(
                {"error": f"Tipo inválido. Válidos: {', '.join(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida FFmpeg filter
        is_valid, error_msg = TemplateService.validate_ffmpeg_filter(ffmpeg_filter)
        if not is_valid:
            return Response(
                {"error": error_msg},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        template_data = TemplateService.create_template(
            name=name,
            type=type_template,
            ffmpeg_filter=ffmpeg_filter,
            preview_url=preview_url
        )
        
        if not template_data:
            return Response(
                {"error": "Erro ao criar template"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return Response(template_data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
def update_template(request, template_id):
    """
    Atualiza um template.
    
    Body:
    {
        "name": "Pro Style v2",
        "ffmpeg_filter": "[0:v]scale=1920:1080[out]",
        "preview_url": "https://example.com/preview-v2.jpg"
    }
    """
    try:
        name = request.data.get("name")
        ffmpeg_filter = request.data.get("ffmpeg_filter")
        preview_url = request.data.get("preview_url")
        
        if not name and not ffmpeg_filter and not preview_url:
            return Response(
                {"error": "Nenhum campo para atualizar"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida FFmpeg filter se fornecido
        if ffmpeg_filter:
            is_valid, error_msg = TemplateService.validate_ffmpeg_filter(ffmpeg_filter)
            if not is_valid:
                return Response(
                    {"error": error_msg},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        template_data = TemplateService.update_template(
            template_id=template_id,
            name=name,
            ffmpeg_filter=ffmpeg_filter,
            preview_url=preview_url
        )
        
        if not template_data:
            return Response(
                {"error": "Template não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(template_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def delete_template(request, template_id):
    """
    Deleta um template.
    """
    try:
        success = TemplateService.delete_template(template_id)
        
        if not success:
            return Response(
                {"error": "Template não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(
            {
                "template_id": str(template_id),
                "status": "deleted",
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
