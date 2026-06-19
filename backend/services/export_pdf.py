"""
LegalEye — Génération du rapport PDF d'activité.

Rapport global : période choisie (X jours), tous les BO traités,
alertes, performances.

Utilise reportlab (pur Python, aucune dépendance système).

Auteur : Marouan (Plastima — DUT IDIA)
"""

import io
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)
from reportlab.pdfgen import canvas

from models import BulletinOfficiel, ArticleEntreprise, ArticleMahakim, Tier, Alerte


# ─────────────────────────────────────────────────────────────
#  Couleurs et styles
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  Theme Heritage - harmonise avec le frontend (tailwind config)
#  primary  = #972a19  (rouge brique)
#  clay     = #B8422E  (terre cuite)
#  ink      = #1A1C1E  (noir doux)
#  limestone= #F7F5F2  (beige clair)
#  slate    = #6C7278  (gris)
# ─────────────────────────────────────────────────────────────

COULEUR_PRIMAIRE = colors.HexColor("#972a19")    # primary Heritage
COULEUR_CLAY     = colors.HexColor("#b8422e")    # clay (accent)
COULEUR_SECONDAIRE = colors.HexColor("#6c7278")  # slate
COULEUR_TEXTE = colors.HexColor("#1a1c1e")       # ink
COULEUR_GRIS_CLAIR = colors.HexColor("#f7f5f2")  # limestone
COULEUR_BORDURE = colors.HexColor("#e2e2e5")     # outline-variant

# Couleurs fonctionnelles pour les badges de priorite
# (rouge plus chaud / orange ambre / vert sobre pour rester dans la palette)
COULEUR_HAUTE = colors.HexColor("#972a19")       # meme que primary -> coherence
COULEUR_MOYENNE = colors.HexColor("#c47410")     # ambre chaud (Heritage)
COULEUR_BASSE = colors.HexColor("#3f7556")       # vert mousse sobre


def _styles():
    """Styles personnalisés pour le PDF."""
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle(
            "titre", parent=base["Title"],
            textColor=COULEUR_PRIMAIRE, fontSize=22, leading=26,
            spaceAfter=12, alignment=TA_LEFT,
        ),
        "soustitre": ParagraphStyle(
            "soustitre", parent=base["Normal"],
            textColor=COULEUR_SECONDAIRE, fontSize=10,
            spaceAfter=20, alignment=TA_LEFT,
        ),
        "section": ParagraphStyle(
            "section", parent=base["Heading2"],
            textColor=COULEUR_PRIMAIRE, fontSize=14, leading=18,
            spaceBefore=14, spaceAfter=8,
        ),
        "normal": ParagraphStyle(
            "normal", parent=base["Normal"],
            textColor=COULEUR_TEXTE, fontSize=10, leading=14,
        ),
        "kpi_valeur": ParagraphStyle(
            "kpi_valeur", parent=base["Normal"],
            textColor=COULEUR_PRIMAIRE, fontSize=20, leading=24,
            alignment=TA_CENTER,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"],
            textColor=COULEUR_SECONDAIRE, fontSize=8, leading=10,
            alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            textColor=COULEUR_SECONDAIRE, fontSize=8,
            alignment=TA_CENTER,
        ),
    }


# ─────────────────────────────────────────────────────────────
#  Helpers : durée et formats
# ─────────────────────────────────────────────────────────────

def _formater_duree(secondes: Optional[float]) -> str:
    """0 → "—", 75 → "1 min 15 s", 3700 → "1 h 1 min"."""
    if secondes is None or secondes <= 0:
        return "—"
    s = int(secondes)
    h, reste = divmod(s, 3600)
    m, sec = divmod(reste, 60)
    if h > 0:
        return f"{h} h {m:02d} min"
    if m > 0:
        return f"{m} min {sec:02d} s"
    return f"{sec} s"


def _date_fr(dt: Optional[datetime]) -> str:
    """2026-05-14 → "14/05/2026"."""
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y")


def _datetime_fr(dt: Optional[datetime]) -> str:
    """2026-05-14 10:30 → "14/05/2026 10:30"."""
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


