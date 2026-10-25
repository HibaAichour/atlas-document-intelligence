"""Evaluation scoring: the evaluation file, answers, citations, the Critic and extractions."""

import copy
from typing import Any

import pytest

from scripts.eval_scoring import (
    AskCase,
    AskOutcome,
    EvalSetError,
    ExtractCase,
    PageRef,
    contains_any,
    extracted_values,
    guess_language,
    load_eval_set,
    normalize,
    outcome_from_api,
    parse_eval_set,
    results_json,
    score_ask,
    score_extraction,
    summarize,
    summary_lines,
)

NOTICE = AskCase(
    id="notice-en",
    language="en",
    question="What is the termination notice period?",
    expected=("60 days",),
    forbidden=("30 days",),
    pages=(PageRef("contract.pdf", (4,)),),
)
SALARY = AskCase("salary-fr", "fr", "Quel est le salaire du PDG ?", None, (), ())
INVOICE = ExtractCase(
    "invoice", "invoice.pdf", {"invoice_number": ("INV-42",), "total_amount": ("15,950",)}
)

VALID: dict[str, Any] = {
    "documents": ["contract.pdf", "invoice.pdf"],
    "questions": [
        {
            "id": "notice-en",
            "language": "en",
            "question": "What is the termination notice period?",
            "expected": ["60 days"],
            "forbidden": ["30 days"],
            "pages": [{"file": "contract.pdf", "pages": [4]}],
            "note": "scenario 1",
        },
        {
            "id": "salary-fr",
            "language": "fr",
            "question": "Quel est le salaire du PDG ?",
            "expected": None,
            "pages": [],
        },
    ],
    "extractions": [
        {"id": "invoice", "file": "invoice.pdf", "fields": {"invoice_number": ["INV-42"]}}
    ],
}


# The evaluation file.


def test_the_real_evaluation_file_is_valid_and_balanced() -> None:
    eval_set = load_eval_set()
    languages = [case.language for case in eval_set.questions]
    assert 15 <= len(eval_set.questions) <= 25
    assert languages.count("en") >= 8 and languages.count("fr") >= 8
    assert any(case.expected is None for case in eval_set.questions)
    assert {case.id for case in eval_set.extractions} == {"invoice", "contract"}
    # Demo scenario 1 is there, with the 30-day trap.
    notice = next(case for case in eval_set.questions if case.id == "notice-en")
    assert "30 days" in notice.forbidden


def test_parse_eval_set() -> None:
    eval_set = parse_eval_set(VALID)
    assert eval_set.questions[0] == AskCase(
        "notice-en",
        "en",
        "What is the termination notice period?",
        ("60 days",),
        ("30 days",),
        (PageRef("contract.pdf", (4,)),),
        "scenario 1",
    )
    assert eval_set.questions[1].expected is None
    assert eval_set.questions[1].forbidden == ()
    assert eval_set.extractions[0].fields == {"invoice_number": ("INV-42",)}


def broken(change) -> dict[str, Any]:
    data = copy.deepcopy(VALID)
    change(data)
    return data


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["questions"][0].update(language="de"), "language"),
        (lambda d: d["questions"][0].update(expected=[]), "expected is empty"),
        (lambda d: d["questions"][0].update(expected=[""]), "non-empty texts"),
        (lambda d: d["questions"][0].update(pages=[]), "needs expected pages"),
        (
            lambda d: d["questions"][1].update(pages=[{"file": "contract.pdf", "pages": [1]}]),
            "refusal",
        ),
        (lambda d: d["questions"][0]["pages"][0].update(file="other.pdf"), "unknown documents"),
        (lambda d: d["extractions"][0].update(file="other.pdf"), "unknown document"),
        (lambda d: d["questions"][1].update(id="notice-en"), "repeated ids"),
        (lambda d: d["questions"][0].pop("question"), "missing"),
    ],
)
def test_parse_eval_set_rejects_malformed_entries(change, message: str) -> None:
    with pytest.raises(EvalSetError, match=message):
        parse_eval_set(broken(change))


# Comparing texts.


