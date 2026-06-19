# Pipeline d'extraction du bulletin → entreprise → partenaire

Détail bout-en-bout : du PDF brut jusqu'à l'alerte liant une annonce à un
**partenaire Plastima (tier)**.

Code de référence :
- Extraction : `../ml/extraction/extraction_pdf.py`
- Orchestration : `../backend/services/pipeline.py` (`traiter_bulletin`)
- Traduction : `../ml/translation/translation.py`
- Similarité : `../ml/similarite/similarite.py`

```
PDF BOAL
  │  ÉTAPE 0 — EXTRACTION (PyMuPDF, regex)
  │    0.1 lecture page par page + correction RTL
  │    0.2 repérage des sections (sommaire / I / II / III)
  │    0.3 découpage en annonces via séparateurs
  ▼
[Section I légales]   [Section II judiciaires]
  │                         │
  │  ÉTAPE 1   M1 classification (type)
  │  ÉTAPE 2   M2 NER (nom entreprise)         M2 NER (nom) + regex (procédure, tribunal)
  ▼                         ▼
  └──────────► ÉTAPE 3 — TRADUCTION nom AR → FR (deep-translator)
                          │
                          ▼
              ÉTAPE 4 — M3 SIMILARITÉ vs TIERS (partenaires Plastima)
                          │
                          ▼
              ÉTAPE 5 — ALERTE si score ≥ seuil
```

---

## ÉTAPE 0 — Extraction du texte du bulletin

Fichier : `extraire_annonces_bo(pdf_path)`. Aucun modèle ML — PyMuPDF + regex.

### 0.1 Lecture page par page + correction RTL

Le BO est en arabe (RTL). Problème : certains PDF stockent les caractères arabes
en ordre **LTR inversé**. `_extract_text_fixed()` :
1. lit chaque page en `rawdict` (chaque caractère avec sa position `x`) ;
2. ignore l'en-tête (`y < y_entete`, défaut 70) ;
3. `_line_needs_fix()` détecte si l'arabe est stocké à l'envers (premier
   caractère arabe à gauche du dernier) ;
4. si oui, `_fix_line_rtl()` reconstruit la ligne en triant les caractères par
   `x` décroissant, tout en gardant les **groupes latins et numériques** dans
   le bon sens (entreprises à nom français, montants, dates).

### 0.2 Repérage de la structure du bulletin

Le BO a 3 sections, chaque titre apparaît **2 fois** (sommaire puis corps) :
- `TITRE_I` = `إعلانات قانونية` (annonces légales) ;
- `TITRE_II` = `إعلانات قضائية` (annonces judiciaires) ;
- `TITRE_III` = `إعلانات إدارية` (annonces administratives).

On prend la **2ᵉ occurrence** de chaque titre = début réel de la section.
Si une section n'a pas 2 occurrences → `return [], [], []` (bulletin invalide,
marqué `erreur` en aval).

Bornes obtenues :
- **Sommaire** = entre 1ʳᵉ et 2ᵉ occurrence de Section I ;
- **Section I** = page_I → page_II ;
- **Section II** = page_II → page_III.

### 0.3 Extraction du sommaire (table des matières)

