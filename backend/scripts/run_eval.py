"""Run the evaluation set (eval/questions.json) against a running ATLAS and print the score.

Each question goes through POST /api/ask (stateless: nothing is saved in the
history), limited to the four demo documents, so test files in the index do
not interfere. Each extraction goes through the session route, the one the
interface uses: one session named "Extract the key fields of ..." is created
per run and appears in the history (there is no route to delete a session in
V1; leave out the extractions with --no-extractions).

The answers are scored by code (scripts/eval_scoring.py), not by an LLM. The
summary is printed and the detail is saved as JSON (eval/results.json by
default), so the score shown in the README can be checked.

Usage, from backend/ while the server and Ollama are running:
    python -m scripts.run_eval
    python -m scripts.run_eval --url http://localhost:8080 --label docker
    python -m scripts.run_eval --no-extractions
"""

import argparse
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2

from app.core.config import get_settings
from scripts.eval_scoring import (
    EVAL_FILE,
    AskCase,
    AskScore,
    EvalSet,
    ExtractCase,
    ExtractScore,
    extracted_values,
    load_eval_set,
    outcome_from_api,
    results_json,
    score_ask,
    score_extraction,
    summarize,
    summary_lines,
)

RESULTS_FILE = EVAL_FILE.parent / "results.json"
Clock = Callable[[], float]
Log = Callable[[str], None]


class EvalRunError(Exception):
    """The evaluation cannot run (a demo document is missing, the server fails)."""


def demo_document_ids(client: httpx2.Client, files: Sequence[str]) -> dict[str, list[str]]:
    """File name -> ids of its ready copies (a file uploaded twice has two ids).

    Raises:
        EvalRunError: If a demo document is not uploaded or not ready.
    """
    response = client.get("/api/documents")
    response.raise_for_status()
    ids: dict[str, list[str]] = {file: [] for file in files}
    for document in response.json():
        if document["filename"] in ids and document["status"] == "ready":
            ids[document["filename"]].append(document["id"])
    missing = [file for file, found in ids.items() if not found]
    if missing:
        raise EvalRunError(f"Demo documents not uploaded or not ready: {', '.join(missing)}")
    return ids


def ask(
    client: httpx2.Client, case: AskCase, document_ids: list[str], clock: Clock
) -> AskScore:
    start = clock()
    response = client.post(
        "/api/ask", json={"question": case.question, "document_ids": document_ids}
    )
    response.raise_for_status()
    return score_ask(case, outcome_from_api(response.json(), clock() - start))


def extract(
    client: httpx2.Client, session_id: str, case: ExtractCase, document_id: str, clock: Clock
) -> ExtractScore:
    start = clock()
    response = client.post(
        f"/api/sessions/{session_id}/extract", json={"document_id": document_id}
    )
    response.raise_for_status()
    answer = response.json()["answer"]
    review = answer.get("review") or {"issues": []}
    issues = [f"{issue['code']} ({issue.get('field') or '-'})" for issue in review["issues"]]
    return score_extraction(case, extracted_values(answer), issues, clock() - start)


def short(text: str, width: int = 90) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 3] + "..."


def ask_line(score: AskScore) -> str:
    mark = "ok" if score.right else "WRONG"
    if score.outcome.refused:
        what = f"refused ({score.outcome.refusal_reason})"
    else:
        what = short(score.outcome.answer)
        if score.citation_right is False:
            what += "  [page not expected]"
    critic = f"  critic: {', '.join(score.outcome.issues)}" if score.outcome.issues else ""
    return f"  {mark:<6}{score.case.id:<22}{score.outcome.seconds:>5.1f} s  {what}{critic}"


def extract_line(score: ExtractScore) -> str:
    if score.refused:
        return f"  {'WRONG':<6}{score.case.id:<22}{score.seconds:>5.1f} s  refused"
    wrong = [f"{f.name}={f.value!r}" for f in score.fields if not f.right]
    detail = f"  wrong: {', '.join(wrong)}" if wrong else ""
    return (
        f"  {'':<6}{score.case.id:<22}{score.seconds:>5.1f} s  "
        f"{score.right} of {len(score.fields)} fields right{detail}"
    )


def run(
    client: httpx2.Client,
    eval_set: EvalSet,
    *,
    extractions: bool = True,
    clock: Clock = time.perf_counter,
    log: Log = print,
) -> tuple[list[AskScore], list[ExtractScore]]:
    """Ask every question, then run every extraction (in one new session)."""
    ids = demo_document_ids(client, eval_set.documents)
    all_ids = [document_id for found in ids.values() for document_id in found]
    log(f"Questions ({len(eval_set.questions)}), on {len(all_ids)} demo documents:")
    asks: list[AskScore] = []
    for case in eval_set.questions:
        asked = ask(client, case, all_ids, clock)
        asks.append(asked)
        log(ask_line(asked))

    extracts: list[ExtractScore] = []
    if extractions and eval_set.extractions:
        response = client.post("/api/sessions")
        response.raise_for_status()
        session_id = response.json()["id"]
        log(f"Extractions ({len(eval_set.extractions)}), in session {session_id}:")
        for extract_case in eval_set.extractions:
            document_id = ids[extract_case.file][0]
            extracted = extract(client, session_id, extract_case, document_id, clock)
            extracts.append(extracted)
            log(extract_line(extracted))
    return asks, extracts


def context(url: str, label: str, extractions: bool) -> dict[str, Any]:
    """Where and when the evaluation ran, with the local settings for reference."""
    settings = get_settings()
    return {
        "label": label,
        "url": url,
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "extractions": extractions,
        "local_settings": {
            "llm_model": settings.llm_model,
            "embedding_model": settings.embedding_model,
            "retrieval_min_score": settings.retrieval_min_score,
            "retrieval_max_gap": settings.retrieval_max_gap,
            "retrieval_top_k": settings.retrieval_top_k,
        },
    }


def write_results(path: Path, results: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend address")
    parser.add_argument("--label", default="native", help="name of the run, saved in the results")
    parser.add_argument("--output", type=Path, default=RESULTS_FILE, help="JSON file to write")
    parser.add_argument(
        "--no-extractions", action="store_true", help="skip the extractions (no session created)"
    )
    args = parser.parse_args()
    eval_set = load_eval_set()
    extractions = not args.no_extractions

    start = time.perf_counter()
    with httpx2.Client(base_url=args.url, timeout=300.0) as client:
        try:
            asks, extracts = run(client, eval_set, extractions=extractions)
        except (httpx2.HTTPError, EvalRunError) as error:
            print(f"Evaluation stopped: {error}", file=sys.stderr)
            return 1
    print(f"\nScore ({args.label}, {time.perf_counter() - start:.0f} s)")
    print("\n".join(summary_lines(summarize(asks, extracts))))
    run_context = context(args.url, args.label, extractions)
    write_results(args.output, results_json(asks, extracts, run_context))
    print(f"\nDetail saved to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())