"""
Tests de la détection des séparateurs d'annonces du BO
(backend/services/screenshot.py — fonction pure, sans PDF).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.screenshot import _est_separateur  # noqa: E402


def test_separateur_section_i():
    assert _est_separateur("43 P")
    assert _est_separateur("1 001 I")     # milliers avec espace
    assert _est_separateur("12C")
    assert _est_separateur("P 43")        # ordre inversé RTL


def test_separateur_section_ii():
    assert _est_separateur("128")          # chiffre seul
    assert _est_separateur("مكرر12")
    assert _est_separateur("12مكرر")


def test_separateur_avec_caracteres_invisibles():
    # PyMuPDF laisse parfois LRM/RLM autour des séparateurs
    assert _est_separateur("‎43 P‏")


def test_non_separateurs():
    assert not _est_separateur("")
    assert not _est_separateur("SIGMATEL SARL")
    assert not _est_separateur("شركة سيغماتيل")
    assert not _est_separateur("43 pages")
