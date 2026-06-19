"""
LegalEye — Alertes Router
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Alerte, ArticleEntreprise, ArticleMahakim, Tier, User, utcnow
from schemas import AlerteResponse, AlerteUpdate
from routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/alertes", tags=["Alertes"])


# ── LISTER ──
@router.get("/", response_model=List[AlerteResponse])
def lister_alertes(
    statut: Optional[str] = None,
    priorite: Optional[str] = None,
    tier_id: Optional[int] = None,
    bulletin_id: Optional[int] = None,
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Alerte).options(
        joinedload(Alerte.tier),
        joinedload(Alerte.article_entreprise),
        joinedload(Alerte.article_mahakim),
    ).order_by(Alerte.created_at.desc())

    if statut:
        query = query.filter(Alerte.statut == statut)
    if priorite:
        query = query.filter(Alerte.priorite == priorite)
    if tier_id:
        query = query.filter(Alerte.tier_id == tier_id)
    if bulletin_id:
        from sqlalchemy import or_
        ae_ids = db.query(ArticleEntreprise.id).filter(ArticleEntreprise.bulletin_id == bulletin_id).subquery()
        am_ids = db.query(ArticleMahakim.id).filter(ArticleMahakim.bulletin_id == bulletin_id).subquery()
        query = query.filter(
            or_(
                Alerte.article_entreprise_id.in_(ae_ids),
                Alerte.article_mahakim_id.in_(am_ids),
            )
        )

    return query.offset(offset).limit(limit).all()


# ── COMPTEUR (badge dashboard) ──
@router.get("/count/nouvelles")
def compter_nouvelles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(Alerte).filter(Alerte.statut == "nouvelle").count()
    return {"count": count}


# ── DÉTAIL ──
@router.get("/{alerte_id}", response_model=AlerteResponse)
def detail_alerte(
    alerte_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alerte = db.get(
        Alerte,
        alerte_id,
        options=[
            joinedload(Alerte.tier),
            joinedload(Alerte.article_entreprise),
            joinedload(Alerte.article_mahakim),
        ],
    )

    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    return alerte


# ── METTRE À JOUR (traiter/ignorer) ──
@router.put("/{alerte_id}", response_model=AlerteResponse)
def modifier_alerte(
    alerte_id: int,
    data: AlerteUpdate,
    db: Session = Depends(get_db),
    # Traiter une alerte (statut + commentaire) est ouvert à tous les rôles
    # connectés : admin, responsable et operateur.
    current_user: User = Depends(get_current_user),
):
    alerte = db.get(Alerte, alerte_id)
    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")

    if data.statut:
        alerte.statut = data.statut
        if data.statut in ("traitee", "ignoree"):
            alerte.traitee_at = utcnow()
            alerte.traitee_par = current_user.id
    if data.commentaire is not None:
        alerte.commentaire = data.commentaire

    db.commit()
    db.refresh(alerte)
    return alerte


# ── MARQUER COMME VUE ──
@router.post("/{alerte_id}/vue")
def marquer_vue(
    alerte_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alerte = db.get(Alerte, alerte_id)
    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    if alerte.statut == "nouvelle":
        alerte.statut = "vue"
        db.commit()
    return {"message": "OK"}
