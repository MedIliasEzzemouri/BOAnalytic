"""
LegalEye — Pipeline Service (orchestrateur)
============================================
Ce fichier ne contient AUCUNE logique métier propre.
Il ne fait qu'appeler les modules de ml/ :

    Extraction  ← ml/extraction/extraction_pdf.py
    Translation ← ml/translation/translation.py
    Similarité  ← ml/similarite/similarite.py
    NER + Classif → restent ici (couplés aux modèles .pkl du backend)

Pipeline :
    PDF → extraction → [Section I + Section II]
        → classification (Section I)
        → NER (les deux)
        → traduction (si arabe)
        → similarité (RF) avec partenaires Plastima
        → création alertes
"""

import logging
import os
import re
import sys
import pickle
from typing import List, Optional
from sqlalchemy.orm import Session

log = logging.getLogger("legaleye.pipeline")

# ──────────────────────────────────────────────────────────────
#  Rendre les modules ml/ importables depuis backend/
# ──────────────────────────────────────────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ML_DIR = os.path.join(ROOT_DIR, "ml")
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

# ──────────────────────────────────────────────────────────────
#  Imports modules métier (ml/)
# ──────────────────────────────────────────────────────────────
from extraction.extraction_pdf import extraire_annonces_bo            # noqa: E402
from translation.translation import (                                  # noqa: E402
    preparer_nom_pour_similarite, reset_translator_state,
)
from similarite.similarite import (                                    # noqa: E402
    charger_modele_similarite, comparer,
)

# ──────────────────────────────────────────────────────────────
#  Imports app (backend/)
# ──────────────────────────────────────────────────────────────
from models import (
    BulletinOfficiel, ArticleEntreprise, ArticleMahakim, Tier, Alerte
)
from config import (
    CLASSIFICATION_MODEL, TFIDF_VECTORIZER,
    NER_MODEL_PATH, SIMILARITE_MODEL, SEUIL_SIMILARITE,
)


# ══════════════════════════════════════════════════════════════
#  CHARGEMENT DES MODÈLES (au démarrage)
# ══════════════════════════════════════════════════════════════

_classification_model = None
_tfidf_vectorizer = None
_ner_model = None
_ner_tokenizer = None
_ner_device = None


def charger_modeles():
    """Charge en mémoire les 3 modèles ML (classification, NER, similarité)."""
    global _classification_model, _tfidf_vectorizer
    global _ner_model, _ner_tokenizer, _ner_device

    # ── Modèle 1 : Classification ──
    if os.path.exists(CLASSIFICATION_MODEL):
        with open(CLASSIFICATION_MODEL, "rb") as f:
            _classification_model = pickle.load(f)
        with open(TFIDF_VECTORIZER, "rb") as f:
            _tfidf_vectorizer = pickle.load(f)
        log.info("Modèle 1 (classification) chargé")
    else:
        log.warning("Modèle 1 introuvable : %s", CLASSIFICATION_MODEL)

    # ── Modèle 2 : NER ──
    if os.path.exists(NER_MODEL_PATH):
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForTokenClassification

            _ner_tokenizer = AutoTokenizer.from_pretrained(NER_MODEL_PATH)
            _ner_model = AutoModelForTokenClassification.from_pretrained(NER_MODEL_PATH)

            if torch.cuda.is_available():
                _ner_device = torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                _ner_device = torch.device("mps")
            else:
                _ner_device = torch.device("cpu")

            _ner_model.to(_ner_device)
            _ner_model.eval()
            log.info("Modèle 2 (NER) chargé (device : %s)", _ner_device)
        except ImportError as e:
            log.warning("Modèle 2 non chargé (dépendance manquante : %s)", e)
        except Exception as e:
            log.warning("Modèle 2 erreur de chargement : %s", e)
    else:
        log.warning("Modèle 2 introuvable : %s", NER_MODEL_PATH)

    # ── Modèle 3 : Similarité ──
    if charger_modele_similarite(SIMILARITE_MODEL):
        log.info("Modèle 3 (similarité RF) chargé")
    else:
        log.warning("Modèle 3 introuvable : %s — fallback rapidfuzz", SIMILARITE_MODEL)


