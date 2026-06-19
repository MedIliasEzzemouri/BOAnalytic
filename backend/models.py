"""
LegalEye — Modèles SQLAlchemy (6 tables)
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    Date, DateTime, Enum, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from database import Base


def utcnow() -> datetime:
    """UTC naïf (les colonnes DATETIME MySQL stockent sans timezone).
    Remplace datetime.utcnow(), déprécié depuis Python 3.12."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "user"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nom           = Column(String(100), nullable=False)
    email         = Column(String(150), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(50), nullable=False, default="operateur")
    actif         = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, nullable=False, default=utcnow)
    updated_at    = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    bulletins = relationship("BulletinOfficiel", back_populates="uploader")


class BulletinOfficiel(Base):
    __tablename__ = "bulletin_officiel"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    numero                  = Column(String(20), nullable=False, unique=True)
    date_publication        = Column(Date, nullable=False)
    fichier_pdf             = Column(String(500), nullable=False)
    nb_pages                = Column(Integer, default=0)
    nb_annonces_legales     = Column(Integer, default=0)
    nb_annonces_judiciaires = Column(Integer, default=0)
    source                  = Column(Enum("scraping", "manuel"), nullable=False, default="manuel")
    statut                  = Column(Enum("en_attente", "en_cours", "traite", "erreur"), nullable=False, default="en_attente")
    message_erreur          = Column(Text, default=None)
    uploaded_by             = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), default=None)
    created_at              = Column(DateTime, nullable=False, default=utcnow)
    updated_at              = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    uploader            = relationship("User", back_populates="bulletins")
    articles_entreprise = relationship("ArticleEntreprise", back_populates="bulletin", cascade="all, delete-orphan")
    articles_mahakim    = relationship("ArticleMahakim", back_populates="bulletin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_bulletin_statut", "statut"),
        Index("idx_bulletin_date_pub", "date_publication"),
    )


class ArticleEntreprise(Base):
    __tablename__ = "article_entreprise"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    bulletin_id          = Column(Integer, ForeignKey("bulletin_officiel.id", ondelete="CASCADE"), nullable=False)
    nom_entreprise       = Column(String(300), default=None)
    texte_annonce        = Column(Text, nullable=False)
    type_annonce         = Column(Enum("creation", "modification", "cession", "liquidation"), default=None)
    score_classification = Column(Float, default=None)
    score_ner            = Column(Float, default=None)
    source_nom           = Column(Enum("ner", "sommaire", "regex"), default=None)
    page_bulletin        = Column(Integer, default=None)
    created_at           = Column(DateTime, nullable=False, default=utcnow)

    bulletin = relationship("BulletinOfficiel", back_populates="articles_entreprise")
    alertes  = relationship("Alerte", back_populates="article_entreprise", cascade="all, delete-orphan")


class ArticleMahakim(Base):
    __tablename__ = "article_mahakim"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    bulletin_id     = Column(Integer, ForeignKey("bulletin_officiel.id", ondelete="CASCADE"), nullable=False)
    nom_entreprise  = Column(String(300), default=None)
    texte_annonce   = Column(Text, nullable=False)
    type_procedure  = Column(String(100), default=None)
    score_ner       = Column(Float, default=None)
    tribunal        = Column(String(200), default=None)
    page_bulletin   = Column(Integer, default=None)
    created_at      = Column(DateTime, nullable=False, default=utcnow)

    bulletin = relationship("BulletinOfficiel", back_populates="articles_mahakim")
    alertes  = relationship("Alerte", back_populates="article_mahakim", cascade="all, delete-orphan")


class Tier(Base):
    __tablename__ = "tier"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    nom            = Column(String(300), nullable=False)
    nom_normalise  = Column(String(300), nullable=False)
    type_tier      = Column(String(50), nullable=False)
    secteur        = Column(String(100), default=None)
    ville          = Column(String(100), default=None)
    rc_numero      = Column(String(50), default=None)
    actif          = Column(Boolean, nullable=False, default=True)
    created_at     = Column(DateTime, nullable=False, default=utcnow)
    updated_at     = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    alertes = relationship("Alerte", back_populates="tier", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tier_actif", "actif"),
        Index("idx_tier_type", "type_tier"),
    )


class Alerte(Base):
    __tablename__ = "alerte"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    tier_id               = Column(Integer, ForeignKey("tier.id", ondelete="CASCADE"), nullable=False)
    article_entreprise_id = Column(Integer, ForeignKey("article_entreprise.id", ondelete="CASCADE"), default=None)
    article_mahakim_id    = Column(Integer, ForeignKey("article_mahakim.id", ondelete="CASCADE"), default=None)
    nom_detecte           = Column(String(300), nullable=False)
    nom_tier              = Column(String(300), nullable=False)
    score_similarite      = Column(Float, nullable=False)
    type_annonce          = Column(String(50), default=None)
    statut                = Column(Enum("nouvelle", "vue", "traitee", "ignoree"), nullable=False, default="nouvelle")
    priorite              = Column(Enum("haute", "moyenne", "basse"), nullable=False, default="moyenne")
    commentaire           = Column(Text, default=None)
    created_at            = Column(DateTime, nullable=False, default=utcnow)
    traitee_at            = Column(DateTime, default=None)
    traitee_par           = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), default=None)

    tier               = relationship("Tier", back_populates="alertes")
    article_entreprise = relationship("ArticleEntreprise", back_populates="alertes")
    article_mahakim    = relationship("ArticleMahakim", back_populates="alertes")

    __table_args__ = (
        Index("idx_alerte_statut", "statut"),
        Index("idx_alerte_priorite", "priorite"),
        Index("idx_alerte_tier", "tier_id"),
        Index("idx_alerte_created", "created_at"),
    )
