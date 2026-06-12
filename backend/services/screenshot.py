"""
LegalEye — Génération de screenshots d'annonces depuis le PDF.

Stratégie :
1. Ouvrir le PDF du bulletin
2. Aller sur la page stockée (article.page_bulletin) si dispo, sinon
   chercher dans tout le PDF
3. Localiser l'annonce avec une cascade de recherches
   (nom_entreprise > snippet > RC)
4. Calculer une bbox englobante pour TOUTE l'annonce
   (en utilisant le début + une recherche de la fin du texte)
5. Rendre la page avec Pillow, dessiner un rectangle rouge semi-transparent
6. Mettre en cache disque pour éviter de re-rendre

Auteur : Marouan (Plastima - DUT IDIA)
"""

import os
import re
import hashlib
from typing import Optional, Tuple, List

import fitz
from PIL import Image, ImageDraw


# ─────────────────────────────────────────────────────────────
#  Cache disque
# ─────────────────────────────────────────────────────────────

_CACHE_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "cache",
        "screenshots",
    )
)


def _ensure_cache_dir():
    """Crée le dossier de cache si nécessaire (utile si purgé entre runs)."""
    os.makedirs(_CACHE_DIR, exist_ok=True)


# Création initiale au chargement du module
_ensure_cache_dir()


def _cache_path(bulletin_id: int, article_type: str, article_id: int) -> str:
    """Chemin du fichier PNG en cache."""
    return os.path.join(
        _CACHE_DIR,
        f"bulletin_{bulletin_id}_{article_type}_{article_id}.png",
    )


# ─────────────────────────────────────────────────────────────
#  Recherche du texte dans le PDF (cascade)
# ─────────────────────────────────────────────────────────────

def _lignes_significatives(texte: str, min_len: int = 12) -> List[str]:
    """
    Renvoie les lignes "distinctives" d'un texte d'annonce :
    - assez longues pour être uniques (>= min_len chars)
    - pas seulement des chiffres/dates
    - pas des phrases génériques communes à toutes les annonces
      (type "تأسيس شركة", "حل شركة", "إعالن قانوني" qui apparaissent
       aussi dans le sommaire)
    """
    if not texte:
        return []
    # Termes trop génériques qu'on retrouve dans des dizaines d'annonces
    blacklist = (
        "تأسيس شركة", "حل شركة", "تفويت حصص", "إعالن قانوني",
        "تعديل القانون", "بيع أصل تجاري", "إعالن عن تأسيس",
        "النشرة األولى", "النشرة الثانية", "النشرة األولى والثانية",
        "رئيس مصلحة كتابة الضبط", "رئيس كتابة الضبط",
    )
    out = []
    for ligne in texte.split("\n"):
        l = ligne.strip()
        if len(l) < min_len:
            continue
        if re.match(r"^[\d\s\-/.,]+$", l):
            continue
        if any(kw in l for kw in blacklist):
            continue
        out.append(l)
    return out


def _snippet_distinctif(texte: str, longueur: int = 30) -> Optional[str]:
    """Première ligne distinctive trouvée (compatibilité ascendante)."""
    lignes = _lignes_significatives(texte)
    if not lignes:
        return None
    snippet = lignes[0][:longueur].strip()
    return snippet if len(snippet) >= 10 else None


def _extraire_rc(texte: str) -> Optional[str]:
    """Tente d'extraire un numéro RC du texte."""
    if not texte:
        return None
    patterns = [
        r"رقم\s+التقييد[^\d]*(\d{4,7})",
        r"السجل التجاري[^\d]*(\d{4,7})",
        r"\bRC\s*N°?\s*(\d{4,7})",
    ]
    for p in patterns:
        m = re.search(p, texte, re.IGNORECASE)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return None


# Offset du sommaire : si on ne connaît pas page_bulletin, on commence la
# recherche après cette page pour éviter de tomber sur le sommaire (qui
# contient seulement les noms d'entreprises avec leur numéro de page).
# Le sommaire fait typiquement 20-30 pages dans un BO marocain de ~450 pages.
SOMMAIRE_OFFSET_DEFAUT = 28