def test_normalize_and_contains_any() -> None:
    assert normalize("17\u202f100,00\xa0USD\n  Total") == "17 100,00 usd total"
    assert contains_any("Le coût est de 17\u202f100,00 USD.", ["17 100"])
    assert contains_any("The notice period is 60 DAYS.", ["60 days"])
    assert not contains_any("It is 90 days.", ["60 days", "60 jours"])
    assert not contains_any("anything", [])


# Language of an answer.


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("The notice period is 60 days [service_agreement.pdf, p. 4].", "en"),
        ("Le préavis de résiliation est de 60 jours [service_agreement.pdf, p. 4].", "fr"),
        # Step 11: an English question answered in French.
        ("Helix estime le travail à 18 jours de conseil, soit un devis de 17 100,00 USD.", "fr"),
        ("USD 45,370.00 [quarterly_review.pptx, p. 5]", None),  # no common word
        ("", None),
    ],
)
def test_guess_language(text: str, language: str | None) -> None:
    assert guess_language(text) == language


def test_the_citation_marker_does_not_count_as_words() -> None:
    assert guess_language("Le montant est de 625 USD [the review of the quarter, p. 6].") == "fr"


# Questions.

API_ANSWER = {
    "status": "answered",
    "refusal_reason": None,
    "answer": "The notice period is 60 days [contract.pdf, p. 4].",
    "citations": [{"filename": "contract.pdf", "page_number": 4}],
    "review": {"verdict": "issues", "issues": [{"code": "unsupported_claim", "origin": "model"}]},
}


def test_outcome_from_api() -> None:
    outcome = outcome_from_api(API_ANSWER, seconds=5.2)
    assert outcome == AskOutcome(
        refused=False,
        answer="The notice period is 60 days [contract.pdf, p. 4].",
        sources=(("contract.pdf", 4),),
        issues=("unsupported_claim (model)",),
        seconds=5.2,
    )
    refusal = {"status": "refused", "refusal_reason": "no_relevant_passages", "answer": "x"}
    assert outcome_from_api(refusal).refused is True
    assert outcome_from_api(refusal).issues == ()  # no review for a refusal


def test_a_right_answer_with_a_right_page() -> None:
    score = score_ask(NOTICE, outcome_from_api(API_ANSWER))
    assert score.right is True
    assert score.citation_right is True
    assert score.right_and_cited is True
    assert score.flagged is True  # a false alarm of the Critic
    assert score.language == "en"
    assert score.language_right is True


def test_an_answer_in_the_other_language_is_right_but_marked() -> None:
    outcome = AskOutcome(
        False, answer="Le préavis est de 60 days.", sources=(("contract.pdf", 4),)
    )
    score = score_ask(NOTICE, outcome)
    assert score.right is True
    assert score.language_right is False


def test_a_right_answer_citing_another_page() -> None:
    outcome = AskOutcome(False, answer="60 days.", sources=(("contract.pdf", 2),))
    score = score_ask(NOTICE, outcome)
    assert score.citation_right is False
    assert score.right_and_cited is False


def test_a_forbidden_text_makes_the_answer_wrong() -> None:
    outcome = AskOutcome(False, answer="60 days for convenience, 30 days for breach.")
    score = score_ask(NOTICE, outcome)
    assert score.right is False
    assert score.citation_right is None


def test_an_unexpected_refusal_is_wrong() -> None:
    score = score_ask(NOTICE, AskOutcome(True, "not_found_by_model"))
    assert score.right is False
    assert score.flagged is False
    assert score.language is None
    assert score.language_right is None


def test_a_refusal_is_right_when_the_documents_lack_the_answer() -> None:
    refused = score_ask(SALARY, AskOutcome(True, "no_relevant_passages"))
    assert refused.right is True
    assert refused.right_and_cited is True  # nothing to cite
    answered = score_ask(SALARY, AskOutcome(False, answer="It is USD 45,370."))
    assert answered.right is False
    assert answered.citation_right is None


# Extractions.


