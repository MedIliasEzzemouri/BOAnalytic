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
SECRET_KEY = os.getenv("SECRET_KEY", "legaleye_secret_key_change_me")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))  # 24h

# ── Environnement ──
ENV = os.getenv("ENV", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ── Chemins ──
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# Les modèles entraînés sont au niveau du projet (../modeles/),
# dans des sous-dossiers par modèle (classification/, ner_camel_v5/, similarite/).
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
MODELES_DIR = os.path.join(ROOT_DIR, "modeles")

# ── Modèles ML ──
CLASSIFICATION_MODEL = os.path.join(MODELES_DIR, "classification", "modele_classification.pkl")
TFIDF_VECTORIZER = os.path.join(MODELES_DIR, "classification", "tfidf_vectorizer.pkl")
NER_MODEL_PATH = os.path.join(MODELES_DIR, "ner_camel_v5")
SIMILARITE_MODEL = os.path.join(MODELES_DIR, "similarite", "similarite_rf.pkl")

# ── Seuils ──
SEUIL_SIMILARITE = float(os.getenv("SEUIL_SIMILARITE", 0.85))

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Avertissement production ──
if ENV == "production" and SECRET_KEY == "legaleye_secret_key_change_me":
    raise RuntimeError(
        "SECRET_KEY non configurée. Définis-la dans backend/.env "
        "avant de lancer en production."
    )