def _trouver_zones(
    doc: fitz.Document,
    nom_entreprise: Optional[str],
    texte_annonce: Optional[str],
    page_hint: Optional[int] = None,
) -> Tuple[Optional[int], List[fitz.Rect]]:
    """
    Cherche l'annonce dans le PDF avec une cascade de stratégies.

    IMPORTANT : on cherche par BOUT DE TEXTE en priorité, pas par nom.
    Pourquoi : le nom_entreprise apparaît 2 fois dans le BO — une fois
    dans le sommaire (avec juste le n° de page) et une fois dans l'annonce
    réelle. Si on cherche le nom globalement, on tombe sur le sommaire.
    Le texte de l'annonce (RC, adresse, capital…) n'existe QUE dans
    l'annonce réelle, donc c'est plus fiable.

    Cascade :
        1. lignes_significatives du texte (priorité, hors sommaire)
        2. numéro RC
        3. nom_entreprise (en dernier recours, en évitant le sommaire)

    Args:
        doc: PDF ouvert
        nom_entreprise: nom détecté par le NER
        texte_annonce: texte complet de l'annonce
        page_hint: numéro de page 1-indexé connu (raccourci la recherche)

    Returns:
        (page_num_0indexed, [rectangles trouvés]) ou (None, []).
    """
    # Page de début de la zone "vraies annonces" — on évite le sommaire
    # qui contient les noms d'entreprises mais pas le contenu des annonces.
    start_page_0 = (page_hint - 1) if page_hint else SOMMAIRE_OFFSET_DEFAUT

    # ─── Pages à explorer en priorité ─────────────────────────
    pages_priority = []
    if page_hint and 1 <= page_hint <= len(doc):
        # Page exacte + ±1 de marge (annonce qui déborde)
        pages_priority.append(page_hint - 1)
        if page_hint - 2 >= max(0, SOMMAIRE_OFFSET_DEFAUT - 1):
            pages_priority.append(page_hint - 2)
        if page_hint < len(doc):
            pages_priority.append(page_hint)

    # ─── 1. Recherche par SNIPPETS (lignes distinctives du texte) ───
    # Ces snippets n'existent QUE dans l'annonce réelle, pas dans le sommaire.
    lignes_sig = _lignes_significatives(texte_annonce)
    snippets = [l[:35] for l in lignes_sig[:5]]   # 5 snippets candidats

    for snippet in snippets:
        # On essaie d'abord les pages indiquées
        for p in pages_priority:
            zones = doc[p].search_for(snippet)
            if zones:
                return p, zones
        # Sinon on parcourt tout le PDF en sautant le sommaire
        for p in range(start_page_0, len(doc)):
            if p in pages_priority:
                continue
            zones = doc[p].search_for(snippet)
            if zones:
                return p, zones

    # ─── 2. Recherche par RC (unique aussi) ────────────────────
    rc = _extraire_rc(texte_annonce)
    if rc:
        for p in pages_priority:
            zones = doc[p].search_for(rc)
            if zones:
                return p, zones
        for p in range(start_page_0, len(doc)):
            if p in pages_priority:
                continue
            zones = doc[p].search_for(rc)
            if zones:
                return p, zones

    # ─── 3. Fallback NOM (en évitant le sommaire) ──────────────
    if nom_entreprise and len(nom_entreprise) >= 3:
        for p in pages_priority:
            zones = doc[p].search_for(nom_entreprise)
            if zones:
                return p, zones
        # Recherche globale en SAUTANT le sommaire
        for p in range(start_page_0, len(doc)):
            if p in pages_priority:
                continue
            zones = doc[p].search_for(nom_entreprise)
            if zones:
                return p, zones

    return None, []


# ─────────────────────────────────────────────────────────────
#  Calcul de la bbox englobante de l'annonce dans la colonne
# ─────────────────────────────────────────────────────────────

# Largeur approximative d'une colonne du BO (en points PDF)
LARGEUR_COLONNE = 135

# Hauteur de l'en-tête de page (titre journal + n° BO + date).
# Même valeur que extraction_pdf.py (y_entete=70).
HAUTEUR_ENTETE = 70.0


# ─────────────────────────────────────────────────────────────
#  Détection des SÉPARATEURS — même logique que extraction_pdf.py
# ─────────────────────────────────────────────────────────────

