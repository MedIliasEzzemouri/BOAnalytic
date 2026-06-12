"""
Tests du module ml/similarite (fonctions pures, sans modèle ni BDD).

Lancer :  python -m pytest tests/ -v
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))

from similarite.similarite import normaliser, calculer_features, comparer  # noqa: E402


# ── normaliser ────────────────────────────────────────────────

def test_normaliser_retire_forme_juridique():
    assert normaliser("SIGMATEL SARL") == "SIGMATEL"
    assert normaliser("Ste Atlas Transport S.A.R.L") == "ATLAS TRANSPORT"


def test_normaliser_retire_ponctuation_et_majuscule():
    assert normaliser("co-me.tav;") == "CO ME TAV"


def test_normaliser_retire_caracteres_invisibles():
    # BOM + zero-width space laissés par PyMuPDF
    assert normaliser("﻿SIGMA​TEL") == "SIGMATEL"


def test_normaliser_entree_vide():
    assert normaliser("") == ""
    assert normaliser(None) == ""


# ── calculer_features ─────────────────────────────────────────

def test_features_identiques():
    f = calculer_features("SIGMATEL", "SIGMATEL")
    assert len(f) == 7
    assert f[0] == 1.0          # levenshtein_ratio
    assert f[4] == 0.0          # diff_longueur
    assert f[5] == 1.0          # jaccard_mots
    assert f[6] == 1            # premier_mot_identique


def test_features_differents():
    f = calculer_features("SIGMATEL", "BIOPEST MAROC")
    assert f[0] < 0.5
    assert f[6] == 0


def test_features_entree_vide():
    f = calculer_features("", "SIGMATEL")
    assert f == [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0]


# ── comparer (fallback rapidfuzz, sans modèle RF chargé) ──────

def _tier(id, nom):
    return SimpleNamespace(id=id, nom=nom, nom_normalise=normaliser(nom))


def test_comparer_match_exact():
    tiers = [_tier(1, "SIGMATEL"), _tier(2, "ATLAS TRANSPORT")]
    matchs = comparer("SIGMATEL", tiers, seuil=0.85)
    assert len(matchs) == 1
    assert matchs[0]["tier_id"] == 1
    assert matchs[0]["score"] >= 0.85


def test_comparer_aucun_match():
    tiers = [_tier(1, "SIGMATEL")]
    assert comparer("ENTREPRISE TOTALEMENT DIFFERENTE", tiers, seuil=0.85) == []


def test_comparer_nom_court_seuil_renforce():
    # "EMT" ne doit pas matcher "EMENTEC" par hasard (garde-fou noms courts)
    tiers = [_tier(1, "EMENTEC SOLUTIONS")]
    assert comparer("EMT", tiers, seuil=0.85) == []


def test_comparer_entrees_vides():
    assert comparer("", [_tier(1, "X")], seuil=0.85) == []
    assert comparer("SIGMATEL", [], seuil=0.85) == []
