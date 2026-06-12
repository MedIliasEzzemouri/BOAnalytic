import fitz
import re
import os

# ══════════════════════════════════════════════════════════════
#  EXTRACTION BULLETINS OFFICIELS — VERSION CORRIGÉE RTL
# ══════════════════════════════════════════════════════════════
#  Fix : certains PDFs stockent les caractères arabes en ordre
#  inversé (LTR au lieu de RTL). Ce script détecte et corrige
#  automatiquement le problème ligne par ligne.
#
#  OUTPUT : SOMMAIRE + SECTION I + SECTION II dans un seul fichier
# ══════════════════════════════════════════════════════════════


def _is_rtl_char(c):
    """Vérifie si un caractère est arabe/RTL."""
    cp = ord(c)
    return (0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or
            0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF)


def _fix_line_rtl(chars_with_pos):
    """Reconstruit une ligne en triant les caractères par position x."""
    if not chars_with_pos:
        return ""
    sorted_chars = sorted(chars_with_pos, key=lambda c: -c[0])
    result = []
    i = 0
    while i < len(sorted_chars):
        c = sorted_chars[i][1]
        if c.isascii() and c.isalpha():
            grp = []
            while (i < len(sorted_chars) and
                   sorted_chars[i][1].isascii() and
                   (sorted_chars[i][1].isalpha() or
                    sorted_chars[i][1] in " .'-_&\"")):
                grp.append(sorted_chars[i][1])
                i += 1
            result.extend(reversed(grp))
        elif c.isdigit() or c in './:,-':
            grp = []
            while (i < len(sorted_chars) and
                   (sorted_chars[i][1].isdigit() or
                    sorted_chars[i][1] in './:,-')):
                grp.append(sorted_chars[i][1])
                i += 1
            result.extend(reversed(grp))
        else:
            result.append(c)
            i += 1
    return "".join(result).strip()


def _line_needs_fix(chars_with_pos):
    """Détecte si les caractères arabes d'une ligne sont stockés en LTR."""
    arabic = [(x, c) for x, c in chars_with_pos if _is_rtl_char(c)]
    if len(arabic) < 3:
        return False
    return arabic[0][0] < arabic[-1][0]


def _extract_text_fixed(page, y_entete=70):
    """Extrait le texte d'une page avec correction RTL automatique."""
    data = page.get_text("rawdict")
    lignes = []

    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            if line["bbox"][1] < y_entete:
                continue

            chars = []
            for span in line["spans"]:
                for char in span.get("chars", []):
                    chars.append((char["bbox"][0], char["c"]))

            if not chars:
                continue

            has_arabic = any(_is_rtl_char(c) for _, c in chars)

            if has_arabic and _line_needs_fix(chars):
                text = _fix_line_rtl(chars)
            else:
                text = "".join(c for _, c in chars).strip()

            if text:
                lignes.append(text)

    return "\n".join(lignes)


# ══════════════════════════════════════════════════════════════
#  FONCTION PRINCIPALE
# ══════════════════════════════════════════════════════════════