def _est_separateur(texte: str) -> bool:
    """
    Détecte un séparateur d'annonce du BO.
    Logique compatible avec extraction_pdf.py, élargie pour accepter :
    - l'ordre inversé "P 43" que PyMuPDF peut produire en RTL
    - les caractères invisibles Unicode (LRM, RLM, ZWNJ, BOM…) qu'on
      strip avant le match
    """
    t = texte.strip()
    if not t:
        return False
    # Strip caractères invisibles Unicode (marqueurs bidirectionnels, BOM, etc.)
    t = re.sub(r"[​-‏‪-‮⁦-⁩﻿]", "", t).strip()
    if not t:
        return False
    # Fusionner milliers : "1 001 I" → "1001I"
    t_clean = re.sub(r"(\d)\s+(\d)", r"\1\2", t)
    # Section I : ordre normal "43 P" ou inversé "P 43"
    if re.match(r"^\d+\s*[PCI]$", t_clean):
        return True
    if re.match(r"^[PCI]\s*\d+$", t_clean):
        return True
    # Section II : chiffre seul, مكررX, Xمكرر
    if re.match(r"^\d+$", t):
        return True
    if re.match(r"^مكرر\d+$", t):
        return True
    if re.match(r"^\d+مكرر$", t):
        return True
    return False


def _bloc_text(b: dict) -> str:
    """Concatène le texte de tous les spans d'un bloc PyMuPDF."""
    out = []
    for line in b.get("lines", []):
        for span in line.get("spans", []):
            out.append(span.get("text", ""))
        out.append(" ")
    return "".join(out).strip()


def _blocs_avec_texte(page: "fitz.Page") -> List[Tuple[float, float, float, float, str]]:
    """
    [LEGACY] Renvoie tous les blocs texte de la page avec leur contenu.
    Préférer _lignes_avec_texte() qui est plus granulaire pour la
    détection de séparateurs.
    """
    data = page.get_text("dict").get("blocks", [])
    out = []
    for b in data:
        if b.get("type") != 0:
            continue
        x0, y0, x1, y1 = b["bbox"]
        out.append((x0, y0, x1, y1, _bloc_text(b)))
    return out


def _lignes_avec_texte(page: "fitz.Page") -> List[Tuple[float, float, float, float, str]]:
    """
    Renvoie toutes les LIGNES de la page (plus granulaire que les blocs),
    pour matcher la logique de extraction_pdf.py qui travaille ligne par
    ligne.

    Returns: [(x0, y0, x1, y1, texte_de_la_ligne), ...]
    """
    data = page.get_text("dict").get("blocks", [])
    out = []
    for b in data:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            x0, y0, x1, y1 = line["bbox"]
            # Concaténer les spans de la ligne
            texte = "".join(
                span.get("text", "") for span in line.get("spans", [])
            ).strip()
            if texte:
                out.append((x0, y0, x1, y1, texte))
    return out


# Si on trouve un trou vertical >= GAP_FIN entre deux blocs consécutifs
# dans la colonne, on considère que l'annonce s'arrête là.
GAP_FIN = 22.0    # points PDF — empiriquement ~1.5 lignes

# Distance du bas de la page en dessous de laquelle on considère que
# l'annonce déborde sur la colonne suivante (ou la page suivante).
SEUIL_BAS_PAGE = 60.0

# Marge interne autour du texte (en points PDF)
MARGE = 3.0


def _blocks_de_page(page: fitz.Page) -> List[Tuple[float, float, float, float]]:
    """Renvoie tous les bboxes de blocs texte de la page (filtrés)."""
    blocks = page.get_text("dict").get("blocks", [])
    return [
        b["bbox"]
        for b in blocks
        if b.get("type") == 0
    ]


def _region_dans_colonne(
    blocks: List[Tuple[float, float, float, float]],
    centre_x: float,
    y_haut: Optional[float] = None,
) -> Optional[fitz.Rect]:
    """
    [LEGACY] Calcule la bbox englobante des blocs d'une colonne via gap.
    Conservée pour compatibilité — préférer _region_jusqu_au_separateur().
    """
    candidats = []
    for bx0, by0, bx1, by1 in blocks:
        cx = (bx0 + bx1) / 2
        if not (centre_x - LARGEUR_COLONNE / 2 - 10 <= cx <= centre_x + LARGEUR_COLONNE / 2 + 10):
            continue
        if y_haut is not None and by1 < y_haut - 2:
            continue
        candidats.append((bx0, by0, bx1, by1))

    if not candidats:
        return None

    candidats.sort(key=lambda b: b[1])
    x_min, y_min, x_max, y_max = candidats[0]
    last_y = y_max
    for bx0, by0, bx1, by1 in candidats[1:]:
        gap = by0 - last_y
        if gap > GAP_FIN:
            break
        x_min = min(x_min, bx0)
        x_max = max(x_max, bx1)
        y_max = max(y_max, by1)
        last_y = by1

    return fitz.Rect(x_min - MARGE, y_min - MARGE, x_max + MARGE, y_max + MARGE)


