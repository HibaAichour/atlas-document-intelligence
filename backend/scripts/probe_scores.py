"""Print the retrieval scores of fixed sets of questions about the demo documents.

Used to calibrate RETRIEVAL_MIN_SCORE: questions answered by a document
should score above the threshold, questions it cannot answer should score
below it. Only the search is called (no LLM), so it runs in a few seconds.

Each set targets one demo document. For an answerable question, the script
also looks for the right passage (expected file and page) in the results and
prints its score: this is the score the threshold must let through, even when
another document ranks first.

Usage, from backend/ while the server is running:
    python -m scripts.probe_scores
    python -m scripts.probe_scores --set review --top-k 5
    python -m scripts.probe_scores --url http://localhost:8080 --top-k 5
"""

import argparse
import sys

import httpx2

# The pages of the document that answer a question: one page, several pages
# (any of them is right), or None when the documents do not hold the answer.
Expected = int | tuple[int, ...] | None

CONTRACT_QUESTIONS: list[tuple[str, Expected]] = [
    ("When does the agreement start?", 1),
    ("What is the platform availability commitment?", 2),
    ("How fast must the provider respond to a critical incident?", 2),
    ("How much is the monthly fee?", 3),
    ("When must invoices be paid?", 3),
    ("What is the late payment interest rate?", 3),
    ("What is the termination notice period?", 4),
    ("How long is the initial term of the agreement?", 4),
    ("Where is the client data stored?", 5),
    ("How long does the confidentiality obligation last?", 5),
    ("Which law governs the agreement?", 6),
    ("Who signed the agreement for the provider?", 6),
    ("What is the CEO's salary?", None),
    ("How many employees does Orion Freight have?", None),
    ("Does the agreement include a non-compete clause?", None),
    ("What is the warranty period for the hardware?", None),
    ("What is the capital of France?", None),
    ("Who won the last football World Cup?", None),
]

REVIEW_QUESTIONS: list[tuple[str, Expected]] = [
    ("When was the onboarding completed?", 2),
    ("What was the platform availability in May 2026?", (3, 6)),
    ("How many critical incidents were there in the quarter?", (2, 3)),
    ("How many shipments were processed in June 2026?", 4),
    ("How many support tickets were opened in the quarter?", 4),
    ("How much was invoiced in Q2 2026?", (2, 5)),
    ("What is the total of invoice HDS-INV-2026-0057?", 5),
    ("What caused the outage in May 2026?", 6),
    ("What service credit is due for May 2026?", 6),
    ("What was Orion Freight's revenue in Q2 2026?", None),
    ("How many critical incidents were there in July 2026?", None),
    ("What is the CEO's salary?", None),
]

# Set name -> (file name of the target document, questions).
QUESTION_SETS: dict[str, tuple[str, list[tuple[str, Expected]]]] = {
    "contract": ("service_agreement.pdf", CONTRACT_QUESTIONS),
    "review": ("quarterly_review_HDS_Q2_2026.pptx", REVIEW_QUESTIONS),
}


def expected_pages(expected: Expected) -> tuple[int, ...]:
    if expected is None:
        return ()
    return expected if isinstance(expected, tuple) else (expected,)


def right_passage_score(results: list[dict], filename: str, pages: tuple[int, ...]) -> float | None:
    """The best score among the results from the expected file and pages."""
    scores = [
        result["score"]
        for result in results
        if result["filename"] == filename and result["page_number"] in pages
    ]
    return max(scores) if scores else None


def describe(result: dict) -> str:
    return f"{result['score']:.3f} {result['filename'][:24]} p.{result['page_number']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend address")
    parser.add_argument("--top-k", type=int, default=3, help="results shown per question")
    parser.add_argument("--set", choices=QUESTION_SETS, default="contract", help="question set")
    args = parser.parse_args()
    filename, questions = QUESTION_SETS[args.set]

    right_scores: list[float] = []
    missed: list[str] = []  # answerable questions whose right passage is not in the results
    first_correct = 0
    best_absent: list[float] = []
    with httpx2.Client(base_url=args.url, timeout=60.0) as client:
        for question, expected in questions:
            try:
                response = client.post("/api/search", json={"query": question, "top_k": args.top_k})
                response.raise_for_status()
            except httpx2.HTTPError as error:
                print(f"Request failed for {question!r}: {error}", file=sys.stderr)
                return 1

            results = response.json()["results"]
            pages = expected_pages(expected)
            if pages:
                label = "p." + ",".join(str(page) for page in pages)
            else:
                label = "absent"
            print(f"[{label:>6}] {question}")
            print("         " + " | ".join(describe(result) for result in results))

            if not pages:
                best_absent.append(results[0]["score"] if results else 0.0)
                continue
            score = right_passage_score(results, filename, pages)
            if score is None:
                missed.append(question)
                print("         right passage: not in the results")
                continue
            right_scores.append(score)
            top = results[0]
            if top["filename"] == filename and top["page_number"] in pages:
                first_correct += 1
            print(f"         right passage: {score:.3f}")

    answerable = len(right_scores) + len(missed)
    print()
    print(f"Set {args.set!r} ({filename}), top-k = {args.top_k}")
    if answerable:
        print(f"Right passage ranked first: {first_correct} of {answerable}")
    if right_scores:
        print(f"Right passage:      lowest score = {min(right_scores):.3f}")
    if missed:
        print(f"Right passage not found for {len(missed)} question(s)")
    if best_absent:
        print(f"Absent information: highest best score = {max(best_absent):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())