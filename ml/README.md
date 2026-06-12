# ML — Code d'entraînement et scripts

> Les modèles **entraînés** (`.pkl`, `.safetensors`) sont dans `../modeles/`.
> Ce dossier contient le **code source** des scripts.

## Structure

```
ml/
├── extraction/
│   └── extraction_pdf.py        Extraction PyMuPDF (Sections I et II)
│
├── ner/
│   └── pipeline_ner_v7.py       Pipeline NER complet (CAMeL-BERT)
│
├── translation/
│   └── translation.py           Translittération arabe → français
│
└── _legacy/
    └── models_standalone.py     Ancien models.py (DeclarativeBase 2.0)
```

## Notes

- L'entraînement des modèles 1, 2 et 3 a été fait sur Google Colab (GPU T4).
- Les notebooks Colab ne sont pas inclus ici — à rapatrier si nécessaire pour la reproductibilité.
- Le pipeline en production est dans `backend/services/pipeline.py`.

## Reproductibilité

Pour réentraîner :
1. Modèle 1 (classification) : nécessite `entreprises_articles.csv` (1 759 articles)
2. Modèle 2 (NER) : nécessite 1 713 annotations BIO
3. Modèle 3 (similarité) : nécessite paires positives/négatives (à générer depuis les noms de partenaires)

À documenter dans des notebooks Colab versionnés.