def _region_jusqu_au_separateur(
    blocs_avec_texte: List[Tuple[float, float, float, float, str]],
    centre_x: float,
    y_haut: Optional[float] = None,
) -> Tuple[Optional[fitz.Rect], bool]:
    """
    Calcule la bbox d'une annonce dans une colonne, en utilisant la
    même logique de séparateurs que extraction_pdf.py.

    On scanne les blocs de la colonne de haut en bas (à partir de y_haut
    si fourni, sinon du tout début). On accumule jusqu'à rencontrer un
    séparateur (X P / X C / X I / chiffre seul / مكررX). Le rectangle
    englobe tout ce qui est AVANT le séparateur.

    Returns:
        (region, separateur_trouve)
        region : fitz.Rect ou None si aucun bloc
        separateur_trouve : True si on a vu un séparateur (= annonce
                            terminée dans cette colonne).
                            False si on est arrivé au bas sans séparateur
                            (= l'annonce déborde vers la suite).
    """
    # Garde les blocs dont le centre est dans la colonne autour de centre_x
    candidats = []
    for bx0, by0, bx1, by1, texte in blocs_avec_texte:
        cx = (bx0 + bx1) / 2
        if not (centre_x - LARGEUR_COLONNE / 2 - 10 <= cx <= centre_x + LARGEUR_COLONNE / 2 + 10):
            continue
        # Filtre identique à extraction_pdf.py : on skippe les lignes dont
        # le haut (y0) est dans la zone d'en-tête. Pas de tolérance —
        # cohérent avec le test `if line["bbox"][1] < y_entete: continue`
        # utilisé dans l'extraction des annonces.
        if y_haut is not None and by0 < y_haut:
            continue
        candidats.append((bx0, by0, bx1, by1, texte))

    if not candidats:
        return None, False

    candidats.sort(key=lambda b: b[1])

    # Accumuler jusqu'au séparateur
    x_min = candidats[0][0]
    y_min = candidats[0][1]
    x_max = candidats[0][2]
    y_max = candidats[0][3]
    last_y = y_max
    separateur_trouve = False

    # Premier bloc : si c'est déjà un séparateur, l'annonce est vide
    if _est_separateur(candidats[0][4]):
        return None, True

    for bx0, by0, bx1, by1, texte in candidats[1:]:
        if _est_separateur(texte):
            # Stop juste avant le séparateur
            separateur_trouve = True
            break
        # Gap trop grand : on considère que c'est la fin (safety)
        gap = by0 - last_y
        if gap > GAP_FIN * 2:
            break
        x_min = min(x_min, bx0)
        x_max = max(x_max, bx1)
        y_max = max(y_max, by1)
        last_y = by1

    return (
        fitz.Rect(x_min - MARGE, y_min - MARGE, x_max + MARGE, y_max + MARGE),
        separateur_trouve,
    )


def _ref_finale_de_l_annonce(texte_annonce: Optional[str]) -> Optional[str]:
    """
    Extrait le numéro de référence unique qui termine chaque annonce
    du BO marocain. Patterns typiques :
        "تم الإيداع ... تحت رقم 60493"
        "تم التقييد ... تحت رقم .709679"

    Ce numéro est UNIQUE par annonce — donc fiable comme marqueur de fin,
    contrairement à des phrases génériques type "تم الإيداع القانوني"
    qui apparaissent dans toutes les annonces.
    """
    if not texte_annonce:
        return None

    # Pattern 1 : "تحت رقم XXXXX" (numéro de dépôt légal / RC)
    matches = re.findall(r"تحت\s+رقم\s*\.?\s*(\d{4,8})", texte_annonce)
    if matches:
        return matches[-1]

    # Pattern 2 : dernier numéro à 5-7 chiffres dans le texte
    matches = re.findall(r"\b(\d{5,7})\b", texte_annonce)
    if matches:
        return matches[-1]

    return None


def _zone_de_fin_dans_colonne(
    page: fitz.Page,
    texte_annonce: Optional[str],
    centre_x: float,
) -> Optional[fitz.Rect]:
    """
    Cherche la fin de l'annonce dans une colonne donnée, via la
    référence unique. Renvoie le Rect ou None.
    """
    ref = _ref_finale_de_l_annonce(texte_annonce)
    if not ref:
        return None

    zones = page.search_for(ref)
    if not zones:
        return None

    zones_col = [
        z for z in zones
        if centre_x - LARGEUR_COLONNE / 2 - 10
           <= (z.x0 + z.x1) / 2
           <= centre_x + LARGEUR_COLONNE / 2 + 10
    ]
    return zones_col[-1] if zones_col else None


