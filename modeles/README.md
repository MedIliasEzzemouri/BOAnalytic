# Modèles — Pipeline LegalEye

> Modèles **entraînés** (artefacts prêts à l'inférence). Le code d'entraînement est dans `../ml/`.
> Le pipeline de production qui les charge : `../backend/services/pipeline.py`.

LegalEye utilise **3 modèles**, un par tâche. Un seul vient de HuggingFace
(le NER arabe) ; les deux autres sont des modèles scikit-learn entraînés à partir
de zéro (pas de nom HuggingFace).

| # | Tâche | Modèle | Base HuggingFace | Score |
|---|-------|--------|------------------|-------|
| 1 | Classification des annonces | TF-IDF + LinearSVC | — (scikit-learn) | Accuracy 97.12 % · F1 macro 97.11 % · CV 97.14 % ± 0.5 % |
| 2 | NER (extraction nom d'entreprise) | CAMeL-BERT fine-tuné | `CAMeL-Lab/bert-base-arabic-camelbert-msa-ner` | F1 94.5 % (P 94.1 % · R 95.0 %) |
| 3 | Similarité de noms (déduplication) | Random Forest (v4) | — (scikit-learn) | Accuracy 98.84 % · F1 CV 97.5 % · adversarial 7/9 |

**Flux du pipeline :** PDF → texte (PyMuPDF) → **M1** filtre → **M2** extrait le nom → **M3** déduplique → base de données.

---

## Modèle 1 — Classification

- **Dossier :** `classification/` (`modele_classification.pkl`, `tfidf_vectorizer.pkl`)
- **Ce qu'il fait :** classe chaque annonce légale dans l'une des 4 catégories :
  `cession`, `création`, `liquidation`, `modification`. Sert à filtrer et router les annonces.
- **Type :** TF-IDF (char n-grammes `char_wb`, n-gram 2–4, 20 000 features) → LinearSVC.
- **HuggingFace :** aucun. scikit-learn pur.
- **Données :** 9 600 train / 2 400 test (`entreprises_articles.csv`).
- **Pourquoi pas un transformer :** signal lexical fort, classes peu nombreuses →
  un modèle linéaire suffit, plus rapide sur CPU, entraînable sur peu de données.

## Modèle 2 — NER (le seul modèle HuggingFace)

- **Dossier :** `ner_camel_v5/` (`model.safetensors`, `config.json`, tokenizer)
- **Ce qu'il fait :** repère le **span exact du nom d'entreprise** (`NOM_ENT`) dans le
  texte arabe de l'annonce. Étiquetage par token : `B-NOM_ENT` / `I-NOM_ENT` / `O`.
- **Type :** BERT arabe (token classification), fine-tuné.
- **HuggingFace :** `CAMeL-Lab/bert-base-arabic-camelbert-msa-ner`
- **Données :** 1 713 annotations BIO ; `class_weights` 20× sur les entités
  (méthode `is_split_into_words=True` + `word_ids()`).
- **Pourquoi ce modèle :** le texte source est de l'arabe MSA (Bulletin Officiel
  marocain). CAMeL-BERT est pré-entraîné nativement sur de l'arabe ; la variante
  `msa` correspond au registre des bulletins légaux ; le checkpoint `-ner` fournit
  déjà une tête de classification de tokens. Tourne en local sur CPU — aucun appel API.

## Modèle 3 — Similarité

- **Dossier :** `similarite/` (`similarite_rf.pkl`)
- **Ce qu'il fait :** décide si deux noms désignent **la même entreprise**
  (ex. « STE MISTRALPRO SARL » vs « MISTRALPRO SARLAU ») → déduplication et
  rattachement des annonces à une seule entité.
- **Type :** Random Forest (500 arbres, profondeur 15, `class_weight=balanced`).
- **HuggingFace :** aucun. scikit-learn pur.
- **Features (rapidfuzz) :** `levenshtein_ratio`, `token_sort_ratio`,
  `token_set_ratio`, `partial_ratio`, `diff_longueur`, `jaccard_mots`,
  `premier_mot_identique`.
- **Données :** 10 362 paires (685 partenaires source), dont 1 649 paires confusables
  détectées automatiquement (v4).

---

## Comment ça marche — pipeline de détection

Code de référence : `../backend/services/pipeline.py` → `traiter_bulletin()`.

### Vue d'ensemble

```
PDF du Bulletin Officiel
   │
   ▼
[0] EXTRACTION (PyMuPDF)  ──►  découpe le texte en annonces
   │                            • Section I  = annonces légales
   │                            • Section II = annonces judiciaires (Mahakim)
   ▼
┌─────────────────────────────┐        ┌─────────────────────────────┐
│  SECTION I (légales)        │        │  SECTION II (judiciaires)   │
│                             │        │                             │
│ [1] M1 → TYPE               │        │ [3] M2 → NOM entreprise     │
│     (création / modif /     │        │ [4] regex → TYPE procédure  │
│      cession / liquidation) │        │     (liquidation jud. /     │
│ [2] M2 → NOM entreprise     │        │      faillite / saisie...)  │
│                             │        │ [5] regex → TRIBUNAL        │
└──────────────┬──────────────┘        └──────────────┬──────────────┘
               │                                       │
               └──────────────┬────────────────────────┘
                              ▼
              [6] M3 → SIMILARITÉ avec les TIERS (partenaires Plastima)
                              │
                              ▼
              [7] si match ≥ seuil  ──►  crée une ALERTE (+ priorité)
```

### Étape par étape

**[0] Extraction (PyMuPDF, pas un modèle)**
`extraire_annonces_bo()` lit le PDF, suit le sommaire et découpe le texte en
annonces individuelles, réparties en deux sections :
- **Section I — annonces légales** → table `ArticleEntreprise`
- **Section II — annonces judiciaires (tribunaux)** → table `ArticleMahakim`

Si 0 annonce extraite → le PDF n'est pas une édition BOAL (mauvais document) →
bulletin marqué `erreur`.

**[1] Détecter le TYPE d'une annonce légale — Modèle 1 (classification)**
`classifier(texte)` :
1. nettoie le texte (retire chiffres latins + arabes, ponctuation) ;
2. TF-IDF transforme le texte en vecteur de n-grammes de caractères ;
3. LinearSVC prédit **une des 4 classes** : `création`, `modification`,
   `cession`, `liquidation` ;
4. un score de confiance est reconstruit (softmax sur `decision_function`,
   car LinearSVC n'a pas de `predict_proba`).

> ⚠️ Il n'existe **pas** de classe « incendie / fuite ». Pour les annonces
> légales le type est strictement l'une des 4 valeurs ci-dessus. Les événements
> de type judiciaire (liquidation judiciaire, faillite…) viennent de la
> Section II, voir étape [4].

**[2] Détecter le NOM de l'entreprise — Modèle 2 (CAMeL-BERT, NER)**
`extraire_nom_ner(texte)` :
1. fusionne les lignes latines fragmentées par PyMuPDF ;
2. découpe en mots, passe au tokenizer (`is_split_into_words=True`) ;
3. CAMeL-BERT prédit un label **par token** : `B-NOM_ENT` (début du nom),
   `I-NOM_ENT` (suite du nom), `O` (hors entité) ;
4. les tokens sont regroupés en mots via `word_ids()`, puis les séquences
   `B + I…` sont assemblées en noms candidats, chacun avec un score moyen ;
5. `_nettoyer_nom()` retire les caractères invisibles (BOM, ZWSP…) et les
   **formes juridiques** (SARL, SA, شركة, ش.م.م…) ;
6. on garde le premier nom dont le score > 0.3.

C'est **comme ça que le modèle « sait » qu'un bout de texte est une entreprise** :
il a appris, sur 1 713 annonces annotées, à reconnaître la position d'un nom
d'entité dans la phrase arabe (contexte gauche/droite), pas juste des mots-clés.

**[3] NOM en Section II** → même fonction `extraire_nom_ner()` (Modèle 2).

**[4] TYPE de procédure judiciaire — regex (pas un modèle)**
`extraire_type_procedure(texte)` cherche des mots-clés arabes et renvoie :
`tsfiya_qadaiya` (liquidation judiciaire), `taswiya_qadaiya` (redressement),
`difficultes`, `faillite`, `dissolution_liquidation`, `liquidation`, `saisie`.

**[5] TRIBUNAL — regex (pas un modèle)**
`extraire_tribunal(texte)` capture « المحكمة التجارية بـ X » /
« المحكمة الابتدائية بـ X ».

**[6] Le rôle des TIERS — Modèle 3 (similarité)**
Les **tiers** sont les **partenaires/clients de Plastima** stockés en base
(table `Tier`, ceux marqués `actif`). Le système ne « détecte » pas les tiers
dans le PDF : il prend le nom d'entreprise détecté par le NER, le translittère
en français (`preparer_nom_pour_similarite`), puis le **compare à chaque tier**
via `comparer()` :
- features rapidfuzz (Levenshtein, token_sort, jaccard…) →
- Random Forest répond « même entité » ou non, avec un score ;
- si `score ≥ SEUIL_SIMILARITE` → c'est un match.

C'est ainsi qu'on relie une annonce du bulletin à **un partenaire connu** de
Plastima malgré les variantes d'écriture.

**[7] ALERTE**
Pour chaque match tier↔annonce, une `Alerte` est créée avec une **priorité
automatique** (`determiner_priorite`) :
- Section I : `liquidation` → **haute**, `cession` → **moyenne**, reste → **basse** ;
- Section II (judiciaire) : toujours **haute**.

### Récapitulatif : qui décide quoi

| Information | Méthode | Modèle / outil |
|-------------|---------|----------------|
| Découpage en annonces | extraction | PyMuPDF |
| Nom de l'entreprise | NER tokens | **M2 CAMeL-BERT** |
| Type (annonce légale) | classification | **M1 TF-IDF + LinearSVC** |
| Type de procédure (judiciaire) | mots-clés | regex |
| Tribunal | mots-clés | regex |
| Est-ce un partenaire Plastima ? | similarité de noms | **M3 Random Forest** |
| Priorité de l'alerte | règles fixes | code (`determiner_priorite`) |

---

**Entraînement :** modèles 1, 2, 3 entraînés sur Google Colab (GPU T4). Inférence en
production sur CPU (`PyTorch CPU` + `transformers 4.x`). Voir `../ml/README.md`.
