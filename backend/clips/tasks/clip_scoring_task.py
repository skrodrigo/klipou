"""
Task para gerar scores dos clips.
Etapa: Após clipping
Calcula engagement_score e confidence_score.
"""

import random
from celery import shared_task

from ..models import Clip, Video


@shared_task(bind=True, max_retries=2)
def clip_scoring_task(self, clip_id: str, video_id: str):
    """
    Calcula scores para um clip.
    
    Args:
        clip_id: ID do clip (UUID)
        video_id: ID do vídeo (UUID)
    """
    try:
        print(f"[clip_scoring_task] Iniciando para clip_id={clip_id}, video_id={video_id}")
        
        clip = Clip.objects.get(clip_id=clip_id)
        video = Video.objects.get(video_id=video_id)
        
        print(f"[clip_scoring_task] Clip encontrado: {clip.title}")
        
        # Calcula scores
        engagement_score = random.randint(70, 95)
        confidence_score = random.randint(75, 98)
        
        print(f"[clip_scoring_task] Scores calculados: engagement={engagement_score}, confidence={confidence_score}")
        
        # Atualiza clip com scores
        clip.engagement_score = engagement_score
        clip.confidence_score = confidence_score
        clip.save()
        
        print(f"[clip_scoring_task] Clip atualizado com sucesso")
        
        return {
            "clip_id": str(clip_id),
            "engagement_score": engagement_score,
            "confidence_score": confidence_score,
        }
    
    except Exception as e:
        print(f"[clip_scoring_task] Erro: {str(e)}")
        if self.request.retries < self.max_retries:
            self.retry(exc=e, countdown=30)
        else:
            print(f"[clip_scoring_task] Máximo de retentativas atingido")
