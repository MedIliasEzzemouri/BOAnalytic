"""
LegalEye — Configuration
Charge automatiquement les variables depuis backend/.env (voir .env.example).
"""

import os
from dotenv import load_dotenv

# Charge le fichier .env situé à côté de config.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ── Base de données ──
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "bo_watch")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── JWT ──
# Valeur de dev uniquement (>=32 octets pour HS256). En production,
# config.py refuse de démarrer si cette valeur n'a pas été remplacée.
SECRET_KEY = os.getenv("SECRET_KEY", "legaleye_dev_secret_key_change_me_in_production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))  # 24h

# ── Environnement ──
ENV = os.getenv("ENV", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Inscription publique (/api/auth/register). Désactivée par défaut :
# les données (alertes, partenaires) sont internes à l'entreprise.
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"

# ── Chemins ──
# Surclassables par variables d'environnement (utilisées par docker-compose).
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))

# Les modèles entraînés sont au niveau du projet (../modeles/),
# dans des sous-dossiers par modèle (classification/, ner_camel_v5/, similarite/).
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
MODELES_DIR = os.getenv("MODELS_DIR", os.path.join(ROOT_DIR, "modeles"))
CACHE_DIR = os.getenv("CACHE_DIR", os.path.join(BASE_DIR, "cache"))

# ── Modèles ML ──
CLASSIFICATION_MODEL = os.path.join(MODELES_DIR, "classification", "modele_classification.pkl")
TFIDF_VECTORIZER = os.path.join(MODELES_DIR, "classification", "tfidf_vectorizer.pkl")
NER_MODEL_PATH = os.path.join(MODELES_DIR, "ner_camel_v5")
SIMILARITE_MODEL = os.path.join(MODELES_DIR, "similarite", "similarite_rf.pkl")

# ── Seuils ──
SEUIL_SIMILARITE = float(os.getenv("SEUIL_SIMILARITE", 0.85))

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Avertissement production ──
if ENV == "production" and SECRET_KEY == "legaleye_dev_secret_key_change_me_in_production":
    raise RuntimeError(
        "SECRET_KEY non configurée. Définis-la dans backend/.env "
        "avant de lancer en production."
    )
