"""
LegalEye — Bulletins Router (Upload + Traitement)
"""

import os
import re
import shutil
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

router = APIRouter(prefix="/api/bulletins", tags=["Bulletins"])


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
    bulletin = db.query(BulletinOfficiel).get(bulletin_id)
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
    # Vérifier doublon
    existing = db.query(BulletinOfficiel).filter(
        BulletinOfficiel.numero == numero
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Bulletin {numero} déjà existant")

    # Sauvegarder le fichier
    filename = f"BO_{numero}_{date_publication}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

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
    except Exception as e:
        print(f"❌ Erreur traitement bulletin {bulletin_id}: {e}")
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
    bulletin = db.query(BulletinOfficiel).get(bulletin_id)
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
    bulletin = db.query(BulletinOfficiel).get(bulletin_id)
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
        import sys
        scraping_dir = str(Path(UPLOAD_DIR).parent.parent / "scraping")
        if scraping_dir not in sys.path:
            sys.path.insert(0, scraping_dir)
        from scraper_bo import telecharger_bulletin, extraire_date_publication
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Module scraper introuvable : {e}")

    filepath, annee = telecharger_bulletin(numero, dossier=Path(UPLOAD_DIR), annee=annee)
    if filepath is None:
        raise HTTPException(status_code=404, detail=f"Bulletin {numero} introuvable sur sgg.gov.ma")

    date_pub = extraire_date_publication(filepath)
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


# ── SYNC UPLOADS (admin) — importe les BOAL_*.pdf non encore en BDD ──
@router.post("/sync-uploads")
def sync_uploads(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Scanne UPLOAD_DIR pour les BOAL_*.pdf absents de la BDD,
    les insère avec statut 'en_attente' et lance le pipeline ML en background.
    """
    upload_path = Path(UPLOAD_DIR)
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail=f"Dossier uploads introuvable : {UPLOAD_DIR}")

    pdfs = sorted(upload_path.glob("BOAL_*.pdf"))
    if not pdfs:
        return {"imported": 0, "skipped": 0, "message": "Aucun fichier BOAL_*.pdf trouvé"}

    imported = []
    skipped = []

    for pdf in pdfs:
        m = re.match(r"BOAL_(\d+)\.pdf$", pdf.name)
        if not m:
            continue
        numero = m.group(1)

        existing = db.query(BulletinOfficiel).filter(BulletinOfficiel.numero == numero).first()
        if existing:
            skipped.append(numero)
            continue

        # Extraire la date depuis le PDF
        try:
            import sys
            scraping_dir = str(Path(UPLOAD_DIR).parent.parent / "scraping")
            if scraping_dir not in sys.path:
                sys.path.insert(0, scraping_dir)
            from scraper_bo import extraire_date_publication
            date_pub = extraire_date_publication(pdf)
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
    bulletin = db.query(BulletinOfficiel).get(bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin non trouvé")

    # Supprimer le fichier PDF
    if bulletin.fichier_pdf and os.path.exists(bulletin.fichier_pdf):
        os.remove(bulletin.fichier_pdf)

    db.delete(bulletin)
    db.commit()
    return {"message": f"Bulletin {bulletin.numero} supprimé"}
