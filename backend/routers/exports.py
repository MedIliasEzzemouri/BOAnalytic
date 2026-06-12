"""
LegalEye — Endpoints d'export PDF.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routers.auth import get_current_user
from services.export_pdf import generer_rapport_global

log = logging.getLogger("legaleye.exports")

router = APIRouter(prefix="/api/exports", tags=["Exports"])


@router.get("/rapport-global")
def rapport_global(
    jours: int = Query(
        30, ge=1, le=365,
        description="Nombre de jours couverts par le rapport (1 à 365).",
    ),
    titre: str = Query(
        None, description="Titre personnalisé (optionnel).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Génère et renvoie un rapport PDF récapitulatif de l'activité
    LegalEye sur les N derniers jours :

    - Vue d'ensemble (KPIs)
    - Bulletins traités sur la période
    - Performances de traitement (temps moyen, médian)
    - Répartition des alertes par priorité et statut
    - Top partenaires les plus mentionnés
    - Top 50 alertes par score

    Returns : PDF (application/pdf) téléchargeable.
    """
    try:
        pdf_bytes = generer_rapport_global(
            db=db, jours=jours, titre_personnalise=titre,
        )
    except Exception:
        # Détail loggé côté serveur uniquement — pas d'internals dans la réponse.
        log.exception("Erreur lors de la génération du rapport global")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la génération du rapport",
        )

    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="Rapport vide")

    filename = f"LegalEye_rapport_{jours}j_{datetime.now():%Y%m%d_%H%M}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
