"""Ask French questions (and one English question on the French minutes) end to end.

Used at step 10 bis to check, before changing any code, that with qwen2.5:3b:
- the Writer answers in the language of the question and keeps its [Sx] citations;
- it still refuses (NOT_FOUND) when the documents lack the answer;
- the Critic does not flag correct numbers written in another format, such as
  "45 370,00" (French) for "45,370.00" (English), as unsupported.

Each question goes through POST /api/ask (stateless: nothing is saved in the
history), limited to the demo documents so that test files do not interfere.

Usage, from backend/ while the server and Ollama are running:
    python -m scripts.probe_writer_fr
"""

import argparse
import re
import sys
from collections import Counter

import httpx2

DEMO_FILES = {
    "service_agreement.pdf",
    "invoice_HDS-INV-2026-0042.pdf",
    "quarterly_review_HDS_Q2_2026.pptx",
    "compte_rendu_copil_HDS_2026-07.pdf",
}

# (question, language of the question, what a right answer contains, or None
# when the documents do not hold the answer and a refusal is expected).
QUESTIONS: list[tuple[str, str, str | None]] = [
    ("Quel est le préavis de résiliation ?", "fr", "60 jours"),
    ("Combien a été facturé au deuxième trimestre 2026 ?", "fr", "45 370 / 45,370"),
    ("Quelle était la disponibilité de la plateforme en mai 2026 ?", "fr", "99,38 / 99.38 %"),
    ("Quel est le montant de la redevance mensuelle ?", "fr", "12 500 / 12,500 USD"),
    ("Quel est le taux d'intérêt en cas de retard de paiement ?", "fr", "1,5 / 1.5 % par mois"),
    ("Quel est le montant total de la facture HDS-INV-2026-0042 ?", "fr", "15 950 / 15,950.00"),
    ("Combien coûte le raccordement de l'entrepôt de Marseille ?", "fr", "17 100,00 USD"),
    ("Quand a lieu le prochain comité de pilotage ?", "fr", "14 octobre 2026"),
    ("What service credit was granted for May 2026?", "en", "USD 625"),
    ("Quel est le chiffre d'affaires d'Orion au deuxième trimestre 2026 ?", "fr", None),
    ("Quel est le salaire du PDG ?", "fr", None),
]

_FRENCH_WORDS = {"le", "la", "les", "est", "de", "des", "du", "une", "un", "et", "au", "sont"}
_ENGLISH_WORDS = {"the", "is", "of", "and", "a", "an", "are", "to", "was", "for", "in"}
_CITATION = re.compile(r"\[[^\]]*\]")


def guess_language(text: str) -> str:
    """'fr', 'en' or '?' from a few common words (enough for short answers)."""
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", _CITATION.sub(" ", text.lower()))
    french = sum(word in _FRENCH_WORDS for word in words)
    english = sum(word in _ENGLISH_WORDS for word in words)
    if french == english:
        return "?"
    return "fr" if french > english else "en"


def demo_document_ids(client: httpx2.Client) -> list[str]:
    response = client.get("/api/documents")
    response.raise_for_status()
    return [
        document["id"]
        for document in response.json()
        if document["filename"] in DEMO_FILES and document["status"] == "ready"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend address")
    args = parser.parse_args()

    right_language = 0
    answered_with_citations = 0
    refusals_ok = 0
    issue_codes: Counter[str] = Counter()
    with httpx2.Client(base_url=args.url, timeout=300.0) as client:
        try:
            document_ids = demo_document_ids(client)
        except httpx2.HTTPError as error:
            print(f"Cannot list the documents: {error}", file=sys.stderr)
            return 1
        print(f"{len(document_ids)} demo documents used\n")

        for number, (question, language, expected) in enumerate(QUESTIONS, 1):
            try:
                response = client.post(
                    "/api/ask", json={"question": question, "document_ids": document_ids}
                )
                response.raise_for_status()
            except httpx2.HTTPError as error:
                print(f"Request failed for {question!r}: {error}", file=sys.stderr)
                return 1
            data = response.json()
            print(f"{number:>2}. [{language}] {question}")
            print(f"    expected: {expected or 'refusal'}")
            if data["status"] == "refused":
                print(f"    REFUSED ({data['refusal_reason']}), best score {data['best_score']}")
                refusals_ok += expected is None
                print()
                continue

            if expected is None:
                print("    ANSWERED, but the documents do not hold the answer")
            answer_language = guess_language(data["answer"])
            if expected is not None:
                right_language += answer_language == language
                answered_with_citations += bool(data["citations"])
            pages = sorted(
                {f"{c['filename'][:20]} p.{c['page_number']}" for c in data["citations"]}
            )
            print(f"    answer [{answer_language}]: {' '.join(data['answer'].split())}")
            print(f"    sources: {', '.join(pages) or 'none'}")
            if data["warnings"]:
                print(f"    warnings: {', '.join(data['warnings'])}")
            review = data["review"] or {"issues": []}
            for issue in review["issues"]:
                issue_codes[f"{issue['code']} ({issue['origin']})"] += 1
                print(f"    CRITIC {issue['code']} ({issue['origin']}): {issue['sentence']}")
            if not review["issues"]:
                print("    CRITIC: no issue")
            print()

    answerable = sum(expected is not None for _, _, expected in QUESTIONS)
    absent = len(QUESTIONS) - answerable
    print(f"Answered in the language of the question: {right_language} (of {answerable})")
    print(f"Answered with at least one citation:      {answered_with_citations} (of {answerable})")
    print(f"Refusals where the answer is absent:      {refusals_ok} of {absent}")
    print("Critic issues: " + (", ".join(f"{k}: {v}" for k, v in issue_codes.items()) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())