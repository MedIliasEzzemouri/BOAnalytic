"""
LegalEye — Main FastAPI Application
=====================================
Système de Veille Juridique Automatisée
Auteur : Marouan (Plastima - DUT IDIA)
"""

import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager

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

# Verrou inter-workers : uvicorn lance N workers qui exécutent chacun ce
# module. Sans verrou, chaque worker démarrerait son propre scheduler de
# scraping (jobs en double, course sur scraper_state.json). Le premier
# worker qui obtient le verrou exclusif démarre le scheduler ; les autres
# passent leur tour. Le handle est gardé ouvert toute la vie du process.
_SCHEDULER_LOCK_PATH = os.path.join(tempfile.gettempdir(), "legaleye_scheduler.lock")
_scheduler_lock_handle = None


def _acquerir_verrou_scheduler() -> bool:
    """Tente de prendre le verrou exclusif. True = ce worker gère le scheduler."""
    global _scheduler_lock_handle
    try:
        import portalocker
        handle = open(_SCHEDULER_LOCK_PATH, "a")
        portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        _scheduler_lock_handle = handle
        return True
    except ImportError:
        log.warning("portalocker absent — scheduler démarré sans verrou inter-workers")
        return True
    except Exception:
        return False


def _demarrer_scheduler_scraping(app: FastAPI):
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

    app.state.scraper_scheduler = scheduler
    log.info("Scheduler scraping démarré (lundi 06h00, jeudi 18h00)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    log.info("=" * 50)
    log.info("LegalEye API — Démarrage")
    log.info("=" * 50)
    charger_modeles()

    if os.environ.get("SCRAPER_ENABLED", "false").lower() == "true":
        if _acquerir_verrou_scheduler():
            _demarrer_scheduler_scraping(app)
        else:
            log.info("Scheduler scraping déjà géré par un autre worker — skip")

    log.info("API prête")
    log.info("=" * 50)

    yield

    # ── Shutdown ──
    sched = getattr(app.state, "scraper_scheduler", None)
    if sched is not None:
        sched.shutdown(wait=False)
        log.info("Scheduler scraping arrêté proprement")
    if _scheduler_lock_handle is not None:
        _scheduler_lock_handle.close()


# ── App ──
app = FastAPI(
    title="LegalEye API",
    description="Système de veille juridique automatisée sur les bulletins officiels marocains",
    version="1.0.0",
    lifespan=lifespan,
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


# ── Health check ──
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "LegalEye"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
