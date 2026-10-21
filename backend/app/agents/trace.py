"""The execution trace: which agents and tools ran for a request, how, and how long.

Each step of the Orchestrator's plan is recorded, including the steps that were
skipped because the plan ended early (a refusal). The trace is saved with the
answer and shown in the interface ("agents involved").
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Literal

# An agent makes decisions (it calls the LLM); a tool is deterministic (retrieval).
StepKind = Literal["agent", "tool"]
# ok: done; refused: the step decided the documents lack the answer;
# skipped: not run because the plan ended earlier; failed: an error was raised.
StepStatus = Literal["ok", "refused", "skipped", "failed"]


@dataclass(frozen=True, slots=True)
class AgentRun:
    """One step of the plan, as it was executed."""

    name: str  # "retrieval", "writer", "critic", ...
    kind: StepKind
    status: StepStatus
    duration_ms: int
    summary: str  # short technical note, e.g. "3 passages, best score 0.81"

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape saved in messages.agent_trace."""
        return asdict(self)


@dataclass(slots=True)
class StepNote:
    """What a running step reports about itself: its outcome and a short note."""

    status: StepStatus = "ok"
    summary: str = ""


class TraceRecorder:
    """Measures and records each step, in the order they run.

    The clock is injectable so tests get exact, repeatable durations.
    """

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._runs: list[AgentRun] = []

    @property
    def runs(self) -> list[AgentRun]:
        return list(self._runs)

    @contextmanager
    def step(self, name: str, kind: StepKind) -> Iterator[StepNote]:
        """Time the block. If it raises, the step is recorded as failed, then the
        error goes on (the request fails with its usual error)."""
        note = StepNote()
        start = self._clock()
        try:
            yield note
        except Exception as error:
            self._record(name, kind, "failed", start, f"{type(error).__name__}: {error}")
            raise
        self._record(name, kind, note.status, start, note.summary)

    def skip(self, name: str, kind: StepKind, reason: str) -> None:
        """Record a step of the plan that did not run."""
        self._runs.append(AgentRun(name, kind, "skipped", 0, reason))

    def _record(
        self, name: str, kind: StepKind, status: StepStatus, start: float, summary: str
    ) -> None:
        duration_ms = max(0, round((self._clock() - start) * 1000))
        self._runs.append(AgentRun(name, kind, status, duration_ms, summary))