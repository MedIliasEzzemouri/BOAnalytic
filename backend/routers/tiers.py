"""
LegalEye — Tiers Router (CRUD Partenaires)
"""

import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import csv
import io

from database import get_db
from models import Tier, User
from schemas import TierCreate, TierResponse, TierUpdate
from routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/tiers", tags=["Tiers"])

FORMES_JUR = re.compile(
    r"\b(?:SARL[\s\-]*AU|SARLAU|SARL|S\.?A\.?R\.?L\.?|SA|SNC|SAS|SCS)\b"
    r"|ش\.?\s*م\.?\s*م|ش\.?\s*ذ\.?\s*م\.?\s*م|شركة",
    re.IGNORECASE,
)

def normaliser(nom: str) -> str:
    nom = FORMES_JUR.sub(" ", nom)
    nom = re.sub(r"['\"\-\.,:;/\\()&\[\]{}«»]", " ", nom)
    return re.sub(r"\s+", " ", nom).strip().upper()


# ── LISTER ──
@router.get("/", response_model=List[TierResponse])
def lister_tiers(
    type_tier: Optional[str] = None,
    actif: Optional[bool] = True,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Tier)
    if type_tier:
        query = query.filter(Tier.type_tier == type_tier)
    if actif is not None:
        query = query.filter(Tier.actif == actif)
    if search:
        query = query.filter(Tier.nom.ilike(f"%{search}%"))
    return query.order_by(Tier.nom).all()


# ── CRÉER (admin) ──
@router.post("/", response_model=TierResponse)
def creer_tier(
    data: TierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    tier = Tier(
        nom=data.nom,
        nom_normalise=normaliser(data.nom),
        type_tier=data.type_tier,
        secteur=data.secteur,
        ville=data.ville,
        rc_numero=data.rc_numero,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)
    return tier


# ── IMPORT CSV (admin) ──
@router.post("/import-csv")
def importer_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Importe une liste de partenaires depuis un CSV.
    Colonnes attendues : nom, type_tier (client/fournisseur), secteur, ville
    """
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    count = 0
    for row in reader:
        nom = row.get("nom", "").strip()
        if not nom:
            continue

        tier = Tier(
            nom=nom,
            nom_normalise=normaliser(nom),
            type_tier=row.get("type_tier", "client").strip(),
            secteur=row.get("secteur", "").strip() or None,
            ville=row.get("ville", "").strip() or None,
            rc_numero=row.get("rc_numero", "").strip() or None,
        )
        db.add(tier)
        count += 1

    db.commit()
    return {"message": f"{count} partenaires importés"}


# ── DÉTAIL ──
@router.get("/{tier_id}", response_model=TierResponse)
def detail_tier(
    tier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tier = db.query(Tier).get(tier_id)
    if not tier:
        raise HTTPException(status_code=404, detail="Tier non trouvé")
    return tier


# ── MODIFIER (admin) ──
@router.put("/{tier_id}", response_model=TierResponse)
def modifier_tier(
    tier_id: int,
    data: TierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    tier = db.query(Tier).get(tier_id)
    if not tier:
        raise HTTPException(status_code=404, detail="Tier non trouvé")

    if data.nom is not None:
        tier.nom = data.nom
        tier.nom_normalise = normaliser(data.nom)
    if data.type_tier is not None:
        tier.type_tier = data.type_tier
    if data.secteur is not None:
        tier.secteur = data.secteur
    if data.ville is not None:
        tier.ville = data.ville
    if data.rc_numero is not None:
        tier.rc_numero = data.rc_numero
    if data.actif is not None:
        tier.actif = data.actif

    db.commit()
    db.refresh(tier)
    return tier


# ── SUPPRIMER (admin) ──
@router.delete("/{tier_id}")
def supprimer_tier(
    tier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    tier = db.query(Tier).get(tier_id)
    if not tier:
        raise HTTPException(status_code=404, detail="Tier non trouvé")
    db.delete(tier)
    db.commit()
    return {"message": f"Tier '{tier.nom}' supprimé"}
