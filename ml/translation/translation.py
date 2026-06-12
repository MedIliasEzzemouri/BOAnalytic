"""
LegalEye — Translittération des Noms Arabes → Français
========================================================
Utilise deep-translator (Google Translate, gratuit, sans clé API).

Étape du pipeline entre le Modèle 2 (NER) et le Modèle 3 (Similarité).

Fonctionnalités robustesse :
- Cache mémoire (les mêmes noms reviennent souvent dans un bulletin)
- Circuit breaker (3 échecs réseau consécutifs → désactivation propre)
- 1 seule tentative par appel (pas de retry chronophage)

Usage :
    from translation import preparer_nom_pour_similarite, reset_translator_state

    reset_translator_state()  # entre 2 bulletins
    nom_fr = preparer_nom_pour_similarite("شركة سيغماتيل ش.م.م")
    # → "SIGMATEL" (ou nom arabe nettoyé si réseau down)

Auteur : Marouan (Plastima - DUT IDIA)
"""

import re
import time

# ══════════════════════════════════════════════════════════════
#  FORMES JURIDIQUES ARABES (supprimées avant traduction)
# ══════════════════════════════════════════════════════════════

FORMES_JUR_AR = [
    (re.compile(r"ش\.?\s*ذ\.?\s*م\.?\s*م"), ""),           # SARL AU
    (re.compile(r"ش\.?\s*م\.?\s*م"), ""),                   # SARL
    (re.compile(r"ش\.?\s*م"), ""),                          # SA
    (re.compile(r"ش\.?\s*ت"), ""),                          # SNC
    (re.compile(r"شركة\s*ذات\s*(?:المسؤولية|املسؤولية)\s*(?:المحدودة|املحدودة)\s*(?:ذات\s*الشريك\s*الوحيد)?"), ""),
    (re.compile(r"شركة\s*ذات"), ""),
    (re.compile(r"شركة\s*مساهمة"), ""),
    (re.compile(r"شركة\s*تضامن"), ""),
    (re.compile(r"شركة"), ""),
]


# ══════════════════════════════════════════════════════════════
#  ÉTAT GLOBAL (singleton + cache + circuit breaker)
# ══════════════════════════════════════════════════════════════

_translator = None

# Cache mémoire : les mêmes noms reviennent souvent dans un bulletin
# (par exemple les formes juridiques après nettoyage). On les traduit
# une seule fois par run.
_translation_cache = {}

# Circuit breaker : si trop d'échecs réseau consécutifs, on désactive
# Google Translate pour le reste du run. Les noms arabes restants sont
# renvoyés en majuscules sans traduction (le RF travaille en mode dégradé).
_translator_disabled = False
_consecutive_failures = 0
_MAX_CONSECUTIVE_FAILURES = 3


def reset_translator_state():
    """Réinitialise le cache et le circuit breaker (à appeler entre 2 bulletins)."""
    global _translation_cache, _translator_disabled, _consecutive_failures
    _translation_cache = {}
    _translator_disabled = False
    _consecutive_failures = 0


def _get_translator():
    """Singleton pour le translator."""
    global _translator
    if _translator is None:
        from deep_translator import GoogleTranslator
        _translator = GoogleTranslator(source='ar', target='fr')
    return _translator


def contient_arabe(texte):
    """Vérifie si un texte contient des caractères arabes."""
    if not texte:
        return False
    return bool(re.search(r'[؀-ۿ]', texte))


def nettoyer_formes_juridiques(nom):
    """Supprime les formes juridiques arabes du nom."""
    for pattern, remplacement in FORMES_JUR_AR:
        nom = pattern.sub(remplacement, nom)
    nom = re.sub(r'[\-\.\,\:\;\/\(\)«»]', ' ', nom)
    nom = re.sub(r'\s+', ' ', nom).strip()
    return nom


