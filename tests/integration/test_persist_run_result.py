"""Integration test for persist_run_result: verifies events, decisions, fills persisted."""

from datetime import date, datetime, timedelta

from alpha_quant.app.pipeline import RunResult, persist_run_result
from alpha_quant.domain.events import PipelineRunCompleted, PipelineRunStarted
from alpha_quant.domain.models import Decision, Fill


class _FakeStore:
    def __init__(self) -> None:
        self.saved_events: list[object] = []
        self.saved_decisions: list[Decision] = []
        self.saved_fills: list[Fill] = []

    def save_event(self, event: object) -> None:
        self.saved_events.append(event)

    def save_decision(self, decision: Decision) -> None:
        self.saved_decisions.append(decision)

    def save_fill(self, fill: Fill) -> None:
        self.saved_fills.append(fill)


def test_persist_empty_result() -> None:
    store = _FakeStore()
    result = RunResult(
        run_id="test-empty",
        date=date(2026, 1, 1),
        decisions=[],
        fills=[],
        events=[],
        violations=[],
    )
    persist_run_result(store, result)
    assert len(store.saved_events) == 0
    assert len(store.saved_decisions) == 0
    assert len(store.saved_fills) == 0


def test_persist_events_decisions_fills() -> None:
    store = _FakeStore()
    run_id = "test-123"
    now = datetime.fromisoformat("2026-06-15T12:00:00+00:00")
    later = now + timedelta(seconds=1)
    events = [
        PipelineRunStarted(run_id=run_id, source="test", mode="unit", timestamp=now),
        PipelineRunCompleted(
            run_id=run_id,
            source="test",
            duration_s=1.0,
            status="completed",
            timestamp=later,
        ),
    ]
    decisions = [
        Decision(symbol="AAPL", date=date(2026, 6, 15), action="enter", confidence=0.8),
        Decision(symbol="MSFT", date=date(2026, 6, 15), action="enter", confidence=0.7),
    ]
    fills = [
        Fill(
            fill_id="f1",
            order_id="o1",
            symbol="AAPL",
            quantity=100.0,
            price=150.0,
            timestamp=now,
        ),
    ]
    result = RunResult(
        run_id=run_id,
        date=date(2026, 6, 15),
        decisions=decisions,
        fills=fills,
        events=events,
        violations=[],
    )

    persist_run_result(store, result)

    assert len(store.saved_events) == 2
    assert len(store.saved_decisions) == 2
    assert len(store.saved_fills) == 1
    assert store.saved_fills[0].fill_id == "f1"
    assert store.saved_decisions[0].symbol == "AAPL"
