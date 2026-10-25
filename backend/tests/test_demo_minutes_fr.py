"""The French demo minutes: coherent figures, readable pages, stable file."""

from decimal import Decimal
from pathlib import Path

from app.ingestion.models import ParseOptions
from app.ingestion.pdf_parser import parse_pdf
from scripts.make_demo_minutes_fr import (
    french_number,
    french_percent,
    marseille_quote,
    missing_values,
    to_bytes,
)
from tests.builders import make_pdf


def write_minutes(tmp_path: Path) -> Path:
    path = tmp_path / "minutes.pdf"
    path.write_bytes(to_bytes())
    return path


def test_french_number_format() -> None:
    assert french_number(Decimal(45370)) == "45 370,00"
    assert french_number(Decimal(625)) == "625,00"
    assert french_number(Decimal("1234567.5")) == "1 234 567,50"
    assert french_percent(Decimal("99.74")) == "99,74 %"


def test_marseille_quote_uses_the_consulting_day_rate() -> None:
    # 18 days at USD 950 per day (Article 3.1 of the contract).
    assert marseille_quote() == Decimal(17100)


def test_parser_finds_the_key_values_on_the_right_page(tmp_path: Path) -> None:
    assert missing_values(write_minutes(tmp_path)) == []


def test_text_pdf_without_ocr(tmp_path: Path) -> None:
    pages = parse_pdf(write_minutes(tmp_path), ParseOptions())

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert not any(page.ocr_used for page in pages)
    # Accents survive the built-in PDF font and the parser.
    assert "Échéance" in pages[2].text
    assert pages[0].text.startswith("Comité de pilotage HDS-2026-014")


def test_figures_match_the_english_review(tmp_path: Path) -> None:
    pages = parse_pdf(write_minutes(tmp_path), ParseOptions())
    first = " ".join(pages[0].text.split())

    # Same figures as quarterly_review_HDS_Q2_2026.pptx, in the French format.
    for value in ("99,74 %", "4 h 37 min", "625,00 USD", "45 370,00 USD"):
        assert value in first


def test_no_salary_so_the_refusal_scenario_still_works(tmp_path: Path) -> None:
    pages = parse_pdf(write_minutes(tmp_path), ParseOptions())

    assert all("salaire" not in page.text.lower() for page in pages)


def test_missing_values_reports_what_is_not_found(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "other.pdf", ["Un texte sans rapport avec le comité."])

    missing = missing_values(path)

    assert "page 1: 15 juillet 2026" in missing
    assert "3 pages expected, 1 found" in missing


def test_running_the_script_again_gives_the_same_bytes() -> None:
    assert to_bytes() == to_bytes()