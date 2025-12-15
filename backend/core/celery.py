import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("klipai")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Configuração de filas por etapa com prioridades
app.conf.task_queues = {
    # Ingestion
    "video.ingestion": {"exchange": "video", "routing_key": "ingestion"},
    
    # Download (por plano)
    "video.download.starter": {"exchange": "video", "routing_key": "download.starter", "priority": 1},
    "video.download.pro": {"exchange": "video", "routing_key": "download.pro", "priority": 5},
    "video.download.business": {"exchange": "video", "routing_key": "download.business", "priority": 10},
    
    # Normalize (por plano)
    "video.normalize.starter": {"exchange": "video", "routing_key": "normalize.starter", "priority": 1},
    "video.normalize.pro": {"exchange": "video", "routing_key": "normalize.pro", "priority": 5},
    "video.normalize.business": {"exchange": "video", "routing_key": "normalize.business", "priority": 10},
    
    # Transcribe (por plano)
    "video.transcribe.starter": {"exchange": "video", "routing_key": "transcribe.starter", "priority": 1},
    "video.transcribe.pro": {"exchange": "video", "routing_key": "transcribe.pro", "priority": 5},
    "video.transcribe.business": {"exchange": "video", "routing_key": "transcribe.business", "priority": 10},
    
    # Analyze (por plano)
    "video.analyze.starter": {"exchange": "video", "routing_key": "analyze.starter", "priority": 1},
    "video.analyze.pro": {"exchange": "video", "routing_key": "analyze.pro", "priority": 5},
    "video.analyze.business": {"exchange": "video", "routing_key": "analyze.business", "priority": 10},
    
    # Classify (por plano)
    "video.classify.starter": {"exchange": "video", "routing_key": "classify.starter", "priority": 1},
    "video.classify.pro": {"exchange": "video", "routing_key": "classify.pro", "priority": 5},
    "video.classify.business": {"exchange": "video", "routing_key": "classify.business", "priority": 10},
    
    # Select (por plano)
    "video.select.starter": {"exchange": "video", "routing_key": "select.starter", "priority": 1},
    "video.select.pro": {"exchange": "video", "routing_key": "select.pro", "priority": 5},
    "video.select.business": {"exchange": "video", "routing_key": "select.business", "priority": 10},
    
    # Reframe (apenas Pro e Business)
    "video.reframe.pro": {"exchange": "video", "routing_key": "reframe.pro", "priority": 5},
    "video.reframe.business": {"exchange": "video", "routing_key": "reframe.business", "priority": 10},
    
    # Clip (por plano)
    "video.clip.starter": {"exchange": "video", "routing_key": "clip.starter", "priority": 1},
    "video.clip.pro": {"exchange": "video", "routing_key": "clip.pro", "priority": 5},
    "video.clip.business": {"exchange": "video", "routing_key": "clip.business", "priority": 10},
    
    # Caption (por plano)
    "video.caption.starter": {"exchange": "video", "routing_key": "caption.starter", "priority": 1},
    "video.caption.pro": {"exchange": "video", "routing_key": "caption.pro", "priority": 5},
    "video.caption.business": {"exchange": "video", "routing_key": "caption.business", "priority": 10},
    
    # Cron jobs
    "cron.credits": {"exchange": "cron", "routing_key": "credits"},
    "cron.cleanup": {"exchange": "cron", "routing_key": "cleanup"},
}

# Configuração de cron jobs (beat schedule)
app.conf.beat_schedule = {
    # Renovação mensal de créditos (1º dia do mês às 00:00)
    "renew-credits-monthly": {
        "task": "clips.tasks.renew_credits_task",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),
        "options": {"queue": "cron.credits"},
    },
    # Limpeza diária de dados antigos (todos os dias às 02:00)
    "cleanup-old-data-daily": {
        "task": "clips.tasks.cleanup_old_data_task",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "cron.cleanup"},
    },
}

# Roteamento de tasks para filas específicas
app.conf.task_routes = {
    # Download
    "clips.tasks.download_video_task": {"queue": "video.download.starter"},
    
    # Normalize
    "clips.tasks.normalize_video_task": {"queue": "video.normalize.starter"},
    
    # Transcribe
    "clips.tasks.transcribe_video_task": {"queue": "video.transcribe.starter"},
    
    # Analyze
    "clips.tasks.analyze_semantic_task": {"queue": "video.analyze.starter"},
    
    # Classify
    "clips.tasks.embed_classify_task": {"queue": "video.classify.starter"},
    
    # Select
    "clips.tasks.select_clips_task": {"queue": "video.select.starter"},
    
    # Reframe
    "clips.tasks.reframe_video_task": {"queue": "video.reframe.pro"},
    
    # Caption
    "clips.tasks.caption_clips_task": {"queue": "video.caption.starter"},
    
    # Clip
    "clips.tasks.clip_generation_task": {"queue": "video.clip.starter"},
    
    # Post
    "clips.tasks.post_to_social_task": {"queue": "default"},
    
    # Cron
    "clips.tasks.renew_credits_task": {"queue": "cron.credits"},
    "clips.tasks.cleanup_old_data_task": {"queue": "cron.cleanup"},
}

# Configurações gerais
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_time_limit = 30 * 60  # 30 minutos por etapa
app.conf.task_soft_time_limit = 25 * 60  # 25 minutos (aviso antes do hard limit)
