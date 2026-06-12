"""
LegalEye — Module Similarité (Modèle 3)
========================================
Charge le Random Forest entraîné et calcule les 7 features
attendues pour comparer un nom détecté avec les partenaires Plastima.

Features (dans l'ordre, important pour le modèle) :
    1. levenshtein_ratio
    2. token_sort_ratio
    3. token_set_ratio
    4. partial_ratio
    5. diff_longueur
    6. jaccard_mots
    7. premier_mot_identique

Usage :
    from similarite import charger_modele_similarite, comparer

    charger_modele_similarite("/chemin/vers/similarite_rf.pkl")
    matchs = comparer("STORABI", liste_tiers, seuil=0.85)
"""

import re
import pickle
from typing import List
from rapidfuzz import fuzz


# ══════════════════════════════════════════════════════════════
#  CHARGEMENT DU MODÈLE
# ══════════════════════════════════════════════════════════════

_rf_model = None


def charger_modele_similarite(model_path: str) -> bool:
    """Charge le Random Forest. Renvoie True si OK, False sinon."""
    global _rf_model
    try:
        with open(model_path, "rb") as f:
            _rf_model = pickle.load(f)
        return True
    except Exception as e:
        print(f"  ⚠️  Modèle similarité non chargé : {e}")
        _rf_model = None
        return False


# ══════════════════════════════════════════════════════════════
#  NORMALISATION
# ══════════════════════════════════════════════════════════════

FORMES_JUR = re.compile(
    r"\b(?:SARL[\s\-]*AU|SARLAU|SARL|S\.?A\.?R\.?L\.?|SA|SNC|SAS|SCS|LLC|"
    r"STE|SOCIETE|SOCIÉTÉ|CIE|COMPAGNIE|GROUPE|GROUP)\b",
    re.IGNORECASE,
)


def normaliser(nom: str) -> str:
    """Normalise un nom : retrait caractères invisibles, formes juridiques,
    ponctuation, mise en majuscules."""
    if not nom:
        return ""
    # Retrait des caractères invisibles (BOM U+FEFF, ZWSP, ZWNJ, ZWJ, marqueurs directionnels)
    nom = re.sub(r"[﻿​‌‍‎‏‪-‮⁠-⁯]", "", nom)
    nom = FORMES_JUR.sub(" ", nom)
    nom = re.sub(r"['\"\-\.,:;/\\()&\[\]{}«»]", " ", nom)
    return re.sub(r"\s+", " ", nom).strip().upper()


# ══════════════════════════════════════════════════════════════
#  CALCUL DES 7 FEATURES
# ══════════════════════════════════════════════════════════════

def calculer_features(nom_a: str, nom_b: str) -> list:
    """
    Calcule les 7 features pour une paire de noms normalisés.
    Renvoie une liste de 7 valeurs (dans l'ordre attendu par le modèle).
    """
    a = normaliser(nom_a)
    b = normaliser(nom_b)

    if not a or not b:
        return [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0]

    mots_a = set(a.split())
    mots_b = set(b.split())
    union = mots_a | mots_b

    return [
        fuzz.ratio(a, b) / 100,                          # 1. levenshtein_ratio
        fuzz.token_sort_ratio(a, b) / 100,               # 2. token_sort_ratio
        fuzz.token_set_ratio(a, b) / 100,                # 3. token_set_ratio
        fuzz.partial_ratio(a, b) / 100,                  # 4. partial_ratio
        abs(len(a) - len(b)) / max(len(a), len(b), 1),   # 5. diff_longueur
        len(mots_a & mots_b) / len(union) if union else 0.0,  # 6. jaccard_mots
        int(a.split()[0] == b.split()[0]) if mots_a and mots_b else 0,  # 7. premier_mot_identique
    ]


# ══════════════════════════════════════════════════════════════
#  COMPARAISON
# ══════════════════════════════════════════════════════════════

def predire_score(nom_a: str, nom_b: str) -> float:
    """
    Prédit le score de similarité avec le Random Forest.
    Si le modèle n'est pas chargé, fallback sur une moyenne pondérée de rapidfuzz.
    """
    features = calculer_features(nom_a, nom_b)

    if _rf_model is not None:
        # Random Forest renvoie une probabilité [P(non_match), P(match)]
        try:
            proba = _rf_model.predict_proba([features])[0]
            return float(proba[1])  # P(match)
        except Exception:
            pass

    # Fallback rapidfuzz (moyenne pondérée)
    lev, ts, tset, _, _, _, _ = features
    return float(lev * 0.3 + ts * 0.3 + tset * 0.4)


# Seuils du pré-filtre.
# Le RF v4 a été entraîné sur paires confusables sélectionnées avec WRatio>=60.
# On adopte donc le MÊME seuil (60) pour rester dans la distribution d'entraînement.
# En dessous, le RF produit des scores haut mais incorrects (faux positifs).
PREFILTER_WRATIO = 60

