"""
LegalEye — Import des PDFs déjà téléchargés dans la base de données.

Utilisation :
    python scripts/import_pdfs.py           # importe tous les BOAL_*.pdf manquants
    python scripts/import_pdfs.py --traiter # importe ET lance le pipeline ML
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Rendre backend/ importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scraping"))

from database import SessionLocal
from models import BulletinOfficiel
from config import UPLOAD_DIR

UPLOAD_PATH = Path(UPLOAD_DIR)


def import_pdfs(lancer_pipeline: bool = False):
    db = SessionLocal()
    try:
        pdfs = sorted(UPLOAD_PATH.glob("BOAL_*.pdf"))
        if not pdfs:
            print(f"Aucun BOAL_*.pdf trouvé dans {UPLOAD_PATH}")
            return

        print(f"Trouvé {len(pdfs)} fichier(s) PDF dans {UPLOAD_PATH}")
        imported = 0
        skipped = 0

        for pdf in pdfs:
            # Extraire le numéro depuis le nom de fichier : BOAL_5921.pdf -> "5921"
            numero = pdf.stem.replace("BOAL_", "")

            existing = db.query(BulletinOfficiel).filter(
                BulletinOfficiel.numero == numero
            ).first()
            if existing:
                print(f"  [skip] BOAL_{numero}.pdf — déjà en BDD (id={existing.id}, statut={existing.statut})")
                skipped += 1
                continue

            # Extraire la date de publication depuis le PDF
            try:
                from scraper_bo import extraire_date_publication
                date_pub = extraire_date_publication(pdf)
            except Exception:
                date_pub = None

            if date_pub is None:
                date_pub = datetime.now().date()
                print(f"  [warn] BOAL_{numero}.pdf — date introuvable, utilisation de la date du jour")

            bulletin = BulletinOfficiel(
                numero=numero,
                date_publication=date_pub,
                fichier_pdf=str(pdf.absolute()),
                source="scraping",
                statut="en_attente",
            )
            db.add(bulletin)
            db.commit()
            db.refresh(bulletin)
            print(f"  [OK]   BOAL_{numero}.pdf — id={bulletin.id}, date={date_pub}")
            imported += 1

            if lancer_pipeline:
                print(f"         → Lancement du pipeline ML pour bulletin {bulletin.id}…")
                try:
                    from services.pipeline import traiter_bulletin
                    traiter_bulletin(bulletin.id, db)
                    print(f"         ✅ Pipeline terminé")
                except Exception as e:
                    print(f"         ❌ Erreur pipeline : {e}")

        print(f"\nBilan : {imported} importé(s), {skipped} ignoré(s)")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importe les PDFs téléchargés en base de données")
    parser.add_argument(
        "--traiter",
        action="store_true",
        help="Lance le pipeline ML après import (lent — traite chaque PDF)",
    )
    args = parser.parse_args()
    import_pdfs(lancer_pipeline=args.traiter)
