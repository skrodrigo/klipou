"""
Serviço para gerenciar templates visuais.
"""

from typing import Dict, Any, List
from ..models import Template


class TemplateService:
    """Serviço para gerenciar templates."""

    @staticmethod
    def create_template(
        name: str,
        type: str,
        ffmpeg_filter: str,
        preview_url: str = None
    ) -> Dict[str, Any]:
        """
        Cria um novo template.
        
        Args:
            name: Nome do template
            type: Tipo (overlay, bar, effect, text_style)
            ffmpeg_filter: Comando FFmpeg
            preview_url: URL de preview
        
        Returns:
            Dicionário com dados do template criado
        """
        try:
            valid_types = ["overlay", "bar", "effect", "text_style"]
            if type not in valid_types:
                return {}
            
            template = Template.objects.create(
                name=name,
                type=type,
                ffmpeg_filter=ffmpeg_filter,
                preview_url=preview_url,
                is_active=True
            )
            
            return {
                "template_id": str(template.template_id),
                "name": template.name,
                "type": template.type,
                "ffmpeg_filter": template.ffmpeg_filter,
                "preview_url": template.preview_url,
                "is_active": template.is_active,
                "version": template.version,
                "created_at": template.created_at.isoformat(),
            }
        except Exception as e:
            print(f"Erro ao criar template: {e}")
            return {}

    @staticmethod
    def list_templates(type: str = None) -> List[Dict[str, Any]]:
        """
        Lista templates.
        
        Args:
            type: Filtrar por tipo (opcional)
        
        Returns:
            Lista de templates
        """
        try:
            query = Template.objects.filter(is_active=True)
            
            if type:
                query = query.filter(type=type)
            
            return [
                {
                    "template_id": str(t.template_id),
                    "name": t.name,
                    "type": t.type,
                    "ffmpeg_filter": t.ffmpeg_filter,
                    "preview_url": t.preview_url,
                    "version": t.version,
                    "created_at": t.created_at.isoformat(),
                }
                for t in query.order_by("-created_at")
            ]
        except Exception as e:
            print(f"Erro ao listar templates: {e}")
            return []

    @staticmethod
    def update_template(
        template_id: str,
        name: str = None,
        ffmpeg_filter: str = None,
        preview_url: str = None
    ) -> Dict[str, Any]:
        """
        Atualiza um template.
        
        Args:
            template_id: ID do template
            name: Novo nome (opcional)
            ffmpeg_filter: Novo comando FFmpeg (opcional)
            preview_url: Nova URL de preview (opcional)
        
        Returns:
            Dicionário com dados do template atualizado
        """
        try:
            template = Template.objects.get(template_id=template_id)
            
            if name:
                template.name = name
            
            if ffmpeg_filter:
                template.ffmpeg_filter = ffmpeg_filter
            
            if preview_url:
                template.preview_url = preview_url
            
            template.version += 1
            template.save()
            
            return {
                "template_id": str(template.template_id),
                "name": template.name,
                "type": template.type,
                "ffmpeg_filter": template.ffmpeg_filter,
                "preview_url": template.preview_url,
                "version": template.version,
                "updated_at": template.updated_at.isoformat(),
            }
        except Template.DoesNotExist:
            return {}
        except Exception as e:
            print(f"Erro ao atualizar template: {e}")
            return {}

    @staticmethod
    def delete_template(template_id: str) -> bool:
        """
        Deleta um template (soft delete).
        
        Args:
            template_id: ID do template
        
        Returns:
            True se deletado com sucesso
        """
        try:
            template = Template.objects.get(template_id=template_id)
            template.is_active = False
            template.save()
            return True
        except Template.DoesNotExist:
            return False
        except Exception as e:
            print(f"Erro ao deletar template: {e}")
            return False

    @staticmethod
    def validate_ffmpeg_filter(ffmpeg_filter: str) -> tuple[bool, str]:
        """
        Valida um comando FFmpeg.
        
        Args:
            ffmpeg_filter: Comando FFmpeg
        
        Returns:
            Tupla (válido, mensagem de erro)
        """
        # TODO: Implementar validação real com ffmpeg
        if not ffmpeg_filter or len(ffmpeg_filter.strip()) == 0:
            return False, "Comando FFmpeg não pode estar vazio"
        
        return True, ""