def _temps_traitement(bulletin: BulletinOfficiel) -> Optional[float]:
    """
    Estime le temps de traitement en secondes (updated_at - created_at).

    Note : updated_at est touche a chaque modification ulterieure du
    bulletin (retraitement, validation d'alerte, etc.), donc le delta
    n'est PAS toujours le temps reel de traitement.
    On filtre les valeurs aberrantes :
      - inferieures a 1 seconde (mesure erronee)
      - superieures a 6 heures (modif posterieure, pas le traitement initial)
    """
    if bulletin.statut != "traite" or not bulletin.updated_at or not bulletin.created_at:
        return None
    delta = bulletin.updated_at - bulletin.created_at
    secondes = delta.total_seconds()
    # Filtrage des valeurs aberrantes
    if secondes < 1 or secondes > 6 * 3600:
        return None
    return secondes


# ─────────────────────────────────────────────────────────────
#  En-tête et pied de page (sur toutes les pages)
# ─────────────────────────────────────────────────────────────

def _on_each_page(canvas_obj, doc):
    """Dessine l'en-tête et le pied de page sur chaque page."""
    canvas_obj.saveState()

    # En-tête : ligne fine en haut
    canvas_obj.setStrokeColor(COULEUR_BORDURE)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)

    # Logo placeholder + nom à gauche
    canvas_obj.setFillColor(COULEUR_PRIMAIRE)
    canvas_obj.setFont("Helvetica-Bold", 9)
    canvas_obj.drawString(2 * cm, A4[1] - 1.2 * cm, "BOAnalytic")
    canvas_obj.setFillColor(COULEUR_SECONDAIRE)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(2 * cm + 2.2 * cm, A4[1] - 1.2 * cm,
                          "Plastima · Veille juridique automatisée")

    # Date à droite
    canvas_obj.drawRightString(A4[0] - 2 * cm, A4[1] - 1.2 * cm,
                               f"Généré le {_datetime_fr(datetime.now())}")

    # Pied de page : numéro de page
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(COULEUR_SECONDAIRE)
    canvas_obj.drawCentredString(
        A4[0] / 2, 1 * cm,
        f"Page {doc.page}"
    )

    canvas_obj.restoreState()


# ─────────────────────────────────────────────────────────────
#  Bloc KPI (4 colonnes de cartes)
# ─────────────────────────────────────────────────────────────

def _bloc_kpis(kpis: list, styles: dict) -> Table:
    """
    kpis = [(valeur, label), ...]
    Renvoie une Table à 1 ligne, N colonnes.
    """
    cells = []
    for valeur, label in kpis:
        cells.append([
            Paragraph(str(valeur), styles["kpi_valeur"]),
            Paragraph(label, styles["kpi_label"]),
        ])

    # Une cellule de la grande table contient un Mini-tableau (val, label)
    grandes_cellules = []
    for cell_content in cells:
        mini = Table([[cell_content[0]], [cell_content[1]]],
                     colWidths=[3.8 * cm], rowHeights=[1.0 * cm, 0.6 * cm])
        mini.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, -1), COULEUR_GRIS_CLAIR),
            ("BOX", (0, 0), (-1, -1), 0.5, COULEUR_BORDURE),
        ]))
        grandes_cellules.append(mini)

    table = Table([grandes_cellules], colWidths=[4 * cm] * len(grandes_cellules))
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


# ─────────────────────────────────────────────────────────────
#  Couleur de cellule selon priorité / statut
# ─────────────────────────────────────────────────────────────

def _badge_priorite(p: str) -> Paragraph:
    couleur = {
        "haute": COULEUR_HAUTE,
        "moyenne": COULEUR_MOYENNE,
        "basse": COULEUR_BASSE,
    }.get(p, COULEUR_SECONDAIRE)
    label = (p or "").upper()
    # hexval() renvoie "0xffc107" → on transforme en "#ffc107" (format
    # attendu par reportlab dans le markup <font color="...">).
    hex_str = "#" + couleur.hexval()[2:]
    return Paragraph(
        f'<font color="{hex_str}"><b>● {label}</b></font>',
        ParagraphStyle("p", fontSize=8, leading=10),
    )


def _badge_statut(s: str) -> str:
    return {
        "nouvelle": "🆕 Nouvelle",
        "vue": "👁  Vue",
        "traitee": "✓ Traitée",
        "ignoree": "✗ Ignorée",
        "en_attente": "⏳ En attente",
        "en_cours": "⚙ En cours",
        "traite": "✓ Traité",
        "erreur": "❌ Erreur",
    }.get(s, s or "—")


