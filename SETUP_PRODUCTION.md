Setup Produção — klipou

Estrutura
c:\Users\r\codes\
├── klipou/
│   ├── backend/          # Django (venv)
│   ├── web/              # Next.js (pnpm)
│   └── docker-compose.yml

1. Subir Docker (PostgreSQL + RabbitMQ)
cd klipou
docker compose up -d
docker compose ps

2. Backend (venv)
cd klipou/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

3. Instalar Dependências

Ubuntu/WSL:

sudo apt-get update -y
sudo apt-get install -y ffmpeg imagemagick
sudo sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml

4. Instalar Whisper

pip install openai-whisper


Ou Whisper C++ (mais rápido):

pip install whispercpp

5. Migrations
cd klipou/backend
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate

6. Configurar .env

backend/.env:

DATABASE_URL=postgres://klipou:klipou@localhost:5432/klipou

CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=rpc://

FFMPEG_PATH=ffmpeg
FFMPEG_TIMEOUT=600

WHISPER_MODEL=medium
DJANGO_SECRET_KEY=gerar_aqui
DEBUG=false


Gerar SECRET_KEY:

python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

7. Iniciar Serviços
Backend
cd klipou/backend
source venv/bin/activate
python manage.py runserver

Celery Worker
cd klipou/backend
source venv/bin/activate
celery -A core worker -l info

Frontend
cd klipou/web
pnpm install
pnpm dev

Fluxo Final (sem FunClip)

1. Upload do vídeo → Django
2. Celery worker:

Extrai áudio com FFmpeg

Roda Whisper para gerar .srt

Lê timestamps

Corta os vídeos com FFmpeg
3. Salva tudo no banco
4. Front recebe progresso via SSE/WebSockets