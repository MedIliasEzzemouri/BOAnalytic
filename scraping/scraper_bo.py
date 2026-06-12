"""
LegalEye - Scraping Automatique des Bulletins Officiels (V3 - Docker ready)
============================================================================
Telecharge les bulletins officiels (annonces legales/judiciaires)
depuis sgg.gov.ma.

Ameliorations V3 :
  - logging au lieu de print (compatible Docker / fluentd / journald)
  - retry HTTP automatique avec backoff (urllib3 Retry)
  - except specifiques (plus de bare except)
  - APScheduler au lieu de schedule (arret propre du conteneur)
  - chemins via variables d'environnement (UPLOAD_DIR, STATE_FILE)
  - file locking sur le state JSON (portalocker)
  - User-Agent identifie pour le proprietaire du site
  - alignement des horaires : lundi 06h00 et jeudi 18h00 (cf. rapport)
  - pipeline lance en BackgroundTask (non bloquant)

Pattern URL :
    https://www.sgg.gov.ma/BO/AR/3111/{annee}/BOAL_{numero}.pdf

Usage :
    python scraper_bo.py                   # Telecharge tous les nouveaux
    python scraper_bo.py --dernier 5921    # Specifier le dernier connu
    python scraper_bo.py --range 5918 5925 # Telecharger une plage
    python scraper_bo.py --scheduler       # Mode automatique (APScheduler)

Auteur : Marouan (Plastima - DUT IDIA)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Verrou de fichier - optionnel mais recommande en multi-process
try:
    import portalocker  # pip install portalocker
    _HAS_LOCK = True
except ImportError:
    _HAS_LOCK = False


# ============================================================
#  LOGGING
# ============================================================

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scraper_bo")


# ============================================================
#  CONFIGURATION (via variables d'environnement)
# ============================================================

# Deux formats connus du site sgg.gov.ma
# Ancien (bulletins ~5000-6000) : BOAL_{numero}.pdf
# Nouveau (bulletins ~7000+)    : BO_{numero}_Ar.pdf
URL_PATTERNS = [
    ("https://www.sgg.gov.ma/BO/AR/3111/{annee}/BOAL_{numero}.pdf", "BOAL_{numero}.pdf"),
    ("https://www.sgg.gov.ma/BO/AR/3111/{annee}/BO_{numero}_Ar.pdf", "BO_{numero}_Ar.pdf"),
]

# Chemins - configurables via variables d'environnement (utile en Docker)
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", _DEFAULT_ROOT / "backend" / "uploads"))
STATE_FILE = Path(os.environ.get("STATE_FILE", _DEFAULT_ROOT / "scraping" / "scraper_state.json"))

# Identification du bot - bonne pratique
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "contact@plastima.ma")
HEADERS = {
    "User-Agent": f"LegalEye-Plastima/1.0 (+{CONTACT_EMAIL})",
    "Accept": "application/pdf",
    "Referer": "https://www.sgg.gov.ma/arabe/BulletinOfficiel.aspx",
}

# Limites
MAX_ESSAIS_VIDES = int(os.environ.get("MAX_ESSAIS_VIDES", "10"))
DELAI_ENTRE_REQUETES = float(os.environ.get("DELAI_ENTRE_REQUETES", "1.0"))
TIMEOUT_HEAD = 10
TIMEOUT_GET = 120
TAILLE_PDF_MIN = 5000  # octets


# ============================================================
#  SESSION HTTP AVEC RETRY AUTOMATIQUE
# ============================================================

def _build_session() -> requests.Session:
    """Cree une session requests avec retry automatique sur erreurs reseau."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,  # attend 2s, 4s, 8s entre les essais
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s


_session = _build_session()


# ============================================================
#  ETAT PERSISTANT (avec verrou)
# ============================================================

def _open_locked(path: Path, mode: str):
    """Ouvre le fichier d'etat avec un verrou si portalocker est dispo."""
    f = open(path, mode, encoding="utf-8")
    if _HAS_LOCK:
        portalocker.lock(f, portalocker.LOCK_EX)
    return f


