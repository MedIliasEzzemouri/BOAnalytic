"""
LegalEye — Routes articles : screenshot PDF avec surlignage.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from models import ArticleEntreprise, ArticleMahakim, BulletinOfficiel, User
from routers.auth import get_current_user
from services.screenshot import generer_screenshot

router = APIRouter(prefix="/api/articles", tags=["Articles"])


@router.get("/entreprise/{article_id}/screenshot")
def screenshot_entreprise(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Renvoie un PNG de la page du BO où se trouve cette annonce,
    avec un rectangle rouge autour de l'annonce.
    """
    article = db.query(ArticleEntreprise).get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    bulletin = db.query(BulletinOfficiel).get(article.bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")

    png = generer_screenshot(
        pdf_path=bulletin.fichier_pdf,
        bulletin_id=bulletin.id,
        article_type="entreprise",
        article_id=article.id,
        nom_entreprise=article.nom_entreprise,
        texte_annonce=article.texte_annonce,
        page_bulletin=article.page_bulletin,
    )
    if png is None:
        raise HTTPException(
            status_code=404,
            detail="Annonce introuvable dans le PDF",
        )

    return Response(content=png, media_type="image/png")


@router.get("/mahakim/{article_id}/screenshot")
def screenshot_mahakim(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Idem pour les annonces judiciaires (Section II)."""
    article = db.query(ArticleMahakim).get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    bulletin = db.query(BulletinOfficiel).get(article.bulletin_id)
    if not bulletin:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")

    png = generer_screenshot(
        pdf_path=bulletin.fichier_pdf,
        bulletin_id=bulletin.id,
        article_type="mahakim",
        article_id=article.id,
        nom_entreprise=article.nom_entreprise,
        texte_annonce=article.texte_annonce,
        page_bulletin=article.page_bulletin,
    )
    if png is None:
        raise HTTPException(
            status_code=404,
            detail="Annonce introuvable dans le PDF",
        )

    return Response(content=png, media_type="image/png")
