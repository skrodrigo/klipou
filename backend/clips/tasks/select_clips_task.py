"""
Task para seleção de clips.
Etapa: Selecting
Combinação de score Gemini, embeddings e regras fixas.
"""

import re
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript
from .job_utils import update_job_status


@shared_task(bind=True, max_retries=5)
def select_clips_task(self, video_id: int) -> dict:
    """
    Seleção de clips baseada em:
    - Score Gemini
    - Regras fixas (duração, densidade de fala, emoção)
    - Proporções desejadas
    
    Seleciona Top N clips respeitando num_clips.
    """
    try:
        # Procura vídeo por video_id (UUID)
        video = Video.objects.get(video_id=video_id)
        
        # Obtém organização
        from ..models import Organization
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "selecting"
        video.current_step = "selecting"
        video.save()

        # Obtém transcrição e análise
        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        analysis_data = transcript.analysis_data or {}
        candidates = analysis_data.get("candidates", [])

        if not candidates:
            raise Exception("Nenhum candidato de clip encontrado na análise")

        # Aplica scoring e seleção
        selected_clips = _select_best_clips(
            candidates=candidates,
            max_clip_duration=60,  # Padrão, pode vir de configuração
            min_clip_duration=10,
            num_clips=5,  # Padrão, pode vir de configuração
            min_engagement_score=40,
        )

        if not selected_clips:
            raise Exception("Nenhum clip passou nos critérios de seleção")

        # Armazena seleção na transcrição
        transcript.selected_clips = selected_clips
        transcript.save()

        # Atualiza vídeo
        video.last_successful_step = "selecting"
        video.status = "reframing"
        video.current_step = "reframing"
        video.save()
        
        # Atualiza job status
        update_job_status(str(video.video_id), "reframing", progress=70, current_step="reframing")

        # Dispara próxima task (reframing)
        try:
            from .reframe_video_task import reframe_video_task
            task = reframe_video_task.apply_async(
                args=[str(video.video_id)],
                queue=f"video.reframe.{org.plan}",
            )
            print(f"[select_clips_task] Disparou reframe_video_task: {task.id}")
        except Exception as e:
            print(f"[select_clips_task] Erro ao disparar reframe_video_task: {e}")
            raise

        return {
            "video_id": str(video.video_id),
            "status": "reframing",
            "selected_clips_count": len(selected_clips),
            "candidates_count": len(candidates),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "selecting"
        video.error_code = "SELECTION_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _select_best_clips(
    candidates: list,
    max_clip_duration: float = 60,
    min_clip_duration: float = 10,
    num_clips: int = 5,
    min_engagement_score: int = 40,
) -> list:
    """
    Seleciona os melhores clips baseado em scoring.
    
    Critérios:
    - Duração dentro dos limites
    - Score de engajamento >= min_engagement_score
    - Ordenado por score de engajamento
    """
    scored_clips = []

    for candidate in candidates:
        start_time = float(candidate.get("start_time", 0))
        end_time = float(candidate.get("end_time", 0))
        duration = end_time - start_time
        engagement_score = int(candidate.get("engagement_score", 0) * 10)  # Converte 0-10 para 0-100

        # Validações de duração
        if duration < min_clip_duration or duration > max_clip_duration:
            continue

        # Validação de score
        if engagement_score < min_engagement_score:
            continue

        # Calcula score final
        final_score = _calculate_clip_score(candidate, engagement_score)

        scored_clips.append({
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "text": candidate.get("text", ""),
            "hook_title": candidate.get("hook_title", ""),
            "tone": candidate.get("tone", ""),
            "engagement_score": engagement_score,
            "final_score": final_score,
        })

    # Ordena por score final (descendente)
    scored_clips.sort(key=lambda x: x["final_score"], reverse=True)

    # Retorna top N clips
    return scored_clips[:num_clips]


def _calculate_clip_score(candidate: dict, engagement_score: int) -> float:
    """
    Calcula score final do clip combinando múltiplos fatores.
    
    Fatores:
    - Engagement score (70%)
    - Presença de palavras-chave (15%)
    - Tom/emoção (15%)
    """
    # Score de engajamento (0-100)
    engagement_weight = engagement_score * 0.7

    # Palavras-chave (0-100)
    text = (candidate.get("text") or "").lower()
    keyword_score = _score_keywords(text) * 0.15

    # Tom/emoção (0-100)
    tone = (candidate.get("tone") or "").lower()
    tone_score = _score_tone(tone) * 0.15

    final_score = engagement_weight + keyword_score + tone_score
    return final_score


def _score_keywords(text: str) -> float:
    """Calcula score baseado em palavras-chave."""
    keyword_set = {
        "segredo", "importante", "nunca", "sempre", "erro", "certo",
        "melhor", "pior", "dica", "hack", "truque", "atenção", "alerta",
        "cuidado", "viral", "crescer", "vender", "dinheiro", "resultado",
        "história", "story", "incrível", "fantástico", "perfeito",
    }

    words = re.findall(r"\w+", text)
    keyword_hits = sum(1 for w in words if w in keyword_set)

    # Score: 0-100 baseado em densidade de palavras-chave
    if not words:
        return 0
    return min(100, (keyword_hits / len(words)) * 100 * 2)


def _score_tone(tone: str) -> float:
    """Calcula score baseado em tom/emoção."""
    positive_tones = {
        "positivo", "positive", "inspirador", "inspiring", "motivador",
        "motivating", "entusiasmado", "enthusiastic", "alegre", "happy",
        "empolgante", "exciting", "incrível", "amazing",
    }

    negative_tones = {
        "negativo", "negative", "triste", "sad", "chato", "boring",
        "deprimido", "depressed", "irritado", "angry",
    }

    if tone in positive_tones:
        return 100
    elif tone in negative_tones:
        return 30
    else:
        return 50  # Neutro