# ══════════════════════════════════════════════════════════════
#  ÉTAPE 1 — EXTRACTION (appelle ml/extraction/)
# ══════════════════════════════════════════════════════════════

def extraire_annonces(pdf_path: str) -> dict:
    """Wrapper autour de extraire_annonces_bo() : renvoie sommaire + Sections I/II + nb_pages."""
    # output_path=None : pas de fichier *_annonces.txt à côté du PDF
    # (les annonces vont en BDD, le .txt ne servait à rien en prod).
    sommaire, annonces_I, annonces_II = extraire_annonces_bo(
        pdf_path, output_path=None
    )
    # nb_pages : on lit le PDF rapidement
    try:
        import fitz
        with fitz.open(pdf_path) as doc:
            nb_pages = len(doc)
    except Exception:
        nb_pages = 0

    return {
        "sommaire": sommaire,
        "annonces_I": annonces_I,
        "annonces_II": annonces_II,
        "nb_pages": nb_pages,
    }


# ══════════════════════════════════════════════════════════════
#  ÉTAPE 2 — CLASSIFICATION (Modèle 1, reste ici)
# ══════════════════════════════════════════════════════════════

def classifier(texte: str) -> tuple[Optional[str], Optional[float]]:
    """
    Classifie une annonce en création / modification / cession / liquidation.

    LinearSVC n'a pas predict_proba natif. On reconstruit un score de
    confiance via decision_function() normalisée par softmax pour ne pas
    laisser le champ score_classification vide en base.

    Returns:
        (label, score) ou (None, None) si modèle non chargé.
    """
    if _classification_model is None or _tfidf_vectorizer is None:
        return None, None
    propre = re.sub(r"[0-9٠-٩]+", " ", texte)
    propre = re.sub(r"[^؀-ۿݐ-ݿa-zA-ZÀ-ÿ\s]", " ", propre)
    propre = re.sub(r"\s+", " ", propre).strip()
    X = _tfidf_vectorizer.transform([propre])
    label = _classification_model.predict(X)[0]

    # Score de confiance : softmax sur decision_function
    score = None
    try:
        import numpy as np
        scores = _classification_model.decision_function(X)[0]
        # scores : array de longueur n_classes
        exp = np.exp(scores - np.max(scores))
        proba = exp / exp.sum()
        # Indice de la classe prédite
        classes = list(_classification_model.classes_)
        idx = classes.index(label)
        score = float(proba[idx])
    except Exception:
        pass

    return label, score


# ══════════════════════════════════════════════════════════════
#  ÉTAPE 3 — NER (Modèle 2, reste ici)
# ══════════════════════════════════════════════════════════════

LABELS = ["O", "B-NOM_ENT", "I-NOM_ENT"]
ID2LABEL = {i: l for i, l in enumerate(LABELS)}

FORMES_JUR = re.compile(
    r"\b(?:SARL[\s\-]*AU|SARLAU|SARL|S\.?A\.?R\.?L\.?|SA|SNC|SAS)\b"
    r"|ش\.?\s*م\.?\s*م|ش\.?\s*ذ\.?\s*م\.?\s*م|شركة\s*ذات|شركة",
    re.IGNORECASE,
)


def _fusionner_lignes_latines(texte: str) -> str:
    """Fusionne les lignes latines fragmentées par PyMuPDF."""
    lignes = texte.split("\n")
    result, buffer = [], []
    for ligne in lignes:
        l = ligne.strip()
        if not l:
            if buffer:
                result.append(" ".join(buffer))
                buffer = []
            continue
        nb_latin = len(re.findall(r"[A-Za-z]", l))
        nb_arabe = len(re.findall(r"[؀-ۿ]", l))
        if nb_latin > 0 and nb_latin >= nb_arabe:
            buffer.append(l)
        else:
            if buffer:
                result.append(" ".join(buffer))
                buffer = []
            result.append(l)
    if buffer:
        result.append(" ".join(buffer))
    return "\n".join(result)


