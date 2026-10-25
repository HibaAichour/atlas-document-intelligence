"""The clause-splitting measurement script: variants, passages and the real page."""

import pytest

from scripts.probe_clauses import CASES, PAGE, as_passages, clause_variants, load_page

PAGE_TEXT = (
    "4.3 Termination for convenience. 60 days' written notice.\n"
    "4.4 Termination for cause. Remedy within 30 days.\n"
    "4.5 Effects of termination. Return the data within 30 days.\n"
)
BEFORE = "4.3 Termination for convenience. 60 days' written notice.\n"
CAUSE = "4.4 Termination for cause. Remedy within 30 days.\n"
AFTER = "4.5 Effects of termination. Return the data within 30 days.\n"


def test_clause_variants() -> None:
    variants = clause_variants(PAGE_TEXT, "first chunk")
    assert variants == {
        "current": ["first chunk"],
        "4.1-4.3": [BEFORE],
        "4.1-4.3 + 4.4": [BEFORE, CAUSE],
        "4.4 + 4.1-4.3": [CAUSE, BEFORE],
        "split page": [BEFORE, CAUSE, AFTER],
    }


@pytest.mark.parametrize(
    "text",
    ["no clause here", AFTER + CAUSE, BEFORE + CAUSE],
)
def test_clause_variants_need_articles_4_4_then_4_5(text: str) -> None:
    with pytest.raises(ValueError):
        clause_variants(text, "first chunk")


def test_as_passages() -> None:
    passages = as_passages(["a", "b"])
    assert [p.text for p in passages] == ["a", "b"]
    assert [p.chunk_id for p in passages] == ["probe-0", "probe-1"]
    assert {p.page_number for p in passages} == {PAGE}
    assert {p.filename for p in passages} == {"service_agreement.pdf"}


def test_the_cases_are_scenario_1_in_english_and_french() -> None:
    assert [case.language for case in CASES] == ["en", "fr"]
    assert all("60 days" in (case.expected or ()) for case in CASES)


def test_the_real_page_splits_as_expected() -> None:
    page_text, first_chunk = load_page()
    variants = clause_variants(page_text, first_chunk)
    before, cause = variants["4.1-4.3 + 4.4"]
    # 4.3 is in the first passage, the 30-day remedy period only in the second.
    assert "60 days' written notice" in " ".join(before.split())
    assert "30 days" not in before
    assert "30 days" in " ".join(cause.split())
    # Today's first chunk holds both: the cause of scenario 1.
    flat = " ".join(first_chunk.split())
    assert "60 days' written notice" in flat and "remedy it within 30 days" in flat