# ═════════════════════════════════════════════════════════════
#  RAPPORT GLOBAL — période choisie
# ═════════════════════════════════════════════════════════════

def generer_rapport_global(
    db: Session,
    jours: int = 30,
    titre_personnalise: Optional[str] = None,
) -> bytes:
    """
    Génère un rapport PDF couvrant la période [aujourd'hui − jours, aujourd'hui].

    Sections :
        1. KPIs récapitulatifs
        2. Liste des bulletins traités sur la période
        3. Alertes générées (top 50 par score)
        4. Performances : temps de traitement moyen, médiane
        5. Top partenaires mentionnés
    """
    date_fin = datetime.utcnow()
    date_debut = date_fin - timedelta(days=jours)

    # ── Données ──
    bulletins = (
        db.query(BulletinOfficiel)
        .filter(BulletinOfficiel.created_at >= date_debut)
        .order_by(BulletinOfficiel.date_publication.desc())
        .all()
    )
    nb_legales = sum(b.nb_annonces_legales or 0 for b in bulletins)
    nb_judiciaires = sum(b.nb_annonces_judiciaires or 0 for b in bulletins)

    # On ne charge plus la liste des alertes (section "Top 50" supprimée).
    total_alertes = (
        db.query(func.count(Alerte.id))
        .filter(Alerte.created_at >= date_debut)
        .scalar() or 0
    )
    alertes_par_prio = dict(
        db.query(Alerte.priorite, func.count(Alerte.id))
        .filter(Alerte.created_at >= date_debut)
        .group_by(Alerte.priorite).all()
    )
    alertes_par_statut = dict(
        db.query(Alerte.statut, func.count(Alerte.id))
        .filter(Alerte.created_at >= date_debut)
        .group_by(Alerte.statut).all()
    )

    # Top partenaires : on ne compte QUE les alertes validées par l'admin
    # (statut = "traitee"). Les "nouvelle", "vue" et "ignoree" sont écartées
    # car le système peut générer des faux positifs.
    top_tiers = (
        db.query(Tier.nom, func.count(Alerte.id).label("nb"))
        .join(Alerte, Alerte.tier_id == Tier.id)
        .filter(Alerte.created_at >= date_debut)
        .filter(Alerte.statut == "traitee")
        .group_by(Tier.id)
        .order_by(func.count(Alerte.id).desc())
        .limit(10)
        .all()
    )

    # Temps de traitement (moyen uniquement)
    temps = [
        _temps_traitement(b) for b in bulletins
        if _temps_traitement(b) is not None
    ]
    temps_moyen = sum(temps) / len(temps) if temps else None

    # ── Construction du PDF ──
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = _styles()
    story = []

    # Titre
    titre = titre_personnalise or f"Rapport d'activité — derniers {jours} jours"
    story.append(Paragraph(titre, styles["titre"]))
    story.append(Paragraph(
        f"Période : du {_date_fr(date_debut)} au {_date_fr(date_fin)}",
        styles["soustitre"],
    ))

    # Section 1 — KPIs
    story.append(Paragraph("Vue d'ensemble", styles["section"]))
    story.append(_bloc_kpis([
        (len(bulletins), "Bulletins traités"),
        (nb_legales + nb_judiciaires, "Annonces extraites"),
        (total_alertes, "Alertes générées"),
        (alertes_par_prio.get("haute", 0), "Alertes prioritaires"),
    ], styles))
    story.append(Spacer(1, 0.4 * cm))

    # Section 2 — Bulletins
    story.append(Paragraph("Bulletins officiels traités", styles["section"]))
    if not bulletins:
        story.append(Paragraph("Aucun bulletin traité sur cette période.", styles["normal"]))
    else:
        data_bul = [["N°", "Date publi.", "Pages", "Légales", "Jud.",
                     "Statut", "Temps"]]
        for b in bulletins:
            data_bul.append([
                b.numero,
                _date_fr(b.date_publication),
                str(b.nb_pages or 0),
                str(b.nb_annonces_legales or 0),
                str(b.nb_annonces_judiciaires or 0),
                _badge_statut(b.statut),
                _formater_duree(_temps_traitement(b)),
            ])
        t = Table(data_bul, colWidths=[1.5 * cm, 2 * cm, 1.5 * cm, 1.8 * cm,
                                       1.8 * cm, 2.5 * cm, 2 * cm],
                  repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COULEUR_PRIMAIRE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, COULEUR_GRIS_CLAIR]),
            ("GRID", (0, 0), (-1, -1), 0.25, COULEUR_BORDURE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)

    # Section 3 — Performances
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Performances de traitement", styles["section"]))
    # Taux d'alertes en pourcentage du nombre d'annonces extraites
    # (mesure plus parlante qu'un ratio brut "alertes par bulletin")
    nb_annonces_total = nb_legales + nb_judiciaires
    if bulletins and nb_annonces_total > 0:
        taux_alertes = f"{(total_alertes / nb_annonces_total) * 100:.2f} %"
    else:
        taux_alertes = "—"

    if bulletins:
        moyenne_alertes = f"{total_alertes / max(len(bulletins), 1):.1f}"
    else:
        moyenne_alertes = "—"

    perf_data = [
        ["Métrique", "Valeur"],
        ["Bulletins traités sur la période", str(len(bulletins))],
        ["Temps moyen de traitement", _formater_duree(temps_moyen)],
        ["Annonces légales extraites", str(nb_legales)],
        ["Annonces judiciaires extraites", str(nb_judiciaires)],
        ["Total alertes générées", str(total_alertes)],
        ["Moyenne d'alertes par bulletin", moyenne_alertes],
        ["Taux d'alertes sur annonces extraites", taux_alertes],
    ]
    t = Table(perf_data, colWidths=[8 * cm, 4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_PRIMAIRE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, COULEUR_GRIS_CLAIR]),
        ("GRID", (0, 0), (-1, -1), 0.25, COULEUR_BORDURE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # Section 4 — Répartition par priorité/statut
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Répartition des alertes", styles["section"]))
    repart_data = [
        ["Priorité", "Nombre", "", "Statut", "Nombre"],
        [
            "Haute", str(alertes_par_prio.get("haute", 0)), "",
            "Nouvelles", str(alertes_par_statut.get("nouvelle", 0)),
        ],
        [
            "Moyenne", str(alertes_par_prio.get("moyenne", 0)), "",
            "Vues", str(alertes_par_statut.get("vue", 0)),
        ],
        [
            "Basse", str(alertes_par_prio.get("basse", 0)), "",
            "Traitées", str(alertes_par_statut.get("traitee", 0)),
        ],
        [
            "—", "—", "",
            "Ignorées (faux positif)", str(alertes_par_statut.get("ignoree", 0)),
        ],
    ]
    t = Table(repart_data, colWidths=[3 * cm, 2 * cm, 0.5 * cm, 4 * cm, 2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), COULEUR_PRIMAIRE),
        ("BACKGROUND", (3, 0), (4, 0), COULEUR_PRIMAIRE),
        ("TEXTCOLOR", (0, 0), (1, 0), colors.white),
        ("TEXTCOLOR", (3, 0), (4, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (1, -1), 0.25, COULEUR_BORDURE),
        ("GRID", (3, 0), (4, -1), 0.25, COULEUR_BORDURE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # Section 5 — Top tiers
    if top_tiers:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            "Partenaires les plus mentionnés (alertes validées)",
            styles["section"],
        ))
        data_tt = [["Rang", "Partenaire", "Nb alertes"]]
        for i, (nom, nb) in enumerate(top_tiers, 1):
            data_tt.append([str(i), nom or "—", str(nb)])
        t = Table(data_tt, colWidths=[1.5 * cm, 11 * cm, 2.5 * cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COULEUR_PRIMAIRE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, COULEUR_GRIS_CLAIR]),
            ("GRID", (0, 0), (-1, -1), 0.25, COULEUR_BORDURE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    # NB : la section "Top 50 alertes par score" a été retirée volontairement.
    # Le rapport se concentre sur les données validées par l'admin
    # (top partenaires sur alertes traitées).

    # Build
    doc.build(story, onFirstPage=_on_each_page, onLaterPages=_on_each_page)
    return buf.getvalue()

