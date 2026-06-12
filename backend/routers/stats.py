"""
LegalEye — Stats Router (Dashboard)
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from database import get_db
from models import BulletinOfficiel, ArticleEntreprise, ArticleMahakim, Tier, Alerte, User, utcnow
from schemas import StatsResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/api/stats", tags=["Stats"])


@router.get("/", response_model=StatsResponse)
def get_stats(
    jours: Optional[int] = Query(
        None,
        ge=1,
        description="Fenêtre temporelle des KPI en jours (7, 30, 90…). "
        "Absent = depuis le début.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Borne temporelle optionnelle pour les KPI.
    cutoff = utcnow() - timedelta(days=jours) if jours else None

    def borne(query, model):
        """Applique le filtre de période sur created_at si demandé."""
        return query.filter(model.created_at >= cutoff) if cutoff else query

    # Compteurs (bornés à la période si `jours` est fourni)
    total_bulletins = borne(db.query(BulletinOfficiel), BulletinOfficiel).count()
    total_legales = borne(db.query(ArticleEntreprise), ArticleEntreprise).count()
    total_judiciaires = borne(db.query(ArticleMahakim), ArticleMahakim).count()
    # Les partenaires actifs forment un registre : compte global, non borné.
    total_tiers = db.query(Tier).filter(Tier.actif == True).count()
    total_alertes = borne(db.query(Alerte), Alerte).count()
    alertes_nouvelles = (
        borne(db.query(Alerte), Alerte).filter(Alerte.statut == "nouvelle").count()
    )

    # Distribution par type d'annonce (bornée à la période également)
    par_type_rows = (
        borne(
            db.query(ArticleEntreprise.type_annonce, func.count()),
            ArticleEntreprise,
        )
        .group_by(ArticleEntreprise.type_annonce)
        .all()
    )
    par_type = {t or "non_classé": c for t, c in par_type_rows}

    # Alertes par mois (12 derniers mois glissants).
    # Le filtre sur created_at garantit qu'on prend bien les mois RÉCENTS :
    # un simple order_by + limit(12) renverrait les 12 PREMIERS mois de
    # l'historique, pas les derniers.
    cutoff_mois = utcnow() - timedelta(days=365)
    par_mois_rows = (
        db.query(
            extract("year", Alerte.created_at).label("annee"),
            extract("month", Alerte.created_at).label("mois"),
            func.count().label("total"),
        )
        .filter(Alerte.created_at >= cutoff_mois)
        .group_by("annee", "mois")
        .order_by("annee", "mois")
        .all()
    )
    par_mois = [
        {"annee": int(r.annee), "mois": int(r.mois), "total": r.total}
        for r in par_mois_rows
    ]

    return StatsResponse(
        total_bulletins=total_bulletins,
        total_annonces_legales=total_legales,
        total_annonces_judiciaires=total_judiciaires,
        total_tiers=total_tiers,
        total_alertes=total_alertes,
        alertes_nouvelles=alertes_nouvelles,
        par_type=par_type,
        par_mois=par_mois,
    )


@router.get("/alertes-par-priorite")
def alertes_par_priorite(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Alerte.priorite, func.count())
        .group_by(Alerte.priorite)
        .all()
    )
    return {p: c for p, c in rows}


@router.get("/top-tiers")
def top_tiers_alertes(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Les partenaires avec le plus d'alertes."""
    rows = (
        db.query(Tier.nom, func.count(Alerte.id).label("nb_alertes"))
        .join(Alerte, Alerte.tier_id == Tier.id)
        .group_by(Tier.id)
        .order_by(func.count(Alerte.id).desc())
        .limit(limit)
        .all()
    )
    return [{"nom": r.nom, "nb_alertes": r.nb_alertes} for r in rows]