def _annonce_complete_dans_regions(
    page: fitz.Page,
    regions: List[fitz.Rect],
    texte_annonce: Optional[str],
) -> bool:
    """
    Vérifie si la fin de l'annonce se trouve à l'intérieur des régions.

    Utilise le numéro de référence unique (تحت رقم XXXX) qui est unique
    à chaque annonce — donc fiable contrairement aux snippets de texte
    génériques qu'on retrouve dans toutes les annonces du BO.
    """
    if not texte_annonce or not regions:
        return False

    ref = _ref_finale_de_l_annonce(texte_annonce)
    if not ref:
        return False

    zones = page.search_for(ref)
    if not zones:
        return False

    for z in zones:
        for r in regions:
            if (r.x0 - 4 <= z.x0 and z.x1 <= r.x1 + 4
                    and r.y0 - 4 <= z.y0 and z.y1 <= r.y1 + 4):
                return True
    return False


def _continue_vraiment_page_suivante(
    doc: fitz.Document,
    page_num: int,
    nom_entreprise: Optional[str],
    texte_annonce: Optional[str],
) -> bool:
    """
    Décide s'il y a une VRAIE continuation page suivante.

    Par défaut : NON, on ne continue pas. On ne dit OUI que si on a
    une preuve positive de continuation :

    1. Le nom_entreprise apparaît sur la page suivante (en SAUTANT le
       sommaire), preuve forte que la même annonce continue.
    2. Ou une ligne distinctive du texte_annonce apparaît sur la page
       suivante alors qu'elle n'a pas été trouvée sur la page courante.

    Ce check conservateur évite de surligner toute une page voisine
    quand l'annonce s'est en fait terminée naturellement.
    """
    next_num = page_num + 1
    if next_num >= len(doc):
        return False

    next_page = doc[next_num]

    # 1) Preuve la plus fiable : le nom_entreprise apparaît sur la page suivante
    if nom_entreprise and len(nom_entreprise) >= 4:
        zones = next_page.search_for(nom_entreprise)
        if zones:
            # Le nom apparaît → c'est sans doute la suite. Vérifier que
            # ce n'est pas juste une mention dans une autre annonce :
            # une vraie continuation devrait être dans le HAUT de la
            # colonne la plus à droite (sens RTL).
            page_w = next_page.rect.width
            for z in zones:
                # Doit être dans la moitié droite ET dans le haut (y < 200)
                if z.x0 > page_w / 2 and z.y0 < 200:
                    return True
            # Sinon, c'est probablement une mention isolée — pas une
            # vraie continuation. On ne déclenche pas la continuation
            # automatiquement dans ce cas.

    # 2) Fallback : recherche d'une ligne distinctive du texte
    if texte_annonce:
        lignes_sig = _lignes_significatives(texte_annonce, min_len=15)
        # On essaie les 3 dernières lignes (probables, car en fin de texte)
        for ligne in lignes_sig[-3:]:
            terme = ligne[:35]
            if len(terme) < 12:
                continue
            zones = next_page.search_for(terme)
            if not zones:
                continue
            # Idem : doit être en haut de la page (continuation typique)
            for z in zones:
                if z.y0 < 200:
                    return True

    return False


