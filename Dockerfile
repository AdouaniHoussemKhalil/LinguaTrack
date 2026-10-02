# Image de production de l'API LinguaTrack (FastAPI). En local : docker-compose up --build.
FROM python:3.11-slim

# Pas de .pyc, logs immédiats (pas de tampon), pip sans cache ni vérification de version.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que requirements.txt ne change pas.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Utilisateur sans privilèges ; /app lui appartient (base SQLite par défaut sans DATABASE_URL).
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000

# Sonde de santé sans curl (absent de l'image slim) : la route est /health/ (avec la barre finale).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health/' % os.environ.get('PORT', '8000'), timeout=4)"

# Port fourni par l'hébergeur (PORT), 8000 par défaut. --proxy-headers : derrière le proxy de Render,
# l'application voit le schéma https et l'IP du client.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