def traduire_nom(nom, max_retries=1):
    """
    Traduit un nom d'entreprise arabe en français.

    Comportement :
    - Si déjà vu (cache) : renvoie le résultat mémorisé instantanément.
    - Si circuit breaker activé : renvoie le nom nettoyé en majuscules.
    - Sinon : 1 appel Google Translate (sans retry, pas de sleep).
      En cas d'échec, incrémente un compteur. Au 3e échec consécutif,
      le circuit breaker s'active : tous les noms arabes restants sont
      renvoyés sans traduction, sans appel réseau.

    Args:
        nom: nom en arabe (ex: "شركة سيغماتيل ش.م.م")
        max_retries: conservé pour compat ascendante, ignoré.

    Returns:
        Nom en français majuscules (ex: "SIGMATEL"), ou nom arabe nettoyé
        en majuscules si le réseau est down.
    """
    global _consecutive_failures, _translator_disabled

    if not nom or not contient_arabe(nom):
        return nom

    # 1. Nettoyage formes juridiques
    nom_clean = nettoyer_formes_juridiques(nom)
    if not nom_clean:
        return nom

    # 2. Cache mémoire
    if nom_clean in _translation_cache:
        return _translation_cache[nom_clean]

    # 3. Circuit breaker : on n'appelle plus Google si déjà désactivé
    if _translator_disabled:
        result = nom_clean.upper()
        _translation_cache[nom_clean] = result
        return result

    # 4. Tentative de traduction (1 seule fois, pas de retry chronophage)
    try:
        translator = _get_translator()
        traduit = translator.translate(nom_clean)
        traduit = traduit.strip().upper()
        traduit = re.sub(r'[«»\"\']', '', traduit)
        traduit = re.sub(r'\s+', ' ', traduit).strip()

        # Succès : reset du compteur d'échecs
        _consecutive_failures = 0
        _translation_cache[nom_clean] = traduit
        return traduit

    except Exception:
        _consecutive_failures += 1
        if _consecutive_failures >= _MAX_CONSECUTIVE_FAILURES and not _translator_disabled:
            print(f"  ⚠️  Traduction Google désactivée après "
                  f"{_MAX_CONSECUTIVE_FAILURES} échecs réseau consécutifs. "
                  f"Les noms arabes restants ne seront pas traduits.")
            _translator_disabled = True

        result = nom_clean.upper()
        _translation_cache[nom_clean] = result
        return result


def traduire_batch(noms, delay=0.0):
    """
    Traduit une liste de noms arabes. Utilise le cache automatiquement.

    Args:
        noms: liste de noms
        delay: secondes entre chaque requête (0 par défaut, le cache gère)

    Returns:
        liste de noms traduits
    """
    resultats = []
    for i, nom in enumerate(noms):
        if contient_arabe(nom):
            resultats.append(traduire_nom(nom))
            if delay > 0:
                time.sleep(delay)
        else:
            resultats.append(nom)
        if (i + 1) % 50 == 0:
            print(f"  Traduit {i + 1}/{len(noms)}...")
    return resultats


# ══════════════════════════════════════════════════════════════
#  FONCTION POUR LE PIPELINE FASTAPI
# ══════════════════════════════════════════════════════════════

def preparer_nom_pour_similarite(nom):
    """
    Fonction utilisée dans le pipeline entre NER et Similarité.
    Si le nom est en arabe → traduit en français.
    Sinon → retourne tel quel.

    Usage dans services/pipeline.py :
        from translation import preparer_nom_pour_similarite, reset_translator_state

        reset_translator_state()  # début de bulletin
        nom = extraire_nom_ner(texte)
        nom = preparer_nom_pour_similarite(nom)
        matchs = comparer(nom, tiers)
    """
    if not nom:
        return nom
    if contient_arabe(nom):
        return traduire_nom(nom)
    return nom


# ══════════════════════════════════════════════════════════════
#  MAIN (tests)
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  LegalEye — Test Translittération")
    print("=" * 55)

    tests = [
        "شركة سيغماتيل ش.م.م",
        "بيوبيست ماروك",
        "فروتيفار",
        "إلياد بروموسيون",
        "المقاولة الكبرى للبناء",
        "شركة النقل أطلس ش.ذ.م.م",
        "SIGMATEL SARL",
        "COMETAV",
    ]

    print("\nTests (1er passage — appels réseau) :")
    for nom in tests:
        resultat = preparer_nom_pour_similarite(nom)
        arabe = "[AR]" if contient_arabe(nom) else "[FR]"
        print(f"  {arabe} {nom:40} -> {resultat}")

    print("\nTests (2e passage — cache, instantané) :")
    for nom in tests:
        resultat = preparer_nom_pour_similarite(nom)
        arabe = "[AR]" if contient_arabe(nom) else "[FR]"
        print(f"  {arabe} {nom:40} -> {resultat}")

    print(f"\nCache : {len(_translation_cache)} entrees")
    print(f"Circuit breaker : {'desactive' if _translator_disabled else 'actif'}")
    print("\nOK")