def _bbox_annonce_simple(
    page: fitz.Page,
    zones_debut: List[fitz.Rect],
    texte_annonce: Optional[str],
) -> Tuple[List[fitz.Rect], bool]:
    """
    Calcule les régions de l'annonce SUR UNE SEULE PAGE, en utilisant
    la même logique de séparateurs que extraction_pdf.py.

    Algorithme :
    1. Trouver la colonne où commence l'annonce (via le snippet trouvé).
    2. Scanner cette colonne du début jusqu'au prochain séparateur
       (X P / X C / X I / etc.).
    3. Si on a trouvé un séparateur → annonce complète, point.
    4. Sinon (on a touché le bas sans séparateur) → l'annonce déborde
       vers la colonne à gauche (sens RTL) : on répète l'étape 2 depuis
       le haut de cette colonne.
    5. Si on épuise les colonnes sans trouver de séparateur → l'annonce
       continue sur la page suivante.

    Returns:
        (regions, continue_page_suivante)
    """
    if not zones_debut:
        return [fitz.Rect(0, 0, page.rect.width, page.rect.height)], False

    debut = zones_debut[0]
    centre_debut = (debut.x0 + debut.x1) / 2
    lignes_txt = _lignes_avec_texte(page)
    regions: List[fitz.Rect] = []

    # 1) Région dans la colonne du début, du snippet jusqu'au séparateur
    region1, sep_trouve = _region_jusqu_au_separateur(
        lignes_txt, centre_debut, y_haut=debut.y0
    )
    if region1 is None:
        # Fallback minimaliste
        region1 = fitz.Rect(
            max(0, debut.x0 - 15),
            max(0, debut.y0 - MARGE),
            min(page.rect.width, debut.x0 + LARGEUR_COLONNE),
            min(page.rect.height, debut.y1 + 200),
        )
    regions.append(region1)

    if sep_trouve:
        # Annonce complète sur cette colonne, pas de débordement
        return regions, False

    # 2) Sinon : on déborde vers la colonne à gauche (sens RTL)
    centre_courant = centre_debut
    while True:
        centre_suivant = centre_courant - LARGEUR_COLONNE
        if centre_suivant - LARGEUR_COLONNE / 2 < 0:
            # Plus de colonne à gauche → continuation page suivante
            return regions, True

        # Sur les colonnes suivantes, on commence sous l'en-tête de page
        # (pas y_haut=None qui inclurait الجريدة الرسمية, etc.)
        region_suite, sep_trouve = _region_jusqu_au_separateur(
            lignes_txt, centre_suivant, y_haut=HAUTEUR_ENTETE
        )
        if region_suite is None:
            # Pas de texte dans cette colonne → considérer annonce finie
            return regions, False

        regions.append(region_suite)
        centre_courant = centre_suivant

        if sep_trouve:
            # Annonce terminée dans cette colonne
            return regions, False


def _bbox_annonce(
    page: fitz.Page,
    zones_debut: List[fitz.Rect],
    texte_annonce: Optional[str],
) -> Tuple[List[fitz.Rect], bool]:
    """
    Wrapper qui délègue à _bbox_annonce_simple (logique basée sur les
    séparateurs du BO, identique à l'extraction).
    """
    return _bbox_annonce_simple(page, zones_debut, texte_annonce)


# ─────────────────────────────────────────────────────────────
#  Génération de l'image PNG
# ─────────────────────────────────────────────────────────────

ZOOM = 2.0  # 2× pour image plus nette


def _rendre_page(
    page: fitz.Page,
    bboxes: List[fitz.Rect],
    page_label: Optional[str] = None,
    note_bas: Optional[str] = None,
) -> Image.Image:
    """
    Rend une page PyMuPDF en PIL Image avec :
    - un ou plusieurs rectangles rouges semi-transparents
    - éventuellement un libellé "Page X" en haut
    - éventuellement une note jaune en bas (ex: continuation)
    """
    matrix = fitz.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img, "RGBA")

    # Rectangles
    for bbox in bboxes:
        rect_scaled = [
            bbox.x0 * ZOOM, bbox.y0 * ZOOM,
            bbox.x1 * ZOOM, bbox.y1 * ZOOM,
        ]
        draw.rectangle(rect_scaled, fill=(255, 50, 50, 50))
        draw.rectangle(rect_scaled, outline=(220, 30, 30, 255), width=4)

    # Libellé page en haut
    if page_label:
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("Helvetica", 28)
        except Exception:
            font = ImageFont.load_default()
        # Bande bleue en haut
        band_h = 40
        draw.rectangle(
            [0, 0, img.width, band_h],
            fill=(40, 90, 180, 230),
        )
        draw.text((14, 8), page_label, fill=(255, 255, 255, 255), font=font)

    # Note de continuation en bas
    if note_bas:
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("Helvetica", 24)
        except Exception:
            font = ImageFont.load_default()
        band_h = 44
        band_y0 = img.height - band_h
        draw.rectangle(
            [0, band_y0, img.width, img.height],
            fill=(255, 220, 80, 240),
        )
        draw.text((14, band_y0 + 10), note_bas,
                  fill=(40, 40, 40, 255), font=font)

    return img


