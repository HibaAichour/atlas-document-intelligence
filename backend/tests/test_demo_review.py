"""The demo quarterly review: coherent figures, readable slides, stable file."""

from decimal import Decimal
from pathlib import Path

from pptx import Presentation

from app.ingestion.models import ParseOptions
from app.ingestion.pptx_parser import parse_pptx
from scripts.make_demo_review import (
    INVOICES,
    MAY,
    MONTHS,
    MonthOfService,
    average_availability,
    downtime,
    missing_values,
    quarter_total,
    service_credit,
    to_bytes,
)


def write_review(tmp_path: Path) -> Path:
    path = tmp_path / "review.pptx"
    path.write_bytes(to_bytes())
    return path


def test_figures_follow_the_contract_and_the_invoice() -> None:
    # The April invoice is the demo invoice (USD 15,950.00, extras 600 + 2,850).
    assert INVOICES[0].extras == Decimal(3450)
    assert INVOICES[0].total == Decimal(15950)
    assert [invoice.total for invoice in INVOICES] == [
        Decimal(15950),
        Decimal(15480),
        Decimal(13940),
    ]
    assert quarter_total() == Decimal(45370)
    assert average_availability() == Decimal("99.74")


def test_may_outage_and_service_credit() -> None:
    # 0.62% of the 744 hours of May is 4.61 hours.
    assert downtime(MAY) == "4 h 37 min"
    # 0.12% below 99.5% counts as one step of 0.5%: 5% of USD 12,500.
    assert service_credit(MAY) == Decimal(625)
    assert [service_credit(month) for month in MONTHS] == [0, Decimal(625), 0]


def test_service_credit_is_capped_at_25_percent() -> None:
    worst = MonthOfService("Bad month", Decimal(90), 9, "5 h", 720)
    assert service_credit(worst) == Decimal(3125)


def test_parser_finds_the_key_values_on_the_right_slide(tmp_path: Path) -> None:
    path = write_review(tmp_path)

    assert missing_values(path) == []


def test_one_topic_per_slide(tmp_path: Path) -> None:
    pages = parse_pptx(write_review(tmp_path), ParseOptions())

    assert [page.page_number for page in pages] == [1, 2, 3, 4, 5, 6]
    assert pages[1].text.startswith("Executive summary")
    # Tables are read row by row, header first.
    assert "Month | Availability | Target | Critical incidents | Max response time" in (
        pages[2].text
    )
    assert "Invoice | Date | Monthly Fee | Extras | Total" in pages[4].text
    # Every slide but the title one ends with its footer.
    assert pages[5].text.endswith("6 / 6")


def test_no_salary_so_the_refusal_scenario_still_works(tmp_path: Path) -> None:
    pages = parse_pptx(write_review(tmp_path), ParseOptions())

    assert all("salary" not in page.text.lower() for page in pages)


def test_missing_values_reports_what_is_not_found(tmp_path: Path) -> None:
    path = tmp_path / "empty.pptx"
    Presentation().save(str(path))

    missing = missing_values(path)

    assert "slide 1: Q2 2026" in missing
    assert "6 slides expected, 0 found" in missing


def test_running_the_script_again_gives_the_same_bytes() -> None:
    assert to_bytes() == to_bytes()