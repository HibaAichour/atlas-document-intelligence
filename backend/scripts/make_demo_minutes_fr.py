"""Create the French demo document: minutes of a steering committee, a text PDF.

The meeting of 15 July 2026 reviews Q2 2026 of the demo contract
(service_agreement.pdf, Agreement No. HDS-2026-014) with Orion Freight France
SAS, the French subsidiary of the Client. Its figures repeat the demo review
(quarterly_review_HDS_Q2_2026.pptx) in the French number format: average
availability, May downtime, service credit and total invoiced. The quote for
the Marseille warehouse uses the consulting day rate of Article 3.1.

ATLAS reads one PDF page as one page, so each page holds one topic and every
fact has a single page to cite.

Usage, from the backend folder:
    python -m scripts.make_demo_minutes_fr

The file is written to demo_documents/ at the root of the repository, then
read back with the ATLAS parser to check that the key values are found on
the right pages. Running the script again gives exactly the same file.
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from app.ingestion.models import ParseOptions
from app.ingestion.pdf_parser import parse_pdf
from scripts.make_demo_review import (
    MAY,
    average_availability,
    downtime,
    quarter_total,
    service_credit,
)

OUTPUT = (
    Path(__file__).resolve().parents[2] / "demo_documents" / "compte_rendu_copil_HDS_2026-07.pdf"
)

# Fixed date written in the file, so that running the script again gives a
# byte-for-byte identical file.
FIXED_DATE = datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC)

# --- Figures of the minutes ---------------------------------------------------

CONSULTING_DAY_RATE = Decimal(950)  # Article 3.1 of the contract
MARSEILLE_DAYS = 18  # consulting days quoted to connect the Marseille warehouse


def french_number(amount: Decimal) -> str:
    """45370 -> '45 370,00': space between thousands, comma before decimals."""
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def french_percent(value: Decimal) -> str:
    """Decimal('99.74') -> '99,74 %'."""
    return f"{value}".replace(".", ",") + " %"


def marseille_quote() -> Decimal:
    return MARSEILLE_DAYS * CONSULTING_DAY_RATE


# Values read back from each page after saving (page number -> texts).
EXPECTED_ON_PAGE = {
    1: [
        "COMPTE RENDU DU COMITÉ DE PILOTAGE",
        "15 juillet 2026",
        "Claire Moreau",
        "99,74 %",
        "4 h 37 min",
        "625,00 USD",
        "45 370,00 USD",
    ],
    2: [
        "14 mai 2026",
        "Francfort",
        "certificat",
        "entrepôt du Havre",
        "Marseille",
        "17 100,00 USD",
    ],
    3: [
        "30 septembre 2026",
        "Antoine Lefèvre",
        "31 juillet 2026",
        "14 octobre 2026",
    ],
}

# --- Look of the pages ----------------------------------------------------------

TEAL = (0x0C, 0x7C, 0x7A)
CORAL = (0xFF, 0x7F, 0x66)
INK = (0x16, 0x32, 0x3A)
MUTED = (0x5B, 0x72, 0x78)
ROW_TINT = (0xE8, 0xF4, 0xF3)
WHITE = (0xFF, 0xFF, 0xFF)

FONT = "helvetica"  # built-in PDF font: Latin-1 only, so no curly quotes or ligatures
PAGE_COUNT = len(EXPECTED_ON_PAGE)
HEADER = "Comité de pilotage HDS-2026-014 - 15 juillet 2026"
FICTION_NOTE = "Document fictif créé uniquement pour la démonstration."


class Minutes(FPDF):
    """An A4 page with a running header, as on the demo contract."""

    def header(self) -> None:
        self.set_font(FONT, size=9)
        self.set_text_color(*MUTED)
        title = f"{HEADER} - Page {self.page_no()} sur {PAGE_COUNT}"
        self.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)


def heading(pdf: FPDF, text: str) -> None:
    """A teal section title with a short coral line under it."""
    pdf.ln(3)
    pdf.set_font(FONT, style="B", size=14)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*CORAL)
    pdf.set_line_width(0.8)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.l_margin + 25, y)
    pdf.ln(4)


def paragraph(pdf: FPDF, text: str, size: int = 11, color: tuple[int, int, int] = INK) -> None:
    pdf.set_font(FONT, size=size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


def bullets(pdf: FPDF, items: list[str]) -> None:
    for item in items:
        paragraph(pdf, f"- {item}")


def actions_table(pdf: FPDF, rows: list[tuple[str, str, str]]) -> None:
    """A table with a teal header row and tinted body rows."""
    pdf.set_font(FONT, size=10)
    pdf.set_text_color(*INK)
    # Thin teal borders (the section titles leave a thick coral pen behind).
    pdf.set_draw_color(*TEAL)
    pdf.set_line_width(0.2)
    with pdf.table(
        col_widths=(95, 45, 40),
        headings_style=FontFace(emphasis="BOLD", color=WHITE, fill_color=TEAL),
        cell_fill_color=ROW_TINT,
        cell_fill_mode="ROWS",
        line_height=6,
        text_align="LEFT",
    ) as table:
        for values in rows:
            row = table.row()
            for value in values:
                row.cell(value)
    pdf.ln(4)


def build_pdf() -> FPDF:
    pdf = Minutes(format="A4")
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title("Compte rendu du comité de pilotage - 15 juillet 2026")
    pdf.set_author("Helix Data Services Ltd. (fictif)")
    pdf.set_creator("ATLAS demo script")
    pdf.set_creation_date(FIXED_DATE)
    pdf.set_lang("fr")

    # 1. Header, participants and Q2 review
    pdf.add_page()
    pdf.set_font(FONT, style="B", size=18)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 10, "COMPTE RENDU DU COMITÉ DE PILOTAGE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    paragraph(
        pdf,
        "Contrat de services HDS-2026-014 entre Helix Data Services Ltd. et Orion Freight Co.",
        size=12,
    )
    paragraph(pdf, FICTION_NOTE, size=9, color=MUTED)
    paragraph(
        pdf,
        "Date et lieu : 15 juillet 2026, de 10 h 00 à 11 h 30, en visioconférence.",
    )

    heading(pdf, "Participants")
    bullets(
        pdf,
        [
            (
                "Pour Orion Freight France SAS (filiale d'Orion Freight Co., entrepôts de Lyon "
                "et du Havre) : Claire Moreau, directrice des opérations ; Julien Faure, "
                "responsable informatique."
            ),
            "Pour Orion Freight Co. : Marcus Webb, directeur des achats.",
            (
                "Pour Helix Data Services Ltd. : Priya Nair, directrice de compte ; Antoine "
                "Lefèvre, chef de projet."
            ),
        ],
    )

    heading(pdf, "Ordre du jour")
    bullets(
        pdf,
        [
            "Bilan du deuxième trimestre 2026.",
            "Incidents de mai et demandes d'Orion Freight France.",
            "Décisions, plan d'actions et prochaine réunion.",
        ],
    )

    heading(pdf, "1. Bilan du deuxième trimestre 2026")
    paragraph(
        pdf,
        f"La disponibilité moyenne de la plateforme sur le trimestre est de "
        f"{french_percent(average_availability())}. Seul le mois de mai est sous l'objectif "
        f"de 99,5 % : la plateforme a été indisponible {downtime(MAY)} au total.",
    )
    paragraph(
        pdf,
        f"Conformément à l'article 2.6 du contrat, Orion Freight Co. bénéficie d'un avoir de "
        f"{french_number(service_credit(MAY))} USD, déduit de la facture de juillet 2026.",
    )
    paragraph(
        pdf,
        f"Le montant total facturé au deuxième trimestre 2026 s'élève à "
        f"{french_number(quarter_total())} USD. Toutes les factures ont été payées dans les "
        "délais.",
    )

    # 2. May incidents and requests of Orion Freight France
    pdf.add_page()
    heading(pdf, "2. Incidents de mai 2026")
    paragraph(
        pdf,
        "Deux incidents critiques ont eu lieu en mai 2026. Helix a répondu à chacun en moins "
        "de deux heures.",
    )
    paragraph(
        pdf,
        f"Premier incident, le 14 mai 2026 : une défaillance de stockage dans la région "
        f"principale de Francfort a rendu la plateforme indisponible pendant {downtime(MAY)}. "
        "Helix a remplacé l'équipement défaillant et ajouté une surveillance de l'espace de "
        "stockage.",
    )
    paragraph(
        pdf,
        "Second incident, le 27 mai 2026 : l'expiration d'un certificat sur le connecteur de "
        "l'entrepôt du Havre a interrompu la remontée des données de cet entrepôt pendant "
        "6 heures. La plateforme est restée disponible pour les autres sites.",
    )
    paragraph(
        pdf,
        "Mesures correctives décidées : une alerte automatique 30 jours avant l'expiration de "
        "chaque certificat, et une revue mensuelle des certificats par Helix.",
    )

    heading(pdf, "3. Demandes d'Orion Freight France")
    paragraph(
        pdf,
        "Orion Freight France ouvre un troisième entrepôt à Marseille et demande son "
        "raccordement à la plateforme.",
    )
    paragraph(
        pdf,
        f"Helix estime le travail à {MARSEILLE_DAYS} jours de conseil au tarif de "
        f"{french_number(CONSULTING_DAY_RATE)} USD par jour prévu à l'article 3.1, soit un "
        f"devis de {french_number(marseille_quote())} USD.",
    )
    paragraph(
        pdf,
        "Orion Freight France demande aussi deux sessions de formation supplémentaires pour "
        "10 utilisateurs de l'entrepôt de Marseille.",
    )

    # 3. Decisions, action plan and next meeting
    pdf.add_page()
    heading(pdf, "4. Décisions")
    bullets(
        pdf,
        [
            (
                f"Le raccordement de l'entrepôt de Marseille est validé, sur la base du devis "
                f"de {french_number(marseille_quote())} USD. Mise en service visée : "
                "30 septembre 2026."
            ),
            (
                "Les deux sessions de formation auront lieu en septembre 2026, avant la mise "
                "en service."
            ),
        ],
    )

    heading(pdf, "5. Plan d'actions")
    actions_table(
        pdf,
        [
            ("Action", "Responsable", "Échéance"),
            (
                "Mettre en place l'alerte d'expiration des certificats",
                "Antoine Lefèvre",
                "31 juillet 2026",
            ),
            ("Signer le devis de raccordement de Marseille", "Marcus Webb", "5 août 2026"),
            ("Raccorder l'entrepôt de Marseille", "Antoine Lefèvre", "30 septembre 2026"),
            ("Organiser les deux sessions de formation", "Julien Faure", "15 septembre 2026"),
        ],
    )

    heading(pdf, "6. Prochaine réunion")
    paragraph(
        pdf,
        "Le prochain comité de pilotage aura lieu le 14 octobre 2026, avec la revue du "
        "troisième trimestre 2026.",
    )
    paragraph(
        pdf,
        "Compte rendu rédigé par Priya Nair, directrice de compte, Helix Data Services Ltd., "
        "le 16 juillet 2026.",
        size=10,
        color=MUTED,
    )
    return pdf


def to_bytes() -> bytes:
    return bytes(build_pdf().output())


def missing_values(path: Path) -> list[str]:
    """Read the file with the ATLAS parser; list the expected texts not found."""
    pages = {page.page_number: page.text for page in parse_pdf(path, ParseOptions())}
    missing = []
    for number, values in EXPECTED_ON_PAGE.items():
        # Lines may break anywhere: compare with single spaces only.
        text = " ".join(pages.get(number, "").split())
        for value in values:
            if value not in text:
                missing.append(f"page {number}: {value}")
    if len(pages) != len(EXPECTED_ON_PAGE):
        missing.append(f"{len(EXPECTED_ON_PAGE)} pages expected, {len(pages)} found")
    return missing


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(to_bytes())
    print(f"Created {OUTPUT}")

    missing = missing_values(OUTPUT)
    if missing:
        raise SystemExit("Parser check failed, not found:\n" + "\n".join(missing))
    print(f"Parser check passed: {len(EXPECTED_ON_PAGE)} pages, key values on the right page")


if __name__ == "__main__":
    main()