def _combiner_horizontalement(images: List[Image.Image]) -> bytes:
    """Colle plusieurs PIL Image côte à côte en une seule PNG."""
    if not images:
        return b""
    if len(images) == 1:
        import io
        buf = io.BytesIO()
        images[0].save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    SEP = 8
    total_w = sum(im.width for im in images) + SEP * (len(images) - 1)
    max_h = max(im.height for im in images)
    combined = Image.new("RGB", (total_w, max_h), (210, 210, 210))
    x = 0
    for im in images:
        combined.paste(im, (x, 0))
        x += im.width + SEP

    import io
    buf = io.BytesIO()
    combined.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _combiner_verticalement(images: List[Image.Image]) -> bytes:
    """Colle plusieurs PIL Image les unes sous les autres en une seule PNG."""
    if not images:
        return b""
    if len(images) == 1:
        import io
        buf = io.BytesIO()
        images[0].save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    SEP = 12  # séparateur gris entre les pages
    total_h = sum(im.height for im in images) + SEP * (len(images) - 1)
    max_w = max(im.width for im in images)
    combined = Image.new("RGB", (max_w, total_h), (210, 210, 210))
    y = 0
    for im in images:
        # Centre horizontalement si une page est plus étroite
        x = (max_w - im.width) // 2
        combined.paste(im, (x, y))
        y += im.height + SEP

    import io
    buf = io.BytesIO()
    combined.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# Hauteur maxi d'une continuation quand on n'arrive pas à localiser sa fin.
# Empiriquement, une continuation typique fait 10-15 lignes (~200pt à zoom 1).
MAX_CONTINUATION_HEIGHT = 240.0


def _trouver_continuation_par_separateur(
    doc: fitz.Document,
    page_num_courant: int,
) -> Tuple[Optional[fitz.Page], List[fitz.Rect], bool]:
    """
    Continuation page suivante en utilisant les SÉPARATEURS du BO.

    Une annonce qui déborde reprend en HAUT de la 1ère colonne (rightmost
    RTL) de la page suivante, jusqu'au prochain séparateur. Si pas de
    séparateur dans cette colonne, elle déborde encore vers la 2e
    colonne, et ainsi de suite.

    Returns:
        (page_suivante, regions, continue_encore_apres)
    """
    next_num = page_num_courant + 1
    if next_num >= len(doc):
        return None, [], False

    next_page = doc[next_num]
    lignes_txt = _lignes_avec_texte(next_page)
    if not lignes_txt:
        return next_page, [], False

    page_width = next_page.rect.width
    # Centres des 4 colonnes en sens RTL (col 0 = rightmost)
    centres = [page_width - (i + 0.5) * LARGEUR_COLONNE - 8 for i in range(4)]

    regions: List[fitz.Rect] = []
    for i, centre in enumerate(centres):
        # On exclut l'en-tête de page (titre journal + n° BO + date),
        # même seuil que extraction_pdf.py (y_entete=70).
        region, sep_trouve = _region_jusqu_au_separateur(
            lignes_txt, centre, y_haut=HAUTEUR_ENTETE
        )
        if region is None:
            return next_page, regions, False

        regions.append(region)
        if sep_trouve:
            return next_page, regions, False

        # Sinon, on continue à gauche (colonne suivante)

    # On a parcouru les 4 colonnes sans trouver de séparateur
    # → l'annonce continue encore après cette page
    return next_page, regions, True


def _trouver_continuation(
    doc: fitz.Document,
    page_num_courant: int,
    texte_annonce: Optional[str] = None,
) -> Tuple[Optional[fitz.Page], List[fitz.Rect], bool]:
    """
    Wrapper : route vers la nouvelle logique basée sur les séparateurs.
    """
    return _trouver_continuation_par_separateur(doc, page_num_courant)


