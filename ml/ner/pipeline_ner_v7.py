#!/usr/bin/env python3
# ============================================================
# LegalEye — Pipeline NER v7
# ============================================================
# Corrections v7 :
# - Fusion lignes latines fragmentées (AVANT NER)
# - Filtrage noms vides, courts, génériques
# - Sélection intelligente meilleure entité
# - Gestion erreurs robuste par annonce
# - Parsing sommaire multi-format (TAB + PIPE)
# ============================================================

import re
import csv
import sys
import os
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════

MODEL_PATH = "/Users/marouan_rhazlani/Desktop/ner_camel_v5"
LABELS     = ["O", "B-NOM_ENT", "I-NOM_ENT"]
ID2LABEL   = {i: l for i, l in enumerate(LABELS)}

MOTS_GENERIQUES = {
    'PHARMACIE', 'ASSURANCE', 'SARL', 'SA', 'SNC', 'SAS',
    'STE', 'SOCIETE', 'SOCIÉTÉ', 'UM', 'VQ', 'AU',
    'LA', 'LE', 'DE', 'DU', 'ET', 'LES', 'DES',
    'محكمة', 'المحكمة', 'شركة', 'إعالن', 'إشعار',
    'بمقتضى', 'بمقتغضى', 'بموجب',
}

FORMES_JUR = re.compile(
    r"\b(?:SARL[\s\-]*AU|SARLAU|SARL|S\.A\.R\.L\.?(?:\s*A\.?U\.?)?|"
    r"SA|SNC|SAS|SCS|FZ-LLC|LLC)\b"
    r"|ش\.?\s*م\.?\s*م|ش\.?\s*ذ\.?\s*م\.?\s*م"
    r"|شركة\s*ذات|شركة",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════
#  CHARGEMENT DU MODÈLE
# ══════════════════════════════════════════════════════════════

def charger_modele(model_path):
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForTokenClassification.from_pretrained(model_path)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    model.to(device)
    model.eval()
    print(f"  Modèle  : {model_path}")
    print(f"  Device  : {device}")
    return model, tokenizer, device


# ══════════════════════════════════════════════════════════════
#  PRÉTRAITEMENT — Fusion lignes fragmentées
# ══════════════════════════════════════════════════════════════

def prefusionner_texte(texte):
    """
    Fusionne les lignes latines consécutives fragmentées par PyMuPDF.

    AVANT :                    APRÈS :
    "GRANDE                    "GRANDE PHARMACIE SARL
    PHARMACIE                   تأسيس شركة..."
    SARL
    تأسيس شركة..."
    """
    lignes = texte.split('\n')
    result = []
    buffer = []

    for ligne in lignes:
        l = ligne.strip()
        if not l:
            if buffer:
                result.append(' '.join(buffer))
                buffer = []
            continue

        nb_latin = len(re.findall(r'[A-Za-z]', l))
        nb_arabe = len(re.findall(r'[\u0600-\u06FF]', l))

        if nb_latin > 0 and nb_latin >= nb_arabe:
            buffer.append(l)
        else:
            if buffer:
                result.append(' '.join(buffer))
                buffer = []
            result.append(l)

    if buffer:
        result.append(' '.join(buffer))

    return '\n'.join(result)


# ══════════════════════════════════════════════════════════════
#  NETTOYAGE ET VALIDATION DE NOM
# ══════════════════════════════════════════════════════════════

def nettoyer_nom(nom):
    if not nom:
        return ""
    clean = FORMES_JUR.sub("", nom).strip()
    clean = re.sub(r"^(?:STE|Sté\.?|SOCIETE|SOCIÉTÉ)\s+", "", clean, flags=re.I)
    clean = re.sub(r"^[\s\-:\.«»\"\'\(\)،,]+", "", clean)
    clean = re.sub(r"[\s\-:\.«»\"\'\(\)،,]+$", "", clean)
    clean = clean.replace('\ufeff', '').replace('\u00a0', ' ')
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def valider_nom(nom):
    nom = nettoyer_nom(nom)
    if not nom:
        return None
    if len(nom) < 3:
        return None
    if nom.upper() in MOTS_GENERIQUES:
        return None
    if nom.replace(' ', '').isdigit():
        return None
    if re.match(r'^[\s\.\-\:\,\;\!\?\(\)«»\"\']+$', nom):
        return None
    if nom.startswith('محكمة') or nom.startswith('المحكمة'):
        return None
    if len(nom) > 60:
        nom = nom[:60].rsplit(' ', 1)[0]
    return nom


# ══════════════════════════════════════════════════════════════
#  NER MODEL — Prédiction
# ══════════════════════════════════════════════════════════════

def predict_ner(texte, model, tokenizer, device):
    mots = texte.strip().split()
    if not mots:
        return []

    try:
        encoding = tokenizer(
            mots,
            is_split_into_words=True,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=False,
        )
        inputs = {k: v.to(device) for k, v in encoding.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            logits  = outputs.logits
            preds   = torch.argmax(logits, dim=-1)[0].cpu().tolist()
            probs   = torch.softmax(logits, dim=-1).max(dim=-1).values[0].cpu().tolist()

        word_ids   = encoding.word_ids(batch_index=0)
        mot_labels = {}
        mot_scores = {}
        for tok_idx, word_idx in enumerate(word_ids):
            if word_idx is not None and word_idx not in mot_labels:
                mot_labels[word_idx] = ID2LABEL[preds[tok_idx]]
                mot_scores[word_idx] = probs[tok_idx]

        entites = []
        current, scores = [], []
        for idx in range(len(mots)):
            label = mot_labels.get(idx, "O")
            score = mot_scores.get(idx, 0.0)
            if label == "B-NOM_ENT":
                if current:
                    entites.append({
                        "nom":   " ".join(current),
                        "score": sum(scores) / len(scores),
                    })
                current, scores = [mots[idx]], [score]
            elif label == "I-NOM_ENT" and current:
                current.append(mots[idx])
                scores.append(score)
            else:
                if current:
                    entites.append({
                        "nom":   " ".join(current),
                        "score": sum(scores) / len(scores),
                    })
                current, scores = [], []
        if current:
            entites.append({
                "nom":   " ".join(current),
                "score": sum(scores) / len(scores),
            })

        entites_valides = []
        for e in entites:
            if e["score"] < 0.3:
                continue
            nom_v = valider_nom(e["nom"])
            if nom_v:
                e["nom"] = nom_v
                entites_valides.append(e)

        entites_valides.sort(key=lambda x: -x["score"])
        return entites_valides

    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
#  SÉLECTION MEILLEURE ENTITÉ
# ══════════════════════════════════════════════════════════════

def choisir_meilleure_entite(entites, sommaire_norms=None):
    if not entites:
        return None

    if sommaire_norms:
        for e in entites:
            match = verifier_sommaire(e["nom"], sommaire_norms)
            if match:
                return {"nom": match, "score": e["score"], "source": "sommaire"}

    best = entites[0]
    return {"nom": best["nom"], "score": best["score"], "source": "ner"}


# ══════════════════════════════════════════════════════════════
#  REGEX — Section II
# ══════════════════════════════════════════════════════════════

def regex_judiciaire(texte):
    if re.search(r"في\s+حق\s+(?:السيد|السيدة|التاجر|التاجرة)\s", texte):
        if not re.search(r"في\s+حق\s+شركة", texte):
            return None

    patterns = [
        r"في\s+حق\s+شركة\s+([\u0600-\u06FF][\u0600-\u06FF\s]+?)(?:\s+(?:ذات|املسجلة|رقم|بالسجل|تحت|ش[\.\s]|SARL|SA\b))",
        r"في\s+حق\s+شركة\s+([A-Z][\w\s\-&\.]+?)(?:\s+(?:ذات|املسجلة|رقم|بالسجل|تحت|ش[\.\s]|SARL|SA\b))",
        r"لفائدة\s+شركة\s+([\u0600-\u06FF][\u0600-\u06FF\s]+?)(?:\s+(?:ذات|شركة|املسجلة|رقم|SARL|SA\b))",
        r"لفائدة\s+شركة\s+([A-Z][\w\s\-&\.]+?)(?:\s+(?:ذات|شركة|املسجلة|رقم|SARL|SA\b))",
        r"الشركة\s+املسماة\s+([A-Z][\w\s\-&\.]+?)(?:\s+(?:SARL|SA\b|S\.A|شركة|ش\.م|ممثلة|رقم))",
        r"الشركة\s+املسماة\s+[«\"]+(.+?)[»\"]+",
        r"(?:باعت?|فوتت?)\s+شركة\s+([\u0600-\u06FF][\u0600-\u06FF\s]+?)(?:\s+(?:ذات|شركة|املسجلة|رقم|لفائدة|SARL|SA\b))",
        r"(?:باعت?|فوتت?)\s+شركة\s+([A-Z][\w\s\-&\.]+?)(?:\s+(?:ذات|شركة|املسجلة|رقم|لفائدة|SARL|SA\b))",
        r"(?:الى|إلى)\s+شركة\s+([A-Z][\w\s\-&\.]+?)(?:\s+(?:شركة|ذات|SARL|SA\b|S\.A))",
        r"شركة\s+[«\"]([\u0600-\u06FF\s]+?)[»\"]",
        r"شركة\s+[«\"]([A-Z][\w\s\-&\.]+?)[»\"]",
        r"لشركة\s+[«\"]([\u0600-\u06FF\s]+?)[»\"]",
        r"لشركة\s+[«\"]([A-Z][\w\s\-&\.]+?)[»\"]",
    ]

    for p in patterns:
        m = re.search(p, texte)
        if m:
            nom = valider_nom(m.group(1))
            if nom:
                return nom

    excl = MOTS_GENERIQUES
    for bloc in re.findall(r"\b([A-Z][A-Z\s\-&\.]{2,})\b", texte):
        mots = [m for m in bloc.split() if m not in excl and len(m) > 1]
        if mots:
            nom = valider_nom(" ".join(mots))
            if nom:
                return nom

    return None


# ══════════════════════════════════════════════════════════════
#  PARSING annonces.txt
# ══════════════════════════════════════════════════════════════

def lire_annonces(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("=" * 60)

    sommaire_text = ""
    section1_text = ""
    section2_text = ""

    for i, part in enumerate(parts):
        if "SOMMAIRE" in part:
            if i + 1 < len(parts):
                sommaire_text = parts[i + 1]
        elif "SECTION II" in part:
            if i + 1 < len(parts):
                section2_text = parts[i + 1]
        elif "SECTION I" in part:
            if i + 1 < len(parts):
                section1_text = parts[i + 1]

    sommaire = []
    for line in sommaire_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        p = line.split("\t")
        if len(p) == 2:
            try:
                sommaire.append({"nom": p[0].strip(), "page": int(p[1])})
            except ValueError:
                continue
        elif " | page " in line:
            parts_line = line.split(" | page ")
            if len(parts_line) == 2:
                try:
                    sommaire.append({
                        "nom":  parts_line[0].strip(),
                        "page": int(parts_line[1].strip())
                    })
                except ValueError:
                    continue

    sep = "-" * 50
    annonces_I  = [a.strip() for a in section1_text.split(sep) if a.strip()]
    annonces_II = [a.strip() for a in section2_text.split(sep) if a.strip()]

    return sommaire, annonces_I, annonces_II


# ══════════════════════════════════════════════════════════════
#  VÉRIFICATION SOMMAIRE
# ══════════════════════════════════════════════════════════════

def _norm(text):
    return re.sub(r"\W+", " ", text).strip().upper()


def verifier_sommaire(nom_ner, sommaire_norms):
    nom_n = _norm(nom_ner)
    if not nom_n or len(nom_n) < 3:
        return None

    words = nom_n.split()

    for nom_s, nom_s_norm in sommaire_norms:
        if nom_n == nom_s_norm:
            return nom_s
        if nom_n in nom_s_norm or nom_s_norm in nom_n:
            return nom_s
        if len(words) >= 2:
            partial = words[0] + " " + words[1]
            if partial in nom_s_norm:
                return nom_s
        if len(words) >= 1 and len(words[0]) >= 5:
            if words[0] in nom_s_norm:
                return nom_s

    return None


# ══════════════════════════════════════════════════════════════
#  PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def pipeline_ner(input_path, output_csv=None, model_path=MODEL_PATH):

    if output_csv is None:
        base = os.path.splitext(input_path)[0]
        output_csv = base + "_ner.csv"

    print("=" * 60)
    print("  LegalEye Pipeline NER v7")
    print("=" * 60)

    model, tokenizer, device = charger_modele(model_path)

    sommaire, annonces_I, annonces_II = lire_annonces(input_path)
    print(f"  Sommaire       : {len(sommaire)} entrées")
    print(f"  Section I      : {len(annonces_I)} annonces")
    print(f"  Section II     : {len(annonces_II)} annonces")

    sommaire_norms = [(e["nom"], _norm(e["nom"])) for e in sommaire]
    csv_rows = []

    # ══════════════════════════════════════════════════════
    # SECTION I : fusion + NER + sommaire
    # ══════════════════════════════════════════════════════
    print("\n  [1/2] Section I : NER + sommaire...")
    stats_I = {"haute": 0, "moyenne": 0, "sommaire": 0, "basse": 0, "erreur": 0}

    for ann in annonces_I:
        try:
            ann_fusionne = prefusionner_texte(ann)
            entites = predict_ner(ann_fusionne[:1500], model, tokenizer, device)
            best = choisir_meilleure_entite(entites, sommaire_norms)

            if best:
                nom_final = valider_nom(best["nom"])
                if nom_final:
                    confiance = "haute" if best["source"] == "sommaire" else "moyenne"
                    csv_rows.append({
                        "section":   "I",
                        "nom":       nom_final,
                        "confiance": confiance,
                        "annonce":   ann,
                    })
                    stats_I[confiance] += 1
                    continue

            premiere_ligne = ann.split("\n")[0].strip()
            premiere_fusionne = prefusionner_texte(premiere_ligne)
            nom_sommaire = verifier_sommaire(premiere_fusionne, sommaire_norms)
            if nom_sommaire:
                nom_final = valider_nom(nom_sommaire)
                if nom_final:
                    csv_rows.append({
                        "section":   "I",
                        "nom":       nom_final,
                        "confiance": "sommaire",
                        "annonce":   ann,
                    })
                    stats_I["sommaire"] += 1
                    continue

            nom_final = valider_nom(premiere_fusionne)
            if nom_final:
                csv_rows.append({
                    "section":   "I",
                    "nom":       nom_final,
                    "confiance": "basse",
                    "annonce":   ann,
                })
                stats_I["basse"] += 1

        except Exception:
            stats_I["erreur"] += 1

    for k, v in stats_I.items():
        if v > 0:
            print(f"         {k:10s} : {v}")

    # ══════════════════════════════════════════════════════
    # SECTION II : fusion + NER + regex
    # ══════════════════════════════════════════════════════
    print("  [2/2] Section II : NER + regex...")
    stats_II = {"haute": 0, "regex": 0, "ner_seul": 0, "sans": 0, "erreur": 0}

    for ann in annonces_II:
        try:
            ann_fusionne = prefusionner_texte(ann)

            entites = predict_ner(ann_fusionne[:1500], model, tokenizer, device)
            nom_ner = None
            if entites:
                nom_ner = valider_nom(entites[0]["nom"])

            nom_regex = regex_judiciaire(ann_fusionne)

            if nom_ner and nom_regex:
                csv_rows.append({
                    "section":   "II",
                    "nom":       nom_regex,
                    "confiance": "haute",
                    "annonce":   ann,
                })
                stats_II["haute"] += 1

            elif nom_regex:
                csv_rows.append({
                    "section":   "II",
                    "nom":       nom_regex,
                    "confiance": "regex",
                    "annonce":   ann,
                })
                stats_II["regex"] += 1

            elif nom_ner:
                csv_rows.append({
                    "section":   "II",
                    "nom":       nom_ner,
                    "confiance": "ner_seul",
                    "annonce":   ann,
                })
                stats_II["ner_seul"] += 1

            else:
                stats_II["sans"] += 1

        except Exception:
            stats_II["erreur"] += 1

    for k, v in stats_II.items():
        if v > 0:
            print(f"         {k:10s} : {v}")

    # ── Écrire le CSV ──
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "section", "nom", "confiance", "annonce",
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    # ── Statistiques finales ──
    total_I  = sum(stats_I.values()) - stats_I["erreur"]
    total_II = sum(stats_II.values()) - stats_II["erreur"]
    trouves_I  = stats_I['haute'] + stats_I['moyenne'] + stats_I['sommaire']
    trouves_II = stats_II['haute'] + stats_II['regex'] + stats_II['ner_seul']

    print(f"\n  Résultats :")
    print(f"    Section I  : {trouves_I}/{total_I} noms trouvés ({trouves_I/total_I*100:.1f}%)" if total_I else "")
    print(f"    Section II : {trouves_II}/{total_II} noms trouvés ({trouves_II/total_II*100:.1f}%)" if total_II else "")
    print(f"    Erreurs    : {stats_I['erreur'] + stats_II['erreur']}")
    print(f"  CSV : {output_csv} ({len(csv_rows)} lignes)")
    print("=" * 60)

    return csv_rows


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":

    INPUT_PATH  = "/Users/marouan_rhazlani/Desktop/BO_mar/BO/annonces5.txt"
    OUTPUT_PATH = "/Users/marouan_rhazlani/Desktop/BO_mar/BO/annonces5_ner.csv"

    if len(sys.argv) >= 2:
        INPUT_PATH = sys.argv[1]
    if len(sys.argv) >= 3:
        OUTPUT_PATH = sys.argv[2]

    if not os.path.exists(INPUT_PATH):
        print(f"Fichier non trouvé : {INPUT_PATH}")
        sys.exit(1)

    pipeline_ner(INPUT_PATH, OUTPUT_PATH)