def charger_etat() -> dict:
    """Charge le dernier numero telecharge depuis le fichier d'etat."""
    if not STATE_FILE.exists():
        return {"dernier_numero": 0, "derniere_verification": None}
    try:
        with _open_locked(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Etat illisible (%s), reinitialisation", e)
        return {"dernier_numero": 0, "derniere_verification": None}


def sauvegarder_etat(dernier_numero: int) -> None:
    """Sauvegarde le dernier numero telecharge."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    etat = {
        "dernier_numero": int(dernier_numero),
        "derniere_verification": datetime.now().isoformat(),
    }
    with _open_locked(STATE_FILE, "w") as f:
        json.dump(etat, f, indent=2)


# ============================================================
#  TELECHARGEMENT
# ============================================================

def _tester_pattern(url_tpl: str, filename_tpl: str, numero: int, annee: int) -> Optional[tuple[str, str]]:
    """Teste un pattern URL. Retourne (url, filename) si existe, sinon None."""
    url = url_tpl.format(annee=annee, numero=numero)
    filename = filename_tpl.format(numero=numero)
    try:
        r = _session.head(url, timeout=TIMEOUT_HEAD, allow_redirects=True)
        if r.status_code == 200:
            return url, filename
    except requests.RequestException as e:
        log.debug("HEAD %s : %s", url, e)
    return None


def trouver_url_bulletin(numero: int, annee: Optional[int] = None) -> Optional[tuple[str, str, int]]:
    """
    Cherche l'URL valide pour un bulletin en testant les deux patterns
    sur l'annee courante +/-1.

    Returns:
        (url, filename, annee) ou None si introuvable.
    """
    annee_actuelle = datetime.now().year
    annees = [annee] if annee else [annee_actuelle, annee_actuelle - 1, annee_actuelle + 1]

    for an in annees:
        for url_tpl, filename_tpl in URL_PATTERNS:
            result = _tester_pattern(url_tpl, filename_tpl, numero, an)
            if result:
                url, filename = result
                log.debug("Pattern trouve : %s (annee=%d)", filename, an)
                return url, filename, an
    return None


def telecharger_bulletin(
    numero: int,
    dossier: Optional[Path] = None,
    annee: Optional[int] = None,
) -> tuple[Optional[Path], Optional[int]]:
    """
    Telecharge un bulletin PDF en essayant les deux formats d'URL.

    Returns:
        (chemin_fichier, annee) ou (None, None) si echec
    """
    dossier = Path(dossier) if dossier else UPLOAD_DIR
    dossier.mkdir(parents=True, exist_ok=True)

    # Verifier si deja telecharge sous l'un ou l'autre nom
    for _, filename_tpl in URL_PATTERNS:
        candidate = dossier / filename_tpl.format(numero=numero)
        if candidate.exists() and candidate.stat().st_size > 1000:
            log.info("[skip] %s deja telecharge", candidate.name)
            return candidate, annee

    # Trouver l'URL valide
    found = trouver_url_bulletin(numero, annee)
    if found is None:
        log.info("Bulletin %d non trouve sur sgg.gov.ma", numero)
        return None, None

    url, filename, annee_trouvee = found
    filepath = dossier / filename
    log.info("Telechargement %s (annee=%d)...", filename, annee_trouvee)

    try:
        response = _session.get(url, timeout=TIMEOUT_GET, stream=True)
    except requests.exceptions.Timeout:
        log.error("Timeout sur %s", url)
        return None, None
    except requests.exceptions.ConnectionError:
        log.error("Site inaccessible (ConnectionError) sur %s", url)
        return None, None
    except requests.RequestException as e:
        log.error("Erreur HTTP sur %s : %s", url, e)
        return None, None

    if response.status_code != 200:
        log.warning("HTTP %d sur %s", response.status_code, url)
        return None, None

    content = response.content

    if content[:4] != b"%PDF":
        log.warning("Reponse non-PDF pour %s (%d octets)", filename, len(content))
        return None, None
    if len(content) < TAILLE_PDF_MIN:
        log.warning("PDF trop petit (%d octets) pour %s", len(content), filename)
        return None, None

    filepath.write_bytes(content)
    taille_mo = len(content) / (1024 * 1024)
    log.info("OK %s (%.2f Mo)", filename, taille_mo)
    return filepath, annee_trouvee


# ============================================================
#  RECHERCHE DES NOUVEAUX BULLETINS
# ============================================================

def telecharger_nouveaux(
    dernier_connu: int,
    dossier: Optional[Path] = None,
) -> list[dict]:
    """
    Telecharge TOUS les bulletins depuis le dernier connu.
    Gere le rattrapage apres une pause de publication.
    """
    log.info("Recherche des nouveaux bulletins depuis #%d", dernier_connu)

    telecharges: list[dict] = []
    essais_vides = 0
    numero = dernier_connu + 1
    derniere_annee: Optional[int] = None

    while essais_vides < MAX_ESSAIS_VIDES:
        result, annee = telecharger_bulletin(numero, dossier, derniere_annee)

        if result:
            telecharges.append({"numero": numero, "fichier": str(result), "annee": annee})
            essais_vides = 0
            derniere_annee = annee
            sauvegarder_etat(numero)
        else:
            essais_vides += 1

        numero += 1
        time.sleep(DELAI_ENTRE_REQUETES)

    if telecharges:
        log.info("Bilan : %d nouveau(x) bulletin(s) telecharge(s)", len(telecharges))
        for t in telecharges:
            log.info("  -> BOAL_%d.pdf (%d)", t["numero"], t["annee"])
    else:
        log.info("Aucun nouveau bulletin disponible")

    return telecharges


def telecharger_plage(
    debut: int,
    fin: int,
    dossier: Optional[Path] = None,
) -> list[Path]:
    """Telecharge une plage specifique de bulletins."""
    log.info("Telechargement bulletins %d -> %d", debut, fin)

    telecharges: list[Path] = []
    annee: Optional[int] = None

    for numero in range(debut, fin + 1):
        result, annee_trouvee = telecharger_bulletin(numero, dossier, annee)
        if result:
            telecharges.append(result)
            annee = annee_trouvee
        time.sleep(DELAI_ENTRE_REQUETES)

    log.info("Bilan : %d/%d telecharges", len(telecharges), fin - debut + 1)
    return telecharges


# ============================================================
#  EXTRACTION DE LA DATE DE PUBLICATION DEPUIS LE PDF
# ============================================================

# Dictionnaire des mois francais (BO publie en arabe + francais)
_MOIS_FR = {
    "janvier": 1, "fevrier": 2, "fevrier": 2, "fevrier": 2, "mars": 3,
    "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "fevrier": 2, "fevrier": 2, "decembre": 12, "decembre": 12,
}
_MOIS_FR.update({
    "janvier": 1, "fevrier": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "decembre": 12,
    "fevrier": 2, "fevrier": 2,
})


def extraire_date_publication(pdf_path: Path) -> Optional[date]:
    """
    Extrait la date de publication depuis la premiere page du PDF du BO.

    Le BO marocain affiche la date en francais sur la page de garde, dans
    un format type "20 mars 2025" ou "20/03/2025". On tente plusieurs
    regex sur le texte extrait.

    Returns:
        date ou None si l'extraction echoue.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        log.warning("PyMuPDF non installe - extraction de date impossible")
        return None

    try:
        doc = fitz.open(str(pdf_path))
        if doc.page_count == 0:
            return None
        texte = doc[0].get_text("text") or ""
        # Pour plus de robustesse, on prend aussi la page 2 si la 1 est vide
        if len(texte.strip()) < 100 and doc.page_count > 1:
            texte += "\n" + (doc[1].get_text("text") or "")
        doc.close()
    except Exception as e:
        log.warning("Impossible d'ouvrir le PDF %s : %s", pdf_path, e)
        return None

    # Normalisation (sans accents, lowercase) pour matcher les mois
    texte_norm = (
        texte.lower()
        .replace("é", "e").replace("è", "e").replace("ê", "e")
        .replace("û", "u").replace("ô", "o").replace("â", "a")
    )

    # Format 1 : JJ MOIS AAAA (ex: "20 mars 2025")
    m = re.search(
        r"\b(\d{1,2})\s+("
        r"janvier|fevrier|mars|avril|mai|juin|juillet|aout|"
        r"septembre|octobre|novembre|decembre)"
        r"\s+(\d{4})\b",
        texte_norm,
    )
    if m:
        jour = int(m.group(1))
        mois = _MOIS_FR.get(m.group(2))
        annee = int(m.group(3))
        if mois and 1 <= jour <= 31 and 2020 <= annee <= 2099:
            try:
                return date(annee, mois, jour)
            except ValueError:
                pass

    # Format 2 : JJ/MM/AAAA
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", texte)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # Format 3 : AAAA-MM-JJ
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", texte)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    log.warning("Date de publication introuvable dans %s", pdf_path.name)
    return None


# ============================================================
#  INTEGRATION FASTAPI / BDD
# ============================================================

def scraper_et_inserer(db_session, background_tasks=None):
    """
    Verifie et telecharge les nouveaux bulletins, les insere en BDD,
    et lance le pipeline de traitement.

    Args:
        db_session: session SQLAlchemy
        background_tasks: instance FastAPI BackgroundTasks. Si fourni,
            le pipeline tourne en arriere-plan (non bloquant).
    """
    from models import BulletinOfficiel
    from services.pipeline import traiter_bulletin

    # Source de verite : le fichier d'etat du scraper (suit la numerotation
    # BOAL ~5900). Le max(numero) en BDD est trompeur : un bulletin hors-serie
    # telecharge manuellement (ex. edition generale 7296) ferait scanner la
    # mauvaise plage de numeros pour toujours.
    etat = charger_etat()
    dernier_num = int(etat.get("dernier_numero") or 0)

    if dernier_num == 0:
        # Fallback : plus grand numero NUMERIQUE present en BDD
        nums = [
            int(n[0])
            for n in db_session.query(BulletinOfficiel.numero).all()
            if str(n[0]).isdigit()
        ]
        dernier_num = max(nums) if nums else 0

    if dernier_num == 0:
        log.warning("Aucun dernier numero connu. Specifier avec --dernier")
        return []

    nouveaux = telecharger_nouveaux(dernier_num)

    bulletins_crees = []
    for nouveau in nouveaux:
        # Idempotence : ne pas re-inserer un numero deja en BDD
        # (sinon IntegrityError sur la contrainte unique -> job mort).
        numero_str = str(nouveau["numero"])
        existe = db_session.query(BulletinOfficiel).filter(
            BulletinOfficiel.numero == numero_str
        ).first()
        if existe:
            log.info("Bulletin %s deja en BDD (id=%d) - skip", numero_str, existe.id)
            continue

        # Extraire la date depuis le PDF (premiere page).
        # Fallback : date du jour si l'extraction echoue (la colonne est NOT NULL).
        date_pub = extraire_date_publication(Path(nouveau["fichier"]))
        if date_pub is None:
            date_pub = datetime.now().date()
            log.warning(
                "Date introuvable pour bulletin %s - utilisation de la date du jour (%s) en attendant",
                nouveau["numero"], date_pub,
            )

        bulletin = BulletinOfficiel(
            numero=str(nouveau["numero"]),
            date_publication=date_pub,
            fichier_pdf=nouveau["fichier"],
            source="scraping",
            statut="en_attente",
        )
        db_session.add(bulletin)
        db_session.commit()
        db_session.refresh(bulletin)

        log.info("Bulletin %s insere en BDD (id=%d)", nouveau["numero"], bulletin.id)
        bulletins_crees.append(bulletin)

        # Lancer le pipeline - en background si possible
        if background_tasks is not None:
            background_tasks.add_task(traiter_bulletin, bulletin.id, db_session)
            log.info("Pipeline planifie en background pour bulletin %s", nouveau["numero"])
        else:
            try:
                traiter_bulletin(bulletin.id, db_session)
                log.info("Pipeline termine pour bulletin %s", nouveau["numero"])
            except Exception as e:
                log.exception("Erreur pipeline pour bulletin %s : %s", nouveau["numero"], e)

    return bulletins_crees


# ============================================================
#  SCHEDULER (APScheduler - arret propre en Docker)
# ============================================================

def lancer_scheduler() -> None:
    """
    Vérifie chaque semaine si de nouveaux bulletins sont disponibles.
    Horaires alignés avec le rapport : lundi 06h00 et jeudi 18h00.
    """
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        log.error("Le mode scheduler requiert APScheduler : pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone=os.environ.get("TZ", "Africa/Casablanca"))

    def job() -> None:
        log.info("=== Verification programmee ===")
        etat = charger_etat()
        try:
            telecharger_nouveaux(etat["dernier_numero"])
        except Exception:
            log.exception("Erreur pendant le job de scraping")

    scheduler.add_job(job, "cron", day_of_week="mon", hour=6, minute=0, id="bo_lundi")
    scheduler.add_job(job, "cron", day_of_week="thu", hour=18, minute=0, id="bo_jeudi")

    log.info("Scheduler demarre - prochains jobs : %s",
             [str(j.next_run_time) for j in scheduler.get_jobs()])

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler arrete proprement")


# ============================================================
#  MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="LegalEye - Scraper Bulletin Officiel")
    parser.add_argument("--dernier", type=int, help="Dernier numero connu (ex: 5921)")
    parser.add_argument("--range", nargs=2, type=int, metavar=("DEBUT", "FIN"),
                        help="Telecharger une plage (ex: --range 5918 5922)")
    parser.add_argument("--scheduler", action="store_true",
                        help="Lancer le mode automatique (APScheduler)")
    parser.add_argument("--dir", default=None,
                        help=f"Dossier de destination (defaut: {UPLOAD_DIR})")
    args = parser.parse_args()

    log.info("LegalEye - Scraper Bulletin Officiel V3")
    log.info("Upload dir : %s", UPLOAD_DIR)
    log.info("State file : %s", STATE_FILE)

    dossier = Path(args.dir) if args.dir else None

    if args.scheduler:
        lancer_scheduler()
        return

    if args.range:
        telecharger_plage(args.range[0], args.range[1], dossier)
        return

    etat = charger_etat()
    if args.dernier:
        dernier = args.dernier
        sauvegarder_etat(dernier)
    elif etat["dernier_numero"] > 0:
        dernier = etat["dernier_numero"]
    else:
        log.error("Premier lancement - specifie le dernier numero connu :")
        log.error("    python scraper_bo.py --dernier 5921")
        sys.exit(1)

    log.info("Dernier connu : BOAL_%d", dernier)
    telecharger_nouveaux(dernier, dossier)


if __name__ == "__main__":
    main()
