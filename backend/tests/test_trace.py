"""The execution trace records each step, its duration and its outcome."""

import pytest

from app.agents.trace import AgentRun, TraceRecorder


class FakeClock:
    """A clock that moves forward only when the test says so (in seconds)."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_a_step_is_recorded_with_its_duration_and_note() -> None:
    clock = FakeClock()
    trace = TraceRecorder(clock)

    with trace.step("retrieval", "tool") as note:
        clock.now += 0.2504
        note.summary = "3 passages"

    assert trace.runs == [AgentRun("retrieval", "tool", "ok", 250, "3 passages")]


def test_a_step_can_report_a_refusal() -> None:
    trace = TraceRecorder(FakeClock())

    with trace.step("writer", "agent") as note:
        note.status = "refused"

    assert trace.runs[0].status == "refused"


def test_an_error_is_recorded_as_failed_then_raised_again() -> None:
    clock = FakeClock()
    trace = TraceRecorder(clock)

    with pytest.raises(ValueError, match="boom"), trace.step("writer", "agent"):
        clock.now += 1.0
        raise ValueError("boom")

    assert trace.runs == [AgentRun("writer", "agent", "failed", 1000, "ValueError: boom")]


def test_a_skipped_step_takes_no_time() -> None:
    trace = TraceRecorder(FakeClock())

    trace.skip("writer", "agent", "no passage above the relevance threshold")

    assert trace.runs == [
        AgentRun("writer", "agent", "skipped", 0, "no passage above the relevance threshold")
    ]


def test_steps_keep_their_order_and_the_list_is_a_copy() -> None:
    trace = TraceRecorder(FakeClock())
    with trace.step("retrieval", "tool"):
        pass
    trace.skip("writer", "agent", "plan ended")

    runs = trace.runs
    runs.clear()

    assert [run.name for run in trace.runs] == ["retrieval", "writer"]


def test_to_dict_gives_the_saved_json_shape() -> None:
    run = AgentRun("retrieval", "tool", "ok", 12, "2 passages")

    assert run.to_dict() == {
        "name": "retrieval",
        "kind": "tool",
        "status": "ok",
        "duration_ms": 12,
        "summary": "2 passages",
    }