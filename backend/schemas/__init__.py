"""
LegalEye — Schémas Pydantic
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime
from enum import Enum


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    nom: str
    role: str

class RegisterRequest(BaseModel):
    nom: str
    email: str
    password: str
    role: str = "viewer"


# ══════════════════════════════════════════════════════════════
#  BULLETIN
# ══════════════════════════════════════════════════════════════

class BulletinResponse(BaseModel):
    id: int
    numero: str
    date_publication: date
    nb_pages: int
    nb_annonces_legales: int
    nb_annonces_judiciaires: int
    source: str
    statut: str
    message_erreur: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  ARTICLE
# ══════════════════════════════════════════════════════════════

class ArticleEntrepriseResponse(BaseModel):
    id: int
    bulletin_id: int
    nom_entreprise: Optional[str] = None
    texte_annonce: str
    type_annonce: Optional[str] = None
    score_classification: Optional[float] = None
    score_ner: Optional[float] = None
    source_nom: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ArticleMahakimResponse(BaseModel):
    id: int
    bulletin_id: int
    nom_entreprise: Optional[str] = None
    texte_annonce: str
    type_procedure: Optional[str] = None
    score_ner: Optional[float] = None
    tribunal: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
#  TIER (Partenaires)
# ══════════════════════════════════════════════════════════════

class TierCreate(BaseModel):
    nom: str
    type_tier: str  # "client" ou "fournisseur"
    secteur: Optional[str] = None
    ville: Optional[str] = None
    rc_numero: Optional[str] = None

class TierResponse(BaseModel):
    id: int
    nom: str
    nom_normalise: str
    type_tier: str
    secteur: Optional[str] = None
    ville: Optional[str] = None
    rc_numero: Optional[str] = None
    actif: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TierUpdate(BaseModel):
    nom: Optional[str] = None
    type_tier: Optional[str] = None
    secteur: Optional[str] = None
    ville: Optional[str] = None
    rc_numero: Optional[str] = None
    actif: Optional[bool] = None


# ══════════════════════════════════════════════════════════════
#  ALERTE
# ══════════════════════════════════════════════════════════════

class AlerteResponse(BaseModel):
    id: int
    tier_id: int
    nom_detecte: str
    nom_tier: str
    score_similarite: float
    type_annonce: Optional[str] = None
    statut: str
    priorite: str
    commentaire: Optional[str] = None
    created_at: datetime
    traitee_at: Optional[datetime] = None

    # Relations
    article_entreprise: Optional[ArticleEntrepriseResponse] = None
    article_mahakim: Optional[ArticleMahakimResponse] = None
    tier: Optional[TierResponse] = None

    class Config:
        from_attributes = True

class AlerteUpdate(BaseModel):
    statut: Optional[str] = None
    commentaire: Optional[str] = None


# ══════════════════════════════════════════════════════════════
#  STATS
# ══════════════════════════════════════════════════════════════

class StatsResponse(BaseModel):
    total_bulletins: int
    total_annonces_legales: int
    total_annonces_judiciaires: int
    total_tiers: int
    total_alertes: int
    alertes_nouvelles: int
    par_type: dict
    par_mois: list
