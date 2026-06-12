"""
LegalEye — Main FastAPI Application
=====================================
Système de Veille Juridique Automatisée
Auteur : Marouan (Plastima - DUT IDIA)
"""

import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, bulletins, tiers, alertes, stats, articles, exports
from services.pipeline import charger_modeles
from config import FRONTEND_URL, ENV

# Rendre le dossier scraping/ importable depuis backend/
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SCRAPING_DIR = os.path.join(_ROOT, "scraping")
if _SCRAPING_DIR not in sys.path:
    sys.path.insert(0, _SCRAPING_DIR)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
)
log = logging.getLogger("legaleye.main")

# ── App ──
app = FastAPI(
    title="LegalEye API",
    description="Système de veille juridique automatisée sur les bulletins officiels marocains",
    version="1.0.0",
)

# ── CORS ──
# En dev on autorise les deux ports usuels (CRA + Vite).
# En prod on n'autorise que FRONTEND_URL.
if ENV == "production":
    allowed_origins = [FRONTEND_URL]
else:
    allowed_origins = list({FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routes ──
app.include_router(auth.router)
app.include_router(bulletins.router)
app.include_router(tiers.router)
app.include_router(alertes.router)
app.include_router(stats.router)
app.include_router(articles.router)
app.include_router(exports.router)


# ── Startup ──
@app.on_event("startup")
def startup():
    log.info("=" * 50)
    log.info("LegalEye API — Démarrage")
    log.info("=" * 50)
    charger_modeles()

    # Démarrage du scheduler de scraping si activé (cf. .env)
    if os.environ.get("SCRAPER_ENABLED", "false").lower() == "true":
        _demarrer_scheduler_scraping()

    log.info("API prête")
    log.info("=" * 50)


def _demarrer_scheduler_scraping():
    """
    Démarre APScheduler en BackgroundScheduler (non bloquant pour FastAPI).
    Deux jobs hebdo : lundi 06h00 et jeudi 18h00.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from scraper_bo import charger_etat, telecharger_nouveaux
    except ImportError as e:
        log.warning("Scheduler non démarré : %s", e)
        return

    scheduler = BackgroundScheduler(timezone=os.environ.get("TZ", "Africa/Casablanca"))

    def job():
        log.info("=== Job de scraping programmé ===")
        try:
            etat = charger_etat()
            telecharger_nouveaux(etat["dernier_numero"])
        except Exception:
            log.exception("Erreur pendant le job de scraping")

    scheduler.add_job(job, "cron", day_of_week="mon", hour=6, minute=0, id="bo_lundi")
    scheduler.add_job(job, "cron", day_of_week="thu", hour=18, minute=0, id="bo_jeudi")
    scheduler.start()

    # Garde la référence sur l'app pour pouvoir l'arrêter au shutdown
    app.state.scraper_scheduler = scheduler
    log.info("Scheduler scraping démarré (lundi 06h00, jeudi 18h00)")


# ── Shutdown ──
@app.on_event("shutdown")
def shutdown():
    sched = getattr(app.state, "scraper_scheduler", None)
    if sched is not None:
        sched.shutdown(wait=False)
        log.info("Scheduler scraping arrêté proprement")


# ── Health check ──
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "LegalEye"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
