from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-ossyduj@zo^*$93=5m3g@p91$5x=++3ku2hi$tya3t^689un77')
DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'authentication',
    'clips',
]

AUTH_USER_MODEL = 'authentication.CustomUser'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    parsed_url = urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': (parsed_url.path.lstrip('/') or ''),
            'USER': parsed_url.username or '',
            'PASSWORD': parsed_url.password or '',
            'HOST': parsed_url.hostname or '',
            'PORT': str(parsed_url.port) if parsed_url.port else '',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'klipai'),
            'USER': os.getenv('DB_USER', 'klipai'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'klipai'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'


# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\\d+$",
    r"^http://127\\.0\\.0\\.1:\\d+$",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-organization-id",
]

# Session Configuration
SESSION_COOKIE_SECURE = False  # True em produção (HTTPS)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# CSRF Configuration
CSRF_COOKIE_SECURE = False  # True em produção (HTTPS)
CSRF_COOKIE_HTTPONLY = False  
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Cloudflare R2 Configuration
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')
CLOUDFLARE_ACCESS_KEY_ID = os.getenv('CLOUDFLARE_ACCESS_KEY_ID')
CLOUDFLARE_SECRET_ACCESS_KEY = os.getenv('CLOUDFLARE_SECRET_ACCESS_KEY')
CLOUDFLARE_BUCKET_NAME = os.getenv('CLOUDFLARE_BUCKET_NAME')
CLOUDFLARE_R2_PUBLIC_URL = os.getenv('CLOUDFLARE_R2_PUBLIC_URL')

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Gemini Whisper transcript refinement (optional)
GEMINI_REFINE_WHISPER_TRANSCRIPT = os.getenv('GEMINI_REFINE_WHISPER_TRANSCRIPT', 'true').lower() == 'true'
GEMINI_REFINE_MODEL = os.getenv('GEMINI_REFINE_MODEL', 'gemini-2.5-flash-lite')
GEMINI_REFINE_TEMPERATURE = float(os.getenv('GEMINI_REFINE_TEMPERATURE', '0.2'))
GEMINI_REFINE_MAX_SEGMENTS = int(os.getenv('GEMINI_REFINE_MAX_SEGMENTS', '120'))

# Whisper tuning (optional)
WHISPER_MODEL = os.getenv('WHISPER_MODEL')
WHISPER_DEVICE = os.getenv('WHISPER_DEVICE')
WHISPER_WORD_TIMESTAMPS = os.getenv('WHISPER_WORD_TIMESTAMPS', 'true').lower() == 'true'
WHISPER_BEAM_SIZE = int(os.getenv('WHISPER_BEAM_SIZE', '1'))
WHISPER_BEST_OF = int(os.getenv('WHISPER_BEST_OF', '1'))
WHISPER_FP16 = os.getenv('WHISPER_FP16', 'true').lower() == 'true'

# Reframe tuning (optional)
REFRAME_SAMPLE_EVERY_SECONDS = float(os.getenv('REFRAME_SAMPLE_EVERY_SECONDS', '1.0'))
REFRAME_MAX_FACE_SAMPLES = int(os.getenv('REFRAME_MAX_FACE_SAMPLES', '240'))
REFRAME_MIN_SAMPLES_TO_STOP = int(os.getenv('REFRAME_MIN_SAMPLES_TO_STOP', '90'))

# Redis Cache Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
        }
    }
}

# Cache timeout: 30 days
CACHE_TIMEOUT = 86400 * 30

# OAuth Configuration
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# OAuth Credentials
TIKTOK_CLIENT_ID = os.getenv('TIKTOK_CLIENT_ID')
TIKTOK_CLIENT_SECRET = os.getenv('TIKTOK_CLIENT_SECRET')

INSTAGRAM_CLIENT_ID = os.getenv('INSTAGRAM_CLIENT_ID')
INSTAGRAM_CLIENT_SECRET = os.getenv('INSTAGRAM_CLIENT_SECRET')

YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')

FACEBOOK_CLIENT_ID = os.getenv('FACEBOOK_CLIENT_ID')
FACEBOOK_CLIENT_SECRET = os.getenv('FACEBOOK_CLIENT_SECRET')

LINKEDIN_CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
LINKEDIN_CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET')

TWITTER_CLIENT_ID = os.getenv('TWITTER_CLIENT_ID')
TWITTER_CLIENT_SECRET = os.getenv('TWITTER_CLIENT_SECRET')