def _nettoyer_nom(nom: str) -> Optional[str]:
    """
    Nettoie un nom détecté par le NER :
    - Retire les caractères invisibles (BOM U+FEFF, ZWJ, ZWSP, etc.)
      que PyMuPDF laisse traîner.
    - Retire les formes juridiques (SARL, SA, شركة, ش.م.م, ...).
    - Retire la ponctuation en début/fin.
    - Normalise les espaces.
    """
    if not nom:
        return None
    # Retirer caractères invisibles Unicode :
    # U+FEFF (BOM), U+200B-200F (ZWSP, ZWNJ, ZWJ, LRM, RLM), U+202A-202E (LRE, RLE, etc.)
    clean = re.sub(r"[﻿​‌‍‎‏‪-‮⁠-⁯]", "", nom)
    clean = FORMES_JUR.sub("", clean).strip()
    clean = re.sub(r"^[\s\-:\.«»\"\'\(\)،,]+", "", clean)
    clean = re.sub(r"[\s\-:\.«»\"\'\(\)،,]+$", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean if len(clean) >= 3 else None


def extraire_nom_ner(texte: str) -> Optional[dict]:
    """Extrait le nom d'entreprise via CAMeL-BERT. Renvoie {nom, score} ou None."""
    if _ner_model is None:
        return None

    import torch
    texte = _fusionner_lignes_latines(texte)
    mots = texte.strip().split()
    if not mots:
        return None

    try:
        enc = _ner_tokenizer(
            mots, is_split_into_words=True, return_tensors="pt",
            truncation=True, max_length=512, padding=False,
        )
        inputs = {k: v.to(_ner_device) for k, v in enc.items()}

        with torch.no_grad():
            out = _ner_model(**inputs)
            preds = torch.argmax(out.logits, dim=-1)[0].cpu().tolist()
            probs = torch.softmax(out.logits, dim=-1).max(dim=-1).values[0].cpu().tolist()

        word_ids = enc.word_ids(batch_index=0)
        mot_labels, mot_scores = {}, {}
        for ti, wi in enumerate(word_ids):
            if wi is not None and wi not in mot_labels:
                mot_labels[wi] = ID2LABEL[preds[ti]]
                mot_scores[wi] = probs[ti]

        entites = []
        current, scores = [], []
        for i in range(len(mots)):
            label = mot_labels.get(i, "O")
            score = mot_scores.get(i, 0.0)
            if label == "B-NOM_ENT":
                if current:
                    entites.append({"nom": " ".join(current), "score": sum(scores) / len(scores)})
                current, scores = [mots[i]], [score]
            elif label == "I-NOM_ENT" and current:
                current.append(mots[i])
                scores.append(score)
            else:
                if current:
                    entites.append({"nom": " ".join(current), "score": sum(scores) / len(scores)})
                current, scores = [], []
        if current:
            entites.append({"nom": " ".join(current), "score": sum(scores) / len(scores)})

        for e in entites:
            nom = _nettoyer_nom(e["nom"])
            if nom and e["score"] > 0.3:
                return {"nom": nom, "score": e["score"]}
        return None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
#  EXTRACTION TRIBUNAL ET TYPE DE PROCÉDURE (Section II)
# ══════════════════════════════════════════════════════════════

# Regex tribunal : capture "المحكمة التجارية بـ X" et "المحكمة الابتدائية بـ X"
_REGEX_TRIBUNAL = re.compile(
    r"(?:المحكمة|املحكمة)\s+"
    r"(?:التجارية|االبتدائية|الابتدائية)"
    r"(?:\s+(?:بـ|ب)\s*([؀-ۿ\s]+?))?(?:\s|$|،|\.)",
    re.UNICODE,
)

# Types de procédures judiciaires usuels au Maroc
_PROCEDURES = [
    (re.compile(r"تصفية\s+قضائية"), "tsfiya_qadaiya"),       # liquidation judiciaire
    (re.compile(r"التسوية\s+القضائية"), "taswiya_qadaiya"),   # redressement judiciaire
    (re.compile(r"مسطرة\s+صعوبات\s+المقاولة"), "difficultes"),
    (re.compile(r"إعالن\s+اإلفلاس|إعلان\s+الإفلاس"), "faillite"),
    (re.compile(r"حل\s+و?تصفية"), "dissolution_liquidation"),
    (re.compile(r"تصفية"), "liquidation"),
    (re.compile(r"حجز"), "saisie"),
]


def extraire_tribunal(texte: str) -> Optional[str]:
    """Extrait le tribunal mentionné dans une annonce judiciaire."""
    m = _REGEX_TRIBUNAL.search(texte)
    if not m:
        return None
    tribunal_full = m.group(0).strip()
    return re.sub(r"\s+", " ", tribunal_full)[:200]


def extraire_type_procedure(texte: str) -> Optional[str]:
    """Identifie le type de procédure judiciaire (regex sur mots-clés arabes)."""
    for regex, label in _PROCEDURES:
        if regex.search(texte):
            return label
    return None


# ══════════════════════════════════════════════════════════════
#  PRIORITÉ AUTOMATIQUE DES ALERTES
# ══════════════════════════════════════════════════════════════

def determiner_priorite(type_annonce: Optional[str]) -> str:
    if type_annonce == "liquidation":
        return "haute"
    if type_annonce == "cession":
        return "moyenne"
    return "basse"


# ══════════════════════════════════════════════════════════════
#  PIPELINE COMPLET (orchestration)
# ══════════════════════════════════════════════════════════════

def traiter_bulletin(bulletin_id: int, db: Session):
    """
    Pipeline : Extraction → Classification → NER → Traduction → Similarité → Alerte.
    Met à jour la BDD.
    """
    bulletin = db.get(BulletinOfficiel, bulletin_id)
    if not bulletin:
        return

    try:
        bulletin.statut = "en_cours"
        db.commit()

        # Reset l'état de traduction (cache + circuit breaker) entre bulletins
        reset_translator_state()

        # ─── 1. EXTRACTION (ml/extraction/) ──────────────────
        data = extraire_annonces(bulletin.fichier_pdf)
        bulletin.nb_pages = data["nb_pages"]
        bulletin.nb_annonces_legales = len(data["annonces_I"])
        bulletin.nb_annonces_judiciaires = len(data["annonces_II"])

        # Aucune annonce = très probablement le mauvais type de document
        # (ex. édition GÉNÉRALE du BO — lois et décrets — au lieu de
        # l'édition annonces légales). On le signale au lieu d'afficher
        # un "traité" trompeur avec 0 annonce.
        if not data["annonces_I"] and not data["annonces_II"]:
            bulletin.statut = "erreur"
            bulletin.message_erreur = (
                "Aucune annonce détectée dans ce PDF. Vérifie qu'il s'agit "
                "bien de l'édition « annonces légales » du BO (numérotation "
                "~5900), pas de l'édition générale (lois et décrets)."
            )
            db.commit()
            log.warning("Bulletin %s : 0 annonce extraite — marqué en erreur", bulletin.numero)
            return

        # Charger les tiers une seule fois
        tiers = db.query(Tier).filter(Tier.actif == True).all()

        import time
        BATCH_SIZE = 200          # commit toutes les N annonces
        PROGRESS_EVERY = 50       # progress print toutes les N annonces
        t0 = time.time()
        nb_alertes_total = 0

        # ─── 2. SECTION I (annonces légales) ─────────────────
        total_I = len(data["annonces_I"])
        log.info("Section I : %d annonces à traiter", total_I)
        for i, item in enumerate(data["annonces_I"]):
            # Compat : nouveau format (texte, page) ou ancien (texte seul)
            if isinstance(item, tuple):
                texte, page_bulletin = item
            else:
                texte, page_bulletin = item, None

            type_annonce, score_classification = classifier(texte)

            ner = extraire_nom_ner(texte)
            nom_brut = ner["nom"] if ner else None
            score_ner = ner["score"] if ner else None

            article = ArticleEntreprise(
                bulletin_id=bulletin_id,
                nom_entreprise=nom_brut,
                texte_annonce=texte,
                type_annonce=type_annonce,
                score_classification=score_classification,
                score_ner=score_ner,
                source_nom="ner" if ner else None,
                page_bulletin=page_bulletin,
            )
            db.add(article)
            db.flush()

            if nom_brut and tiers:
                nom_fr = preparer_nom_pour_similarite(nom_brut)
                matchs = comparer(nom_fr, tiers, seuil=SEUIL_SIMILARITE)
                for m in matchs:
                    db.add(Alerte(
                        tier_id=m["tier_id"],
                        article_entreprise_id=article.id,
                        nom_detecte=nom_fr,
                        nom_tier=m["nom_tier"],
                        score_similarite=m["score"],
                        type_annonce=type_annonce,
                        priorite=determiner_priorite(type_annonce),
                    ))
                    nb_alertes_total += 1

            # Progress + commit batch
            if (i + 1) % PROGRESS_EVERY == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total_I - i - 1) / rate if rate > 0 else 0
                log.info("[%d/%d] Section I — %.1f ann/sec — alertes: %d — ETA: %.0fs",
                         i + 1, total_I, rate, nb_alertes_total, eta)
            if (i + 1) % BATCH_SIZE == 0:
                db.commit()

        # Commit après Section I
        db.commit()
        log.info("Section I terminée en %.1fs (%d alertes)", time.time() - t0, nb_alertes_total)

        # ─── 3. SECTION II (annonces judiciaires) ────────────
        total_II = len(data["annonces_II"])
        log.info("Section II : %d annonces à traiter", total_II)
        t1 = time.time()
        for i, item in enumerate(data["annonces_II"]):
            if isinstance(item, tuple):
                texte, page_bulletin = item
            else:
                texte, page_bulletin = item, None

            ner = extraire_nom_ner(texte)
            nom_brut = ner["nom"] if ner else None
            score_ner = ner["score"] if ner else None

            article = ArticleMahakim(
                bulletin_id=bulletin_id,
                nom_entreprise=nom_brut,
                texte_annonce=texte,
                type_procedure=extraire_type_procedure(texte),
                score_ner=score_ner,
                tribunal=extraire_tribunal(texte),
                page_bulletin=page_bulletin,
            )
            db.add(article)
            db.flush()

            if nom_brut and tiers:
                nom_fr = preparer_nom_pour_similarite(nom_brut)
                matchs = comparer(nom_fr, tiers, seuil=SEUIL_SIMILARITE)
                for m in matchs:
                    db.add(Alerte(
                        tier_id=m["tier_id"],
                        article_mahakim_id=article.id,
                        nom_detecte=nom_fr,
                        nom_tier=m["nom_tier"],
                        score_similarite=m["score"],
                        type_annonce="judiciaire",
                        priorite="haute",
                    ))
                    nb_alertes_total += 1

        db.commit()
        log.info("Section II terminée en %.1fs", time.time() - t1)

        # ─── 4. TERMINÉ ──────────────────────────────────────
        bulletin.statut = "traite"
        db.commit()
        total_time = time.time() - t0
        log.info("Pipeline terminé en %.1fs — %d alertes générées",
                 total_time, nb_alertes_total)

    except Exception as e:
        # IMPORTANT : on rollback d'abord pour libérer les verrous MySQL.
        # Sans ça, la session reste dans un état corrompu et l'UPDATE
        # suivant timeout (cas typique : Lock wait timeout exceeded).
        db.rollback()
        try:
            bulletin = db.get(BulletinOfficiel, bulletin_id)
            if bulletin is not None:
                bulletin.statut = "erreur"
                bulletin.message_erreur = str(e)[:500]
                db.commit()
        except Exception:
            log.exception("Impossible de marquer le bulletin %s en erreur", bulletin_id)
            db.rollback()
        raise
