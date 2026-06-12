"""
LegalEye — Bulletins Router (Upload + Traitement)
"""

import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from models import BulletinOfficiel, User
from schemas import BulletinResponse, ArticleEntrepriseResponse, ArticleMahakimResponse
from models import ArticleEntreprise, ArticleMahakim
from services.pipeline import traiter_bulletin
from config import UPLOAD_DIR
from routers.auth import get_current_user, require_admin

log = logging.getLogger("legaleye.bulletins")

router = APIRouter(prefix="/api/bulletins", tags=["Bulletins"])

# Numéro de BO : chiffres uniquement (utilisé dans un nom de fichier —
# tout autre caractère ouvrirait un path traversal).
_NUMERO_RE = re.compile(r"^\d{1,10}$")

# Taille max d'un PDF uploadé (aligné sur client_max_body_size nginx).
MAX_PDF_BYTES = 100 * 1024 * 1024


def _valider_numero(numero: str) -> str:
    numero = numero.strip()
    if not _NUMERO_RE.match(numero):
        raise HTTPException(
            status_code=400,
            detail="Numéro de bulletin invalide (chiffres uniquement)",
        )
    return numero


def _importer_scraper():
    """Import du module scraper_bo (dossier scraping/ hors backend/)."""
    scraping_dir = str(Path(UPLOAD_DIR).parent.parent / "scraping")
    if scraping_dir not in sys.path:
        sys.path.insert(0, scraping_dir)
    import scraper_bo
    return scraper_bo


