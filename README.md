# BOAnalytic — Système de Veille Juridique Automatisée

> Stage Plastima Casablanca · 6 mois
> Surveillance automatique des bulletins officiels marocains pour détecter les annonces juridiques (faillite, liquidation, cession, modification) concernant les partenaires commerciaux de Plastima.

---

## Vue d'ensemble

LegalEye télécharge chaque semaine le Bulletin Officiel marocain (~759 pages, bilingue arabe/français), extrait les annonces, les classifie via 3 modèles ML, et alerte l'utilisateur si un partenaire de Plastima est concerné.

```
sgg.gov.ma → Scraper → PDF → Pipeline ML → MySQL → Dashboard React
                              (3 modèles)
```

## Stack technique

| Couche | Technologies |
|--------|--------------|
| Backend | FastAPI · SQLAlchemy · MySQL · JWT |
| Frontend | React · TypeScript · Bootstrap 5 |
| ML / NLP | PyMuPDF · scikit-learn · HuggingFace Transformers · CAMeL-BERT · rapidfuzz |
| Scraping | Python (requests · BeautifulSoup) |

## Structure du projet

```
BOAnalytic/
├── README.md                     ← ce fichier
│
├── backend/                      Application FastAPI (API + ORM)
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── requirements.txt
│   ├── routers/                  Endpoints (auth, bulletins, tiers, alertes, stats)
│   ├── schemas/                  Pydantic
│   ├── services/                 Pipeline ML + translation
│   ├── uploads/                  PDFs reçus
│   └── modeles/                  Modèles ML chargés au runtime
│
├── frontend/                     React (à développer)
│
├── ml/                           Code ML — entraînement et scripts
│   ├── extraction/               PyMuPDF — extraction des annonces
│   ├── ner/                      Pipeline NER CAMeL-BERT
│   ├── translation/              Translittération arabe → français
│   └── _legacy/                  Versions antérieures
│
├── modeles/                      Modèles ML entraînés (.pkl, .safetensors)
│   ├── classification/           TF-IDF + SVM
│   ├── ner_camel_v5/             CAMeL-BERT fine-tuned
│   └── similarite/               Random Forest
│
├── scraping/
│   └── scraper_bo.py             Téléchargement automatique sgg.gov.ma
│
├── database/
│   └── bo_watch_mysql.sql        Schéma MySQL (6 tables)
│
├── data/                         Jeux de données (CSV)
├── tests/                        Tests unitaires et d'intégration
│
├── docs/                         Documentation technique
│   ├── 01_architecture.md
│   ├── 02_pipeline_ml.md
│   ├── 03_base_de_donnees.md
│   ├── 04_api_endpoints.md
│   └── 05_installation.md
│
├── rapport/                      Rapport de stage
│   └── plan_rapport.md
│
└── planning/                     Suivi de projet
    ├── roadmap.md
    ├── todo.md
    ├── checklist_soutenance.md
    └── journal_de_bord.md
```

## Démarrage rapide

```bash
# 1. Installer les dépendances backend
cd backend
pip install -r requirements.txt

# 2. Créer la base de données MySQL
mysql -u root -p < ../database/bo_watch_mysql.sql

# 3. Configurer config.py (DATABASE_URL, SECRET_KEY)

# 4. Lancer l'API
python main.py
# → http://localhost:8000
# → Doc Swagger : http://localhost:8000/docs
```

## Statut des composants

| Composant | Statut | Score |
|-----------|--------|-------|
| Extraction PDF (PyMuPDF) | Terminé | — |
| Modèle 1 — Classification (TF-IDF + LinearSVC) | Terminé | Accuracy 97.12 % · F1 macro 97.11 % · CV 97.14 % ± 0.5 % |
| Modèle 2 — NER (CAMeL-BERT) | Terminé | F1 = 95.8 % |
| Modèle 3 — Similarité (Random Forest v4) | Terminé | Accuracy 98.84 % · F1 CV 97.5 % · adversarial 7/9 |
| Scraper sgg.gov.ma | Terminé | — |
| Backend FastAPI | Terminé (auth + endpoints + tests) | — |
| Frontend React | À démarrer | — |
| Tests unitaires (pytest) | 4 fichiers en place | — |
| Rapport de stage | En cours | — |


## Auteur

**Marouan Rhazlani** — Stagiaire DUT IDIA, Plastima Casablanca
Référence du rapport antérieur : Fouad Anas (bac+5, 4 mois)