def test_extracted_values() -> None:
    message = {
        "extraction": {
            "fields": [
                {"name": "invoice_number", "value": "INV-42", "page": 1},
                {"name": "due_date", "value": None, "page": None},
            ]
        }
    }
    assert extracted_values(message) == {"invoice_number": "INV-42", "due_date": None}
    assert extracted_values({"extraction": None}) is None


def test_score_extraction() -> None:
    score = score_extraction(INVOICE, {"invoice_number": "INV-42", "total_amount": "USD 15,950.00"})
    assert score.right == 2
    assert score.refused is False

    partial = score_extraction(INVOICE, {"invoice_number": "INV-41", "total_amount": None})
    assert [f.right for f in partial.fields] == [False, False]

    refused = score_extraction(INVOICE, None)
    assert refused.refused is True
    assert refused.right == 0
    assert len(refused.fields) == 2


# Summary.


def scores():
    # English: right and cited (flagged), right but badly cited (flagged), wrong.
    right_flagged = score_ask(NOTICE, outcome_from_api(API_ANSWER))
    badly_cited = score_ask(
        NOTICE,
        AskOutcome(False, answer="It is 60 days.", sources=(("contract.pdf", 2),), issues=("x",)),
    )
    wrong_unflagged = score_ask(NOTICE, AskOutcome(False, answer="It is 30 days."))
    # French: a right refusal, and an answer that should have been a refusal (flagged).
    salary_refused = score_ask(SALARY, AskOutcome(True, "no_relevant_passages"))
    salary_answered = score_ask(
        SALARY, AskOutcome(False, answer="Le salaire est de 45 370 USD.", issues=("x (code)",))
    )
    extract = score_extraction(INVOICE, {"invoice_number": "INV-42", "total_amount": "1"})
    return [right_flagged, badly_cited, wrong_unflagged, salary_refused, salary_answered], [
        extract
    ]


def test_summarize() -> None:
    asks, extracts = scores()
    summary = summarize(asks, extracts)
    assert str(summary.questions["all"]) == "3 of 5 (60%)"
    assert str(summary.answers["en"]) == "2 of 3 (67%)"
    assert str(summary.refusals["fr"]) == "1 of 2 (50%)"
    assert str(summary.answers["fr"]) == "-"
    # The badly cited answer is right, but not right and cited.
    assert str(summary.cited["en"]) == "1 of 3 (33%)"
    assert str(summary.cited["all"]) == "2 of 5 (40%)"
    assert str(summary.citations) == "1 of 2 (50%)"
    # Four answers, all in the language of their question.
    assert str(summary.languages) == "4 of 4 (100%)"
    # Wrong answers: one flagged of two; right answers: the well-cited one is a
    # false alarm, the badly cited one a justified alert.
    assert str(summary.caught) == "1 of 2 (50%)"
    assert str(summary.false_alarms) == "1 of 1 (100%)"
    assert str(summary.justified) == "1 of 1 (100%)"
    assert str(summary.fields) == "1 of 2 (50%)"


def test_summary_lines() -> None:
    lines = summary_lines(summarize(*scores()))
    assert lines[0].split() == ["English", "French", "All"]
    assert lines[1].startswith("Questions right")
    assert "3 of 5 (60%)" in lines[1]
    assert lines[4].startswith("Right, with a right citation")
    assert any(line.startswith("Answers in the right language") for line in lines)
    assert any("flagged 1 of 1 (100%)" in line for line in lines if "badly cited" in line)
    assert lines[-1].startswith("Extracted fields right")


def test_results_json() -> None:
    asks, extracts = scores()
    results = results_json(asks, extracts, {"url": "http://localhost:8080"})
    assert results["context"] == {"url": "http://localhost:8080"}
    assert results["summary"]["questions"]["all"] == "3 of 5 (60%)"
    assert results["summary"]["right_and_cited"]["all"] == "2 of 5 (40%)"
    assert results["questions"][0]["sources"] == ["contract.pdf p. 4"]
    assert results["questions"][0]["citation_right"] is True
    assert results["questions"][0]["answer_language"] == "en"
    assert results["extractions"][0]["fields_right"] == "1 of 2"