# Sécurité supplémentaire : on rejette aussi les paires où aucun token n'est
# significativement partagé. Évite les cas type "DESIRS" vs "DES 2 EAUX ET
# TRAVAUX DIVERS" où WRatio est gonflé par le sous-mot "DIVERS" mais token_set
# est faible.
PREFILTER_TOKEN_SET = 40

# Garde-fou supplémentaire : pour les noms très courts (<5 chars), on exige
# un match plus strict pour éviter les faux positifs dus aux abréviations
# du type "EMT", "ADI", "DAS" qui matchent par hasard des sous-chaînes.
MIN_LENGTH_FOR_NORMAL = 5
PREFILTER_WRATIO_SHORT = 80


def comparer(nom_detecte: str, tiers: List, seuil: float = 0.85) -> List[dict]:
    """
    Compare un nom détecté avec la liste des partenaires.

    Optimisations :
    1. **Pré-filtre WRatio** : on rejette d'emblée les paires manifestement
       différentes (WRatio < 40). Le RF n'a pas été entraîné sur ces cas
       et y produit des scores élevés mais incorrects (faux positifs).
       Le WRatio combine 4 ratios rapidfuzz (Levenshtein, token_sort,
       token_set, partial) — c'est l'agrégat le plus robuste pour filtrer
       sans rater de vrais matches.

    2. **Batch predict_proba** : pour les paires survivant au pré-filtre,
       on construit une seule matrice (N_candidats × 7) et on appelle le
       RF UNE SEULE fois. Speedup 50-100× sans perte de qualité.

    Args:
        nom_detecte: nom déjà normalisé / traduit
        tiers: liste d'objets Tier (avec .id, .nom, .nom_normalise)
        seuil: score minimum pour créer une alerte

    Returns:
        liste de matchs triés par score décroissant :
        [{"tier_id": ..., "nom_tier": ..., "score": ...}, ...]
    """
    if not nom_detecte or not tiers:
        return []

    nom_a_norm = normaliser(nom_detecte)
    if not nom_a_norm:
        return []

    # ── Étape 1 : pré-filtre rapidfuzz (très rapide, en C/Rust) ──
    # On combine WRatio (combinaison robuste) + token_set_ratio (anti-faux-positif
    # type "DESIRS"/"...DIVERS") + seuil renforcé pour les noms courts.
    candidats = []
    a_short = len(nom_a_norm) < MIN_LENGTH_FOR_NORMAL
    for tier in tiers:
        nom_tier = getattr(tier, "nom_normalise", None) or getattr(tier, "nom", "")
        nom_b_norm = normaliser(nom_tier)
        if not nom_b_norm:
            continue

        # Garde-fou nom court : seuil plus strict
        b_short = len(nom_b_norm) < MIN_LENGTH_FOR_NORMAL
        wratio_threshold = PREFILTER_WRATIO_SHORT if (a_short or b_short) else PREFILTER_WRATIO

        w = fuzz.WRatio(nom_a_norm, nom_b_norm)
        if w < wratio_threshold:
            continue

        # Anti-faux-positif : exiger un minimum de chevauchement de tokens.
        # token_set_ratio ignore l'ordre et la répétition des mots — c'est
        # le ratio le plus tolérant aux variations légitimes (et le plus
        # discriminant face aux faux matchs par sous-chaîne aléatoire).
        ts = fuzz.token_set_ratio(nom_a_norm, nom_b_norm)
        if ts < PREFILTER_TOKEN_SET:
            continue

        candidats.append((tier, nom_b_norm))

    if not candidats:
        return []

    # ── Étape 2 : features + batch predict_proba sur les candidats ──
    features_matrix = []
    for tier, nom_b_norm in candidats:
        features_matrix.append(calculer_features(nom_a_norm, nom_b_norm))

    if _rf_model is not None:
        try:
            probas = _rf_model.predict_proba(features_matrix)
            scores = probas[:, 1]
        except Exception:
            scores = [
                float(f[0] * 0.3 + f[1] * 0.3 + f[2] * 0.4)
                for f in features_matrix
            ]
    else:
        scores = [
            float(f[0] * 0.3 + f[1] * 0.3 + f[2] * 0.4)
            for f in features_matrix
        ]

    # ── Étape 3 : filtrer par seuil et formater ──
    matchs = []
    for (tier, _), score in zip(candidats, scores):
        score = float(score)
        if score >= seuil:
            matchs.append({
                "tier_id": tier.id,
                "nom_tier": tier.nom,
                "score": round(score, 3),
            })

    matchs.sort(key=lambda x: -x["score"])
    return matchs