def _LEGACY_trouver_continuation(
    doc: fitz.Document,
    page_num_courant: int,
    texte_annonce: Optional[str] = None,
) -> Tuple[Optional[fitz.Page], List[fitz.Rect], bool]:
    """
    [LEGACY] Ancienne stratégie basée sur la référence unique.
    Conservée pour rollback rapide.
    """
    next_num = page_num_courant + 1
    if next_num >= len(doc):
        return None, [], False

    next_page = doc[next_num]
    blocks = _blocks_de_page(next_page)
    if not blocks:
        return next_page, [], False

    page_width = next_page.rect.width
    page_height = next_page.rect.height

    # Centres des 4 colonnes en sens RTL (colonne 0 = rightmost)
    centres_cols = [
        page_width - (i + 0.5) * LARGEUR_COLONNE - 8
        for i in range(4)
    ]

    # ── Cas 1 : on trouve la zone de fin via la référence unique ──
    ref = _ref_finale_de_l_annonce(texte_annonce)
    fin_col_idx = None
    fin_y_max = None

    if ref:
        toutes_zones_fin = next_page.search_for(ref)
        # Pour chaque zone trouvée, déterminer dans quelle colonne
        for z in toutes_zones_fin:
            cx = (z.x0 + z.x1) / 2
            for idx, centre in enumerate(centres_cols):
                if abs(cx - centre) < LARGEUR_COLONNE / 2 + 10:
                    # On garde la colonne la plus à droite (1ère en RTL)
                    # où la ref apparaît — c'est la continuation directe
                    if fin_col_idx is None or idx < fin_col_idx:
                        fin_col_idx = idx
                        fin_y_max = z.y1
                    break

    # ── Construire les régions ──
    regions: List[fitz.Rect] = []

    if fin_col_idx is not None:
        # Fin trouvée : encadrer col 0 → col fin_col_idx, dernier capé à fin_y_max
        for col_idx in range(fin_col_idx + 1):
            region = _region_dans_colonne(blocks, centres_cols[col_idx], y_haut=None)
            if region is None:
                continue
            if col_idx == fin_col_idx:
                # Dernière colonne : on coupe à fin_y_max
                region = fitz.Rect(
                    region.x0,
                    region.y0,
                    region.x1,
                    min(fin_y_max + MARGE, region.y1),
                )
            regions.append(region)
        return next_page, regions, False

    # ── Cas 2 : pas de référence trouvée → fallback prudent ──
    # On encadre uniquement le HAUT de la colonne 1 (max MAX_CONTINUATION_HEIGHT)
    region = _region_dans_colonne(blocks, centres_cols[0], y_haut=None)
    if region is None:
        return next_page, [], False

    # Limiter à MAX_CONTINUATION_HEIGHT depuis le haut
    region = fitz.Rect(
        region.x0,
        region.y0,
        region.x1,
        min(region.y0 + MAX_CONTINUATION_HEIGHT, region.y1),
    )
    regions.append(region)

    # Signaler éventuellement "continue encore" si la région touche le bas
    continue_apres = region.y1 > page_height - SEUIL_BAS_PAGE
    return next_page, regions, continue_apres


# ─────────────────────────────────────────────────────────────
#  Fonction principale
# ─────────────────────────────────────────────────────────────

def generer_screenshot(
    pdf_path: str,
    bulletin_id: int,
    article_type: str,   # "entreprise" ou "mahakim"
    article_id: int,
    nom_entreprise: Optional[str],
    texte_annonce: Optional[str],
    page_bulletin: Optional[int] = None,
    use_cache: bool = True,
) -> Optional[bytes]:
    """
    Génère le PNG d'une annonce avec son rectangle de surlignage.

    Returns: bytes du PNG, ou None si l'annonce est introuvable.
    """
    cache_file = _cache_path(bulletin_id, article_type, article_id)
    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            return f.read()

    if not os.path.exists(pdf_path):
        return None

    doc = fitz.open(pdf_path)
    try:
        page_num, zones = _trouver_zones(
            doc, nom_entreprise, texte_annonce, page_hint=page_bulletin,
        )
        if page_num is None or not zones:
            return None

        page = doc[page_num]
        regions, continue_page_suivante = _bbox_annonce(page, zones, texte_annonce)

        images = []

        # ── Page courante ──
        # Si on continue page suivante, on n'affiche PAS la note jaune ici
        # (la suite sera visible directement). Sinon, pas de note.
        label_courant = f"Page {page_num + 1}"
        images.append(
            _rendre_page(page, regions, page_label=label_courant, note_bas=None)
        )

        # ── Page suivante (si l'annonce continue) ──
        if continue_page_suivante:
            next_page, regions_next, continue_3e = _trouver_continuation(doc, page_num)
            if next_page is not None and regions_next:
                label_next = f"Page {page_num + 2} (suite)"
                note_next = None
                if continue_3e and page_num + 2 < len(doc):
                    note_next = f"L'annonce continue page {page_num + 3}"
                images.append(
                    _rendre_page(
                        next_page, regions_next,
                        page_label=label_next, note_bas=note_next,
                    )
                )

        # ── Combine en une seule PNG ──
        # Pages empilées verticalement (page suivante EN DESSOUS de la page courante)
        png_bytes = _combiner_verticalement(images)

        if use_cache:
            # Re-création du dossier au cas où il aurait été purgé manuellement
            # depuis le démarrage de l'API (rm -rf cache/...).
            _ensure_cache_dir()
            with open(cache_file, "wb") as f:
                f.write(png_bytes)

        return png_bytes
    finally:
        doc.close()
