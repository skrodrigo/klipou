"""
Serviço para gerenciar performance de clips em redes sociais.
"""

from typing import Dict, Any, List
from ..models import ClipPerformance


class PerformanceService:
    """Serviço para gerenciar performance de clips."""

    @staticmethod
    def record_performance(
        clip_id: str,
        platform: str,
        post_url: str,
        views: int = 0,
        likes: int = 0,
        shares: int = 0,
        comments: int = 0
    ) -> Dict[str, Any]:
        """
        Registra performance de um clip em uma plataforma.
        
        Args:
            clip_id: ID do clip
            platform: Plataforma (tiktok, instagram, etc)
            post_url: URL do post
            views: Número de visualizações
            likes: Número de likes
            shares: Número de compartilhamentos
            comments: Número de comentários
        
        Returns:
            Dicionário com dados de performance
        """
        try:
            # Calcula engagement rate
            total_interactions = likes + shares + comments
            engagement_rate = (total_interactions / views * 100) if views > 0 else 0
            
            performance, created = ClipPerformance.objects.update_or_create(
                clip_id=clip_id,
                platform=platform,
                defaults={
                    "post_url": post_url,
                    "views": views,
                    "likes": likes,
                    "shares": shares,
                    "comments": comments,
                    "engagement_rate": engagement_rate,
                }
            )
            
            return {
                "performance_id": str(performance.performance_id),
                "clip_id": str(performance.clip_id),
                "platform": performance.platform,
                "views": performance.views,
                "likes": performance.likes,
                "shares": performance.shares,
                "comments": performance.comments,
                "engagement_rate": round(performance.engagement_rate, 2),
                "created": created,
            }
        except Exception as e:
            print(f"Erro ao registrar performance: {e}")
            return {}

    @staticmethod
    def get_clip_performance(clip_id: str) -> List[Dict[str, Any]]:
        """
        Obtém performance de um clip em todas as plataformas.
        
        Args:
            clip_id: ID do clip
        
        Returns:
            Lista de performance por plataforma
        """
        try:
            performances = ClipPerformance.objects.filter(clip_id=clip_id)
            
            return [
                {
                    "performance_id": str(p.performance_id),
                    "platform": p.platform,
                    "post_url": p.post_url,
                    "views": p.views,
                    "likes": p.likes,
                    "shares": p.shares,
                    "comments": p.comments,
                    "engagement_rate": round(p.engagement_rate, 2),
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in performances.order_by("-updated_at")
            ]
        except Exception as e:
            print(f"Erro ao obter performance: {e}")
            return []

    @staticmethod
    def get_top_performing_clips(platform: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtém clips com melhor performance.
        
        Args:
            platform: Filtrar por plataforma (opcional)
            limit: Número máximo de resultados
        
        Returns:
            Lista de clips com melhor performance
        """
        try:
            query = ClipPerformance.objects.all()
            
            if platform:
                query = query.filter(platform=platform)
            
            performances = query.order_by("-engagement_rate")[:limit]
            
            return [
                {
                    "clip_id": str(p.clip_id),
                    "platform": p.platform,
                    "views": p.views,
                    "engagement_rate": round(p.engagement_rate, 2),
                    "likes": p.likes,
                    "shares": p.shares,
                }
                for p in performances
            ]
        except Exception as e:
            print(f"Erro ao obter clips com melhor performance: {e}")
            return []

    @staticmethod
    def calculate_average_engagement(clip_id: str) -> float:
        """
        Calcula engagement rate médio de um clip.
        
        Args:
            clip_id: ID do clip
        
        Returns:
            Engagement rate médio
        """
        try:
            performances = ClipPerformance.objects.filter(clip_id=clip_id)
            
            if not performances.exists():
                return 0.0
            
            total_engagement = sum(p.engagement_rate for p in performances)
            average = total_engagement / performances.count()
            
            return round(average, 2)
        except Exception as e:
            print(f"Erro ao calcular engagement médio: {e}")
            return 0.0