# ── LISTER LES BULLETINS ──
@router.get("/", response_model=List[BulletinResponse])
def lister_bulletins(
    statut: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(BulletinOfficiel).order_by(BulletinOfficiel.date_publication.desc())
    if statut:
        query = query.filter(BulletinOfficiel.statut == statut)
    return query.offset(offset).limit(limit).all()


# ── DÉTAIL D'UN BULLETIN ──
@router.get("/{bulletin_id}", response_model=BulletinResponse)
def detail_bulletin(
    bulletin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bulletin = db.get(BulletinOfficiel, bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin non trouvé")
    return bulletin


# ── UPLOAD + TRAITEMENT (admin) ──
@router.post("/upload", response_model=BulletinResponse)
def upload_bulletin(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    numero: str = Form(...),
    date_publication: date = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    numero = _valider_numero(numero)

    # Vérifier doublon
    existing = db.query(BulletinOfficiel).filter(
        BulletinOfficiel.numero == numero
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Bulletin {numero} déjà existant")

    # Vérifier que le fichier est bien un PDF (magic bytes, pas l'extension)
    entete = file.file.read(5)
    file.file.seek(0)
    if entete != b"%PDF-":
        raise HTTPException(status_code=400, detail="Le fichier n'est pas un PDF valide")

    # Sauvegarder le fichier (avec plafond de taille)
    filename = f"BO_{numero}_{date_publication}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)

    taille = 0
    with open(filepath, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            taille += len(chunk)
            if taille > MAX_PDF_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(status_code=413, detail="PDF trop volumineux (max 100 Mo)")
            f.write(chunk)

    # Créer l'entrée en BDD
    bulletin = BulletinOfficiel(
        numero=numero,
        date_publication=date_publication,
        fichier_pdf=filepath,
        source="manuel",
        statut="en_attente",
        uploaded_by=current_user.id,
    )
    db.add(bulletin)
    db.commit()
    db.refresh(bulletin)

    # Lancer le traitement en arrière-plan
    background_tasks.add_task(traiter_bulletin_task, bulletin.id)

    return bulletin


def traiter_bulletin_task(bulletin_id: int):
    """Tâche en arrière-plan pour traiter un bulletin."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        traiter_bulletin(bulletin_id, db)
    except Exception:
        log.exception("Erreur traitement bulletin %s", bulletin_id)
    finally:
        db.close()


# ── RELANCER LE TRAITEMENT (admin) ──
@router.post("/{bulletin_id}/retraiter", response_model=BulletinResponse)
def retraiter_bulletin(
    bulletin_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    bulletin = db.get(BulletinOfficiel, bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin non trouvé")

    bulletin.statut = "en_attente"
    bulletin.message_erreur = None
    db.commit()

    background_tasks.add_task(traiter_bulletin_task, bulletin.id)
    return bulletin


# ── ARTICLES D'UN BULLETIN (résultats ML) ──
@router.get("/{bulletin_id}/articles")
def articles_bulletin(
    bulletin_id: int,
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bulletin = db.get(BulletinOfficiel, bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin non trouvé")

    legales = (
        db.query(ArticleEntreprise)
        .filter(ArticleEntreprise.bulletin_id == bulletin_id)
        .order_by(ArticleEntreprise.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    judiciaires = (
        db.query(ArticleMahakim)
        .filter(ArticleMahakim.bulletin_id == bulletin_id)
        .order_by(ArticleMahakim.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "legales": [ArticleEntrepriseResponse.model_validate(a) for a in legales],
        "judiciaires": [ArticleMahakimResponse.model_validate(a) for a in judiciaires],
    }


# ── TÉLÉCHARGER PAR NUMÉRO (admin) — download depuis sgg.gov.ma ──
@router.post("/download-numero")
def download_par_numero(
    background_tasks: BackgroundTasks,
    numero: int = Form(...),
    annee: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Télécharge un bulletin depuis sgg.gov.ma et le traite."""
    str_numero = str(numero)

    existing = db.query(BulletinOfficiel).filter(BulletinOfficiel.numero == str_numero).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Bulletin {numero} déjà en base (statut: {existing.statut})")

    try:
        scraper = _importer_scraper()
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Module scraper introuvable : {e}")

    filepath, annee = scraper.telecharger_bulletin(numero, dossier=Path(UPLOAD_DIR), annee=annee)
    if filepath is None:
        raise HTTPException(status_code=404, detail=f"Bulletin {numero} introuvable sur sgg.gov.ma")

    date_pub = scraper.extraire_date_publication(filepath)
    if date_pub is None:
        date_pub = datetime.now().date()

    bulletin = BulletinOfficiel(
        numero=str_numero,
        date_publication=date_pub,
        fichier_pdf=str(filepath),
        source="scraping",
        statut="en_attente",
    )
    db.add(bulletin)
    db.commit()
    db.refresh(bulletin)

    background_tasks.add_task(traiter_bulletin_task, bulletin.id)
    return bulletin


# ── SCAN NOUVEAUX (admin) — cycle scraper complet à la demande ──
def _scan_nouveaux_task():
    """Télécharge les nouveaux BOAL depuis sgg.gov.ma, insère en BDD,
    lance le pipeline. Même cycle que le job planifié (lundi/jeudi)."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        scraper = _importer_scraper()
        crees = scraper.scraper_et_inserer(db)
        log.info("Scan manuel terminé : %d bulletin(s) importé(s)", len(crees))
    except Exception:
        log.exception("Erreur pendant le scan manuel des nouveaux bulletins")
    finally:
        db.close()


@router.post("/scan-nouveaux")
def scan_nouveaux(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Déclenche immédiatement le cycle complet du scraper :
    téléchargement des nouveaux bulletins (depuis le dernier numéro connu
    du fichier d'état) + insertion BDD + pipeline ML, en arrière-plan.
    """
    try:
        scraper = _importer_scraper()
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Module scraper introuvable : {e}")

    etat = scraper.charger_etat()
    background_tasks.add_task(_scan_nouveaux_task)
    return {
        "message": "Scan lancé en arrière-plan",
        "dernier_numero_connu": etat.get("dernier_numero", 0),
    }


# ── SYNC UPLOADS (admin) — importe les PDF du dossier non encore en BDD ──

# Noms acceptés : BOAL_5921.pdf (scraper) et BO_5907_2026-01-14.pdf (upload manuel)
_SYNC_PDF_RE = re.compile(r"^BO(?:AL)?_(\d+)(?:_\d{4}-\d{2}-\d{2})?\.pdf$", re.IGNORECASE)


@router.post("/sync-uploads")
def sync_uploads(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Scanne UPLOAD_DIR pour les PDF de bulletins (BOAL_*.pdf ou BO_*.pdf)
    absents de la BDD, les insère avec statut 'en_attente' et lance le
    pipeline ML en background.
    """
    upload_path = Path(UPLOAD_DIR)
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail=f"Dossier uploads introuvable : {UPLOAD_DIR}")

    pdfs = sorted(p for p in upload_path.glob("*.pdf") if _SYNC_PDF_RE.match(p.name))
    if not pdfs:
        return {
            "imported": 0,
            "skipped": 0,
            "message": "Aucun PDF de bulletin trouvé (formats acceptés : BOAL_<numéro>.pdf, BO_<numéro>_<date>.pdf)",
        }

    imported = []
    skipped = []

    for pdf in pdfs:
        m = _SYNC_PDF_RE.match(pdf.name)
        numero = m.group(1)

        existing = db.query(BulletinOfficiel).filter(BulletinOfficiel.numero == numero).first()
        if existing:
            skipped.append(numero)
            continue

        # Extraire la date depuis le PDF
        try:
            date_pub = _importer_scraper().extraire_date_publication(pdf)
        except Exception:
            date_pub = None

        if date_pub is None:
            date_pub = datetime.now().date()

        bulletin = BulletinOfficiel(
            numero=numero,
            date_publication=date_pub,
            fichier_pdf=str(pdf.absolute()),
            source="scraping",
            statut="en_attente",
        )
        db.add(bulletin)
        db.commit()
        db.refresh(bulletin)

        background_tasks.add_task(traiter_bulletin_task, bulletin.id)
        imported.append(numero)

    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "bulletins_importes": imported,
        "message": f"{len(imported)} importé(s), {len(skipped)} déjà en BDD",
    }


# ── SUPPRIMER UN BULLETIN (admin) ──
@router.delete("/{bulletin_id}")
def supprimer_bulletin(
    bulletin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    bulletin = db.get(BulletinOfficiel, bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin non trouvé")

    numero = bulletin.numero
    fichier_pdf = bulletin.fichier_pdf

    # Supprimer en BDD d'abord : si le commit échoue, le fichier est intact.
    db.delete(bulletin)
    db.commit()

    if fichier_pdf and os.path.exists(fichier_pdf):
        try:
            os.remove(fichier_pdf)
        except OSError:
            log.warning("PDF orphelin non supprimé : %s", fichier_pdf)

    return {"message": f"Bulletin {numero} supprimé"}
