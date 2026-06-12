# ====================================================================
#  Backend FastAPI - Image Docker
#  Image legere basee sur python:3.11-slim.
#  Build : docker build -t legaleye-backend .
# ====================================================================

FROM python:3.11-slim

# Variables d'environnement Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app:/app/ml:/app/scraping

# Dependances systeme minimales
# - default-libmysqlclient-dev : pymysql / mysqlclient
# - build-essential : compilation eventuelle de wheels
# - libgl1 : PyMuPDF / Pillow
# - curl : healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) torch en version CPU-only (evite les 3 Go de dependances NVIDIA CUDA
#    qui sont inutiles sur un environnement sans GPU).
#    On utilise l'index PyPI specifique de PyTorch pour les builds CPU.
RUN pip install --no-cache-dir --default-timeout=300 \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1

# 2) Le reste des dependances (FastAPI, transformers, scikit-learn...)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=300 -r /app/requirements.txt

# Copie du code applicatif
COPY backend/ /app/
COPY ml/ /app/ml/
COPY scraping/ /app/scraping/
# Modeles ML : chemin lu par config.py via la variable MODELS_DIR
# (definie a /app/modeles dans docker-compose.yml)
COPY modeles/ /app/modeles/

# Bulletins officiels de demo (seed) : copies dans /app/uploads/
# Docker va automatiquement les transferer dans le volume "uploads"
# au PREMIER demarrage (le volume est vide). Aux demarrages suivants,
# le volume contient deja les donnees et les ecrasures sont evitees.
COPY seed_uploads/ /app/uploads/

# Etat initial du scraper (numero du dernier BO connu au moment
# de la livraison Plastima). Copie dans /app/state/ qui est un
# volume Docker - meme logique que pour /app/uploads/.
RUN mkdir -p /app/state
COPY scraping/scraper_state.json /app/state/scraper_state.json

# Dossiers persistants montes en volume
RUN mkdir -p /app/uploads /app/cache /app/state /app/storage

# Utilisateur non-root (securite)
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app \
    && chown -R app:app /app
USER app

# Port FastAPI
EXPOSE 8000

# Healthcheck (utilise par docker-compose pour signaler "healthy")
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# Demarrage avec uvicorn (2 workers).
# Le scheduler de scraping est protege par un verrou fichier : un seul
# worker le demarre (cf. main.py).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