`extraire_sommaire()` lit la grille **2 colonnes** (bloc par bloc, colonne
droite d'abord car RTL) et produit des paires `{nom, page}`. Gère 3 cas :
- nom suivi du numéro de page sur la ligne suivante ;
- numéro de page **collé** à la fin du nom (`شركة NOM737`) ;
- nom seul en attente de sa page.
Filtres anti-bruit (en-têtes « الجريدة الرسمية », « درهم », tribunaux…).

> Le sommaire sert d'index/repère ; les annonces traitées par les modèles
> viennent des sections I et II, pas du sommaire.

### 0.4 Découpage en annonces individuelles

`extraire_section()` parcourt les pages de la section et **coupe à chaque
séparateur** :
- **Section I** — `est_separateur_s1` : ligne du type `733 P`, `12 C`, `45 I`
  (numéro d'annonce + lettre de rubrique) ;
- **Section II** — `est_separateur_s2` : numéro seul (`733`) ou variantes
  `مكرر` (bis).

Chaque annonce = bloc de texte accumulé entre deux séparateurs + le **numéro de
page** (1-indexé) où elle commence. Arrêt total dès le titre de la section
suivante. Retour :
- `annonces_I` : `[(texte, page), …]` → table `ArticleEntreprise`
- `annonces_II` : `[(texte, page), …]` → table `ArticleMahakim`

Si `annonces_I` et `annonces_II` sont vides → ce n'est pas une édition BOAL →
bulletin `erreur`.

---

## ÉTAPES 1-2 — Détection type + nom (par annonce)

Voir `README.md` (section « Comment ça marche ») pour le détail des modèles.
Résumé :
- **Section I** : `classifier()` (M1) → type (`création`/`modification`/
  `cession`/`liquidation`) ; `extraire_nom_ner()` (M2) → nom entreprise.
- **Section II** : `extraire_nom_ner()` (M2) → nom ; `extraire_type_procedure()`
  (regex) → procédure judiciaire ; `extraire_tribunal()` (regex) → tribunal.

Le nom détecté (`nom_brut`) est stocké dans `nom_entreprise` avec son
`score_ner`, et `source_nom = "ner"`.

---

## ÉTAPE 3 — Traduction du nom (arabe → français)

`preparer_nom_pour_similarite(nom_brut)` (`translation.py`) :
1. supprime les formes juridiques arabes (`ش.م.م`, `شركة ذات…`, `شركة`…) ;
2. translittère/traduit l'arabe restant en français via **deep-translator**
   (Google Translate, sans clé API) ;
3. robustesse : cache mémoire (mêmes noms répétés dans un bulletin), circuit
   breaker (3 échecs réseau → désactivation propre), 1 seule tentative.

`reset_translator_state()` est appelé entre deux bulletins (vide cache +
breaker). Si réseau down → renvoie le nom arabe nettoyé (dégradation gracieuse).

Pourquoi traduire : les **tiers Plastima sont stockés en français/latin**
(`Tier.nom`, `Tier.nom_normalise`). Pour comparer, il faut ramener le nom
détecté dans le même alphabet.

---

## ÉTAPE 4 — Rattachement à un partenaire (TIER)

C'est ici que « l'entreprise détectée » est reliée à « un partenaire connu ».

### Qu'est-ce qu'un tier ?

Table `Tier` (`backend/models.py`) = partenaires/clients/fournisseurs de
Plastima à surveiller :
`id`, `nom`, `nom_normalise`, `type_tier`, `secteur`, `ville`, `rc_numero`,
`actif`. Seuls les `actif = True` sont chargés une fois par bulletin.

Les tiers **ne sont pas détectés dans le PDF** — ils préexistent en base. Le
bulletin fournit des entreprises ; on cherche lesquelles **correspondent** à un
tier.

### Comparaison (Modèle 3 — `comparer(nom_fr, tiers, seuil)`)

Pour le nom détecté vs chaque tier :

**a) Normalisation** (`normaliser`) : retire caractères invisibles, formes
juridiques (SARL, STE, GROUPE…), ponctuation, met en MAJUSCULES.

**b) Pré-filtre rapidfuzz** (rapide, écarte les paires évidentes ≠) :
- `WRatio ≥ 60` (ou `≥ 80` si un nom fait < 5 caractères → anti faux positifs
  sur sigles type « EMT ») ;
- `token_set_ratio ≥ 40` (anti faux positif par sous-chaîne, ex.
  « DESIRS » vs « …DIVERS »).

**c) 7 features** (`calculer_features`) sur les survivants :
`levenshtein_ratio`, `token_sort_ratio`, `token_set_ratio`, `partial_ratio`,
`diff_longueur`, `jaccard_mots`, `premier_mot_identique`.

**d) Random Forest** (`predict_proba`, un seul batch pour tous les candidats →
50-100× plus rapide) renvoie `P(match)`. Fallback moyenne pondérée rapidfuzz si
le modèle n'est pas chargé.

**e) Seuil** : on garde les tiers avec `score ≥ SEUIL_SIMILARITE`, triés par
score décroissant. Résultat :
`[{tier_id, nom_tier, score}, …]`.

C'est ainsi qu'« STORABI SARL » détecté dans le bulletin est relié au
partenaire « STORABI » malgré la forme juridique et les variantes d'écriture.

---

## ÉTAPE 5 — Création de l'alerte

Pour chaque match tier↔annonce → une `Alerte` :
- lien vers le tier (`tier_id`) et vers l'article
  (`article_entreprise_id` ou `article_mahakim_id`) ;
- `nom_detecte` (FR), `nom_tier`, `score_similarite` ;
- `type_annonce` (Section I : type M1 ; Section II : `"judiciaire"`) ;
- `priorite` automatique (`determiner_priorite`) :
  - Section I : `liquidation` → **haute**, `cession` → **moyenne**, sinon **basse** ;
  - Section II : toujours **haute**.

Une annonce sans nom détecté, ou dont aucun tier ne dépasse le seuil, est quand
même enregistrée (article en base) mais **ne génère pas d'alerte**.

---

## Récapitulatif — qui fait quoi

| Étape | Entrée → Sortie | Méthode |
|-------|------------------|---------|
| 0.1 RTL | page PDF → lignes texte correctes | PyMuPDF + tri par position x |
| 0.2 structure | bulletin → bornes sections | regex titres (2ᵉ occurrence) |
| 0.3 sommaire | pages sommaire → `{nom, page}` | regex 2 colonnes |
| 0.4 découpage | section → annonces `(texte, page)` | regex séparateurs |
| 1 type (légales) | texte → création/modif/cession/liquidation | **M1** |
| 2 nom | texte → nom entreprise | **M2 CAMeL-BERT** |
| 2′ procédure/tribunal (jud.) | texte → procédure, tribunal | regex |
| 3 traduction | nom AR → nom FR | deep-translator |
| 4 partenaire | nom FR + tiers → matchs | **M3 Random Forest** |
| 5 alerte | match → Alerte + priorité | code |