def extraire_annonces_bo(pdf_path, output_path="annonces.txt", y_entete=70):

    doc = fitz.open(pdf_path)

    # ── Séparateurs ──────────────────────────────────────────
    def est_separateur_s1(l):
        l = l.strip()
        l_clean = re.sub(r'(\d)\s+(\d)', r'\1\2', l)
        return bool(re.match(r'^\d+\s*[PCI]$', l_clean))

    def est_separateur_s2(l):
        l = l.strip()
        if re.match(r'^\d+$', l):      return True
        if re.match(r'^مكرر\d+$', l):  return True
        if re.match(r'^\d+مكرر$', l):  return True
        return False

    # ── Titres de sections ───────────────────────────────────
    TITRE_I   = re.compile(r'إعالنات قانونية-?\s*\.?\s*I')
    TITRE_II  = re.compile(r'إعالنات قضائية-?\s*\.?\s*II')
    TITRE_III = re.compile(r'إعالنات إدارية-?\s*\.?\s*III')

    LIGNES_TITRE = re.compile(
        r'إعالنات قانونية وقضائية وإدارية|'
        r'إعالنات قانونية-?\s*\.?\s*I|'
        r'يلتزم املعلنون|'
        r'وال تتحمل اإلدارة'
    )

    # ── PHASE 1 : Trouver les 2èmes occurrences ──────────────
    occurrences = {'I': [], 'II': [], 'III': []}

    for page_num in range(len(doc)):
        page = doc[page_num]
        texte = _extract_text_fixed(page, y_entete)
        lignes = texte.split('\n')

        for line_num, ligne in enumerate(lignes):
            l = ligne.strip()
            if not l:
                continue
            if est_separateur_s1(l) or est_separateur_s2(l):
                continue
            if TITRE_I.search(l):
                occurrences['I'].append((page_num, line_num))
            if TITRE_II.search(l):
                occurrences['II'].append((page_num, line_num))
            if TITRE_III.search(l):
                occurrences['III'].append((page_num, line_num))

    if len(occurrences['I']) < 2:
        print("ERREUR: Section I non trouvée (2ème occurrence)")
        return [], [], []
    if len(occurrences['II']) < 2:
        print("ERREUR: Section II non trouvée (2ème occurrence)")
        return [], [], []
    if len(occurrences['III']) < 2:
        print("ERREUR: Section III non trouvée (2ème occurrence)")
        return [], [], []

    page_I,   ligne_I   = occurrences['I'][1]
    page_II,  ligne_II  = occurrences['II'][1]
    page_III, ligne_III = occurrences['III'][1]

    # Page du sommaire = entre 1ère et 2ème occurrence de Section I
    page_sommaire_debut = occurrences['I'][0][0]

    print(f"Sommaire    : page {page_sommaire_debut+1} → {page_I}")
    print(f"Section I   : page {page_I+1}  ligne {ligne_I}")
    print(f"Section II  : page {page_II+1} ligne {ligne_II}")
    print(f"Section III : page {page_III+1} ligne {ligne_III}")

    # ── EXTRACTION SOMMAIRE (Section I uniquement) ───────────
    def extraire_sommaire():
        """
        Extrait les entrées du sommaire des annonces légales.
        Le sommaire est entre la 1ère et 2ème occurrence du titre Section I.

        Le PDF a 2 colonnes. Pour chaque colonne, le format est :
          Cas 1 (latin) : NOM.................  (ligne avec des points)
                          733                  (page seule, ligne suivante)
          Cas 2 (arabe) : شركة NOM737..........  (page collée au nom)
                          → pas de ligne séparée pour le numéro

        On traite BLOC PAR BLOC (pas page entière) pour séparer
        les colonnes gauche/droite et éviter les fusions.
        """
        entries = []

        # Filtres
        FILTRE_SOMMAIRE = re.compile(
            r'صفحة|الجريدة الرسمية|عدد \d{4}|'
            r'املحكمة.{0,20}التجارية|املحكمة.{0,20}االبتدائية|'
            r'وكالة الحوض|نزع ملكية|القطع األرضية|'
            r'استدراك تعديلي|طريق التهيئة|منحدر|'
            r'الطريق السيار|بموجبه ملكية|الالزمة لهذ|'
            r'بالجريدة\s+الرسمية\s+عدد|'
            r'التابعة لقناة|'
            r'^درهم[ا]?$'
        )

        # ── Collecter les lignes BLOC PAR BLOC ──
        # Chaque bloc = une cellule dans la grille 2 colonnes
        items = []  # (pdf_page, column, y, text)

        for pn in range(page_sommaire_debut, page_I):
            page = doc[pn]
            data = page.get_text("rawdict")

            for block in data["blocks"]:
                if block["type"] != 0:
                    continue
                bx = block["bbox"][0]
                col = 0 if bx < 200 else 1

                for line in block["lines"]:
                    if line["bbox"][1] < 90:
                        continue

                    chars = []
                    for span in line["spans"]:
                        for char in span.get("chars", []):
                            chars.append((char["bbox"][0], char["c"]))

                    if not chars:
                        continue

                    has_arabic = any(_is_rtl_char(c) for _, c in chars)

                    if has_arabic and _line_needs_fix(chars):
                        text = _fix_line_rtl(chars)
                    else:
                        text = "".join(c for _, c in chars).strip()

                    if text:
                        items.append((pn, col, line["bbox"][1], text))

        # ── Traiter colonne par colonne ──
        for col in [1, 0]:  # Droite d'abord (lecture RTL)
            col_items = sorted(
                [(pn, y, t) for pn, c, y, t in items if c == col],
                key=lambda x: (x[0], x[1])
            )

            pending_name = None

            for _, _, text in col_items:
                text = text.strip()
                if not text:
                    continue

                # Filtrer en-têtes et titres
                if FILTRE_SOMMAIRE.search(text):
                    continue
                if LIGNES_TITRE.search(text) or TITRE_II.search(text) or TITRE_III.search(text):
                    continue

                # ── Cas 1 : numéro de page seul ──
                if re.match(r'^\d{3,4}$', text):
                    if pending_name:
                        entries.append({
                            "nom": pending_name,
                            "page": int(text)
                        })
                        pending_name = None
                    continue

                # Retirer les points
                nom = re.sub(r'\.{2,}', '', text).strip()
                if not nom or len(nom) <= 1:
                    continue

                # Filtrer les faux positifs après nettoyage
                if re.match(r'^درهم[ا]?$', nom):
                    continue
                if nom in ('تسيير حر', 'Maroc', 'DE TELECOMPENSATION',
                           'الغاية'):
                    continue

                # ── Cas 2 : numéro de page collé à la fin ──
                m_embedded = re.search(r'(\d{3,4})\s*$', nom)
                if m_embedded:
                    page_num = int(m_embedded.group(1))
                    nom_clean = nom[:m_embedded.start()].strip()
                    if nom_clean and len(nom_clean) > 1:
                        # Filtrer les faux noms
                        if re.match(r'^درهم[ا]?$', nom_clean):
                            continue
                        if nom_clean in ('تسيير حر',):
                            continue
                        entries.append({
                            "nom": nom_clean,
                            "page": page_num
                        })
                        pending_name = None
                        continue

                # ── Cas 3 : nom seul → attendre la page ──
                pending_name = nom

        return entries

    sommaire = extraire_sommaire()
    print(f"Sommaire    : {len(sommaire)} entrées")

    # ── EXTRACTION D'UNE SECTION ─────────────────────────────
    def extraire_section(page_debut, page_fin_max,
                         titre_fin, est_separateur,
                         lignes_a_filtrer=None):
        """
        Renvoie une liste de tuples (texte, page_debut_1indexed).
        page_debut_1indexed = numéro de page (1-based) où commence l'annonce.
        """
        annonces         = []
        annonce_courante = ""
        annonce_page     = None         # page (1-indexed) où commence l'annonce courante
        termine          = False

        def sauvegarder():
            nonlocal annonce_courante, annonce_page
            t = annonce_courante.strip()
            if t and annonce_page is not None:
                annonces.append((t, annonce_page))
            annonce_courante = ""
            annonce_page = None

        page_num = page_debut

        while page_num <= page_fin_max and not termine:
            page = doc[page_num]

            # ═══ CORRECTION RTL ═══
            texte = _extract_text_fixed(page, y_entete)
            lignes = texte.split('\n')

            for l_brut in lignes:
                l = l_brut.strip()
                if not l:
                    continue

                # Titre de fin → ARRÊT TOTAL
                if titre_fin.search(l):
                    sauvegarder()
                    termine = True
                    break

                # Filtrer les lignes de titre/entête
                if lignes_a_filtrer and lignes_a_filtrer.search(l):
                    continue

                # Séparateur → nouvelle annonce
                if est_separateur(l):
                    sauvegarder()
                    continue

                # Première ligne de la nouvelle annonce → mémoriser la page
                if not annonce_courante:
                    annonce_page = page_num + 1   # 1-indexed pour l'affichage

                annonce_courante += "\n" + l \
                                    if annonce_courante else l

            page_num += 1

        sauvegarder()
        return annonces

    # ── EXTRACTION SECTION I ─────────────────────────────────
    annonces_I = extraire_section(
        page_debut     = page_I,
        page_fin_max   = page_II,
        titre_fin      = TITRE_II,
        est_separateur = est_separateur_s1,
        lignes_a_filtrer = LIGNES_TITRE
    )

    # ── EXTRACTION SECTION II ────────────────────────────────
    LIGNES_TITRE_II = re.compile(
        r'إعالنات قضائية-?\s*\.?\s*II'
    )

    annonces_II = extraire_section(
        page_debut     = page_II,
        page_fin_max   = page_III - 1,
        titre_fin      = TITRE_III,
        est_separateur = est_separateur_s2,
        lignes_a_filtrer = LIGNES_TITRE_II
    )

    doc.close()

    # ── ÉCRITURE (optionnelle : output_path=None pour ne rien écrire) ──
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:

            # ── SOMMAIRE ──
            f.write("=" * 60 + "\n")
            f.write("SOMMAIRE — فهرس اإلعالنات القانونية\n")
            f.write("=" * 60 + "\n\n")
            for entry in sommaire:
                f.write(f"{entry['nom']}\t{entry['page']}\n")
            f.write("\n")

            # ── SECTION I ──
            f.write("=" * 60 + "\n")
            f.write("SECTION I — إعلانات قانونية (Annonces Légales)\n")
            f.write("=" * 60 + "\n\n")
            for annonce, page in annonces_I:
                f.write(f"[page {page}]\n")
                f.write(annonce)
                f.write("\n" + "-" * 50 + "\n\n")

            # ── SECTION II ──
            f.write("=" * 60 + "\n")
            f.write("SECTION II — إعلانات قضائية (Annonces Judiciaires)\n")
            f.write("=" * 60 + "\n\n")
            for annonce, page in annonces_II:
                f.write(f"[page {page}]\n")
                f.write(annonce)
                f.write("\n" + "-" * 50 + "\n\n")

    # ── STATISTIQUES ─────────────────────────────────────────
    total = len(annonces_I) + len(annonces_II)
    print(f"Sommaire             : {len(sommaire)} entrées")
    print(f"Section I  (légales)     : {len(annonces_I)} annonces")
    print(f"Section II (judiciaires) : {len(annonces_II)} annonces")
    print(f"Total                    : {total} annonces")
    if output_path:
        print(f"Fichier                  : {output_path}")

    return sommaire, annonces_I, annonces_II


if __name__ == "__main__":
    PDF_PATH    = "bo20.pdf"
    OUTPUT_PATH = "annonces20.txt"

    if not os.path.exists(PDF_PATH):
        print(f"Fichier non trouvé : {PDF_PATH}")
    else:
        extraire_annonces_bo(PDF_PATH, OUTPUT_PATH)