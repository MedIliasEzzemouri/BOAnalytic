# Modèle 3 — Similarité (Random Forest)

## Fichiers

| Fichier | Rôle |
|---|---|
| `similarite.py` | Module utilisé par `backend/services/pipeline.py` (chargement + features + comparaison) |
| `train_similarite_colab.ipynb` | Notebook d'entraînement à exécuter sur Google Colab |
| `__init__.py` | Marque le dossier comme package Python |

Les modèles entraînés (`.pkl`) sont dans `../../modeles/similarite/`.

---

## Entraînement sur Google Colab — pas à pas

### 1. Préparer le fichier Excel des partenaires

Ton fichier `.xlsx` doit avoir au moins une colonne avec les noms des partenaires.
Exemple minimal :

| nom | type_tier | secteur |
|---|---|---|
| STORABI SARL | client | Plastique |
| SIGMATEL | fournisseur | Électronique |
| ATLAS PLASTIQUE | client | Industrie |
| ... | ... | ... |

**Important** : noter le nom exact de la colonne (par défaut le notebook attend `nom`).

### 2. Ouvrir Google Colab

1. Va sur https://colab.research.google.com
2. **Fichier → Importer un notebook → Importer** : sélectionne `train_similarite_colab.ipynb`
3. Le notebook s'ouvre

### 3. Uploader le fichier Excel

Dans Colab, panneau gauche :
1. Clique sur l'icône 📁 (Fichiers)
2. Glisse-dépose ton `partenaires_plastima.xlsx`
3. Vérifie qu'il apparaît dans la liste

### 4. Vérifier les paramètres

Cellule **section 2** :
```python
FICHIER_PARTENAIRES = "partenaires_plastima.xlsx"   # nom de ton fichier
COLONNE_NOM = "nom"                                  # nom de la colonne
```
Adapte si tes noms diffèrent.

### 5. Exécuter le notebook

**Exécution → Tout exécuter** (ou Ctrl+F9).
Durée : ~2 à 5 minutes selon le nombre de partenaires.

### 6. Vérifier les résultats

Tu verras s'afficher :
- Nombre de paires générées (positives / négatives)
- F1-score en cross-validation
- Matrice de confusion
- **Score adversarial** : ce qui nous intéresse vraiment
- Importance des features

**Objectif visé** :
- Score adversarial **>= 8/9** (sur 9 cas)
- F1 CV **> 0.95**

### 7. Télécharger les fichiers générés

Panneau Files de Colab → clic droit sur chaque fichier → **Télécharger** :
- `similarite_rf_v2.pkl` — le nouveau modèle
- `metriques_v2.json` — les métriques
- `matrice_confusion_v2.png`
- `importance_features_v2.png`

### 8. Remplacer la v1 sur ta machine

```bash
# Backup de la v1 (au cas où)
cd "/Users/marouan_rhazlani/Desktop/veille juridique/modeles/similarite"
mv similarite_rf.pkl similarite_rf_v1_backup.pkl
mv metriques.json metriques_v1_backup.json

# Placer la v2 à la place
# (déplace les fichiers téléchargés depuis ~/Downloads)
mv ~/Downloads/similarite_rf_v2.pkl similarite_rf.pkl
mv ~/Downloads/metriques_v2.json metriques.json
mv ~/Downloads/matrice_confusion_v2.png matrice_confusion.png
mv ~/Downloads/importance_features_v2.png importance_features.png
```

### 9. Tester la v2 sur ton bulletin

```bash
cd "/Users/marouan_rhazlani/Desktop/veille juridique/backend"
python test_pipeline_pdf.py uploads/bulletin.pdf
```

Tu devrais voir le score adversarial **bien meilleur** que la v1 (notamment sur les fautes de frappe).

---

## Que fait le notebook ?

### Augmentation — 4 stratégies par partenaire

1. **Formes juridiques** : `ATLAS` ↔ `ATLAS SARL`, `ATLAS SA`...
2. **Fautes de frappe** : `STORABI` ↔ `STROABI` (inversion / suppression / substitution)
3. **Ordre des mots** : `ATLAS PLASTIQUE` ↔ `PLASTIQUE ATLAS`
4. **Abréviations** : `GRANDE ENTREPRISE BTP` ↔ `G.E. B.` ou `GRAN ENTR BTP`

### Hard negatives

En plus des paires négatives aléatoires, le notebook génère des « **hard negatives** » :
des paires de partenaires qui **commencent par le même mot** mais sont différents
(ex : `SIGMA TECH` vs `SIGMA TELECOM`). Ça force le modèle à ne pas se fier
uniquement au premier mot.

### Évaluation adversariale

Le notebook teste **9 cas durs choisis manuellement** :
- 6 cas où le modèle doit dire « match » malgré la difficulté
- 3 cas où il doit dire « no match » malgré une apparente similarité

C'est cette métrique qu'il faut maximiser, plus que l'accuracy globale.

---

## Hyperparamètres

| Param | Valeur | Pourquoi |
|---|---|---|
| `n_estimators` | 300 | Plus que la v1 (200) → plus stable |
| `max_depth` | 12 | Plus profond (v1=10) → plus expressif |
| `min_samples_leaf` | 3 | Identique à v1 — évite le sur-apprentissage |
| `class_weight` | balanced | Gère le déséquilibre potentiel positives/négatives |
| `random_state` | 42 | Reproductibilité |

---

## Comparaison v1 vs v2 (à remplir après ton training)

| Métrique | v1 | v2 | Δ |
|---|---|---|---|
| F1 CV | 0.9938 | ? | ? |
| Score adversarial | ~3/9 (estimé) | ? | ? |
| Cas faute de frappe | < 0.5 | ? | ? |
| Cas ordre des mots | ? | ? | ? |

À documenter dans le rapport de stage.
