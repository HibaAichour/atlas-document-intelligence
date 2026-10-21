"""Print the retrieval scores of a fixed set of questions about the demo contract.

Used to calibrate RETRIEVAL_MIN_SCORE: questions answered by the contract
should score above the threshold, questions it cannot answer should score
below it. Only the search is called (no LLM), so it runs in a few seconds.

Usage, from backend/ while the server is running:
    python -m scripts.probe_scores
    python -m scripts.probe_scores --url http://localhost:8080 --top-k 5
"""

import argparse
import sys

import httpx2

# (question, page of the demo contract that answers it; None = not in the documents)
QUESTIONS: list[tuple[str, int | None]] = [
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


def describe(result: dict) -> str:
    return f"{result['score']:.3f} {result['filename'][:24]} p.{result['page_number']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend address")
    parser.add_argument("--top-k", type=int, default=3, help="results shown per question")
    args = parser.parse_args()

    best_answerable: list[float] = []
    best_absent: list[float] = []
    with httpx2.Client(base_url=args.url, timeout=60.0) as client:
        for question, expected_page in QUESTIONS:
            try:
                response = client.post(
                    "/api/search", json={"query": question, "top_k": args.top_k}
                )
                response.raise_for_status()
            except httpx2.HTTPError as error:
                print(f"Request failed for {question!r}: {error}", file=sys.stderr)
                return 1

            results = response.json()["results"]
            best = results[0]["score"] if results else 0.0
            (best_absent if expected_page is None else best_answerable).append(best)
            expected = "absent" if expected_page is None else f"p.{expected_page}"
            print(f"[{expected:>6}] {question}")
            print("         " + " | ".join(describe(result) for result in results))

    print()
    if best_answerable:
        print(f"Answerable questions: lowest best score = {min(best_answerable):.3f}")
    if best_absent:
        print(f"Absent information:   highest best score = {max(best_absent):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())