"""Citation identifiers are checked by the code and converted to document and page."""

from app.rag.citations import (
    number_passages,
    passage_label,
    resolve_citations,
    source_label,
)
from app.retrieval.retriever import RetrievedPassage


def make_passage(chunk_id: str, filename: str, page_number: int) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id=f"doc-{filename}",
        filename=filename,
        page_number=page_number,
        position=0,
        text=f"Text of {chunk_id}",
        score=0.8,
    )


PASSAGES = [
    make_passage("c1", "contract.pdf", 3),
    make_passage("c2", "contract.pdf", 5),
    make_passage("c3", "contract.pdf", 3),  # same page as c1
    make_passage("c4", "invoice.png", 1),
]


def test_passages_are_numbered_from_s1() -> None:
    assert passage_label(0) == "S1"
    assert [label for label, _ in number_passages(PASSAGES)] == ["S1", "S2", "S3", "S4"]
    assert source_label(PASSAGES[3]) == "[invoice.png, p. 1]"


def test_a_valid_citation_becomes_document_and_page() -> None:
    result = resolve_citations("The notice period is 30 days [S2].", PASSAGES)

    assert result.text == "The notice period is 30 days [contract.pdf, p. 5]."
    assert [c.label for c in result.citations] == ["S2"]
    assert result.citations[0].passage.chunk_id == "c2"
    assert result.invalid_labels == []


def test_a_citation_glued_to_the_word_gets_a_space() -> None:
    result = resolve_citations("Paid in USD[S4].", PASSAGES)

    assert result.text == "Paid in USD [invoice.png, p. 1]."


def test_several_identifiers_in_one_marker() -> None:
    result = resolve_citations("Both apply [S2, S4].", PASSAGES)

    assert result.text == "Both apply [contract.pdf, p. 5] [invoice.png, p. 1]."
    assert [c.label for c in result.citations] == ["S2", "S4"]


def test_markers_side_by_side_are_merged_and_same_page_shown_once() -> None:
    result = resolve_citations("Fees are due monthly [S1][S3].", PASSAGES)

    assert result.text == "Fees are due monthly [contract.pdf, p. 3]."
    # Both passages are still listed: each one can be opened by the user.
    assert [c.label for c in result.citations] == ["S1", "S3"]


def test_variants_written_by_small_models_are_understood() -> None:
    answer = "One [s1]. Two [ S2 ]. Three [S1; S4]. Four [S01]. Five [S2, 4]."
    result = resolve_citations(answer, PASSAGES)

    assert result.text == (
        "One [contract.pdf, p. 3]. Two [contract.pdf, p. 5]. "
        "Three [contract.pdf, p. 3] [invoice.png, p. 1]. Four [contract.pdf, p. 3]. "
        "Five [contract.pdf, p. 5] [invoice.png, p. 1]."
    )
    assert [c.label for c in result.citations] == ["S1", "S2", "S4"]


def test_an_invented_identifier_is_removed_and_reported() -> None:
    result = resolve_citations("The term is two years [S9].", PASSAGES)

    assert result.text == "The term is two years."
    assert result.citations == []
    assert result.invalid_labels == ["S9"]


def test_valid_identifiers_are_kept_next_to_an_invented_one() -> None:
    result = resolve_citations("Late fees apply [S2, S7] [S0].", PASSAGES)

    assert result.text == "Late fees apply [contract.pdf, p. 5]."
    assert [c.label for c in result.citations] == ["S2"]
    assert result.invalid_labels == ["S7", "S0"]


def test_each_passage_is_listed_once_in_order_of_first_citation() -> None:
    result = resolve_citations("A [S4]. B [S1]. C [S4]. D [S9]. E [S9].", PASSAGES)

    assert [c.label for c in result.citations] == ["S4", "S1"]
    assert result.invalid_labels == ["S9"]


def test_an_answer_without_citation_is_unchanged() -> None:
    result = resolve_citations("  No marker here.\n", PASSAGES)

    assert result.text == "No marker here."
    assert result.citations == []
    assert result.invalid_labels == []


def test_brackets_that_are_not_citations_are_left_alone() -> None:
    result = resolve_citations("See [Note] and [1] and [Section 2] [S1].", PASSAGES)

    assert result.text == "See [Note] and [1] and [Section 2] [contract.pdf, p. 3]."


def test_line_breaks_are_kept() -> None:
    result = resolve_citations("- First point [S1]\n- Second point [S8]\n", PASSAGES)

    assert result.text == "- First point [contract.pdf, p. 3]\n- Second point"


def test_no_passages_means_every_citation_is_invalid() -> None:
    result = resolve_citations("Something [S1].", [])

    assert result.text == "Something."
    assert result.invalid_labels == ["S1"]