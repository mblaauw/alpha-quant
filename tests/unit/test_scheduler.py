from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

from alpha_quant.app.scheduler import run_daily_pipeline


def _mock_config() -> object:
    class _FakeData:
        mode = "live"
        fixture_version = "v1"

    class _FakeBootstrap:
        symbols = ["AAPL"]
        include_benchmarks = ["SPY"]

    class _FakeConnector:
        pass

    config = type(
        "FakeConfig",
        (),
        {
            "data": _FakeData(),
            "bootstrap": _FakeBootstrap(),
            "connector": _FakeConnector(),
            "model_dump": lambda self, **kwargs: {
                "data": {"mode": "live", "fixture_version": "v1"},
                "bootstrap": {"symbols": ["AAPL"], "include_benchmarks": ["SPY"]},
            },
        },
    )
    return config()


def _mock_run_result(
    halted: bool = False,
    violations: list | None = None,
    decisions: int = 0,
    fills: int = 0,
    events: int = 0,
) -> object:
    from dataclasses import dataclass

    @dataclass
    class RunResult:
        run_id: str
        date: date
        decisions: list
        fills: list
        events: list
        violations: list
        halted: bool
        prev_equity: float | None
        new_equity: float | None

    return RunResult(
        run_id="test-run-id",
        date=date.today(),
        decisions=list(range(decisions)),
        fills=list(range(fills)),
        events=list(range(events)),
        violations=violations or [],
        halted=halted,
        prev_equity=100_000.0,
        new_equity=101_000.0,
    )


class _FakeStore:
    def __init__(self, existing_runs: list | None = None) -> None:
        self._existing_runs = existing_runs or []
        self.registered_run_id: str | None = None
        self.completed_status: str | None = None

    def list_runs(self, since_date: date | None = None) -> list[dict]:
        return self._existing_runs

    def register_run(self, run_type: str, config_hash: str, fixture_version: str = "") -> str:
        run_id = "test-run-id"
        self.registered_run_id = run_id
        return run_id

    def complete_run(self, run_id: str, status: str = "completed", manifest_hash: str = "") -> None:
        self.completed_status = status

    def load_latest_portfolio_snapshot(self) -> None:
        return None


def _mock_violation(check: str) -> object:
    from alpha_quant.domain.invariants import InvariantViolation

    return InvariantViolation(check=check, detail="test violation")


class TestRunDailyPipeline:
    def test_skips_non_market_day(self) -> None:
        with (
            patch("alpha_quant.app.scheduler.is_market_day", return_value=False),
            patch("alpha_quant.app.scheduler.load_config", return_value=_mock_config()),
            patch("alpha_quant.app.scheduler.CanonicalStore"),
        ):
            result = run_daily_pipeline()
        assert result["status"] == "skipped"
        assert result["reason"] == "non_market_day"

    def test_skips_duplicate_completed(self) -> None:
        fake_store = _FakeStore(
            existing_runs=[
                {
                    "run_id": "existing",
                    "start_ts": datetime.now().isoformat(),
                    "status": "completed",
                }
            ]
        )
        with (
            patch("alpha_quant.app.scheduler.is_market_day", return_value=True),
            patch("alpha_quant.app.scheduler.load_config", return_value=_mock_config()),
            patch("alpha_quant.app.scheduler.CanonicalStore", return_value=fake_store),
            patch("alpha_quant.app.scheduler.run_pipeline") as mock_run,
        ):
            result = run_daily_pipeline()
        assert result["status"] == "skipped"
        assert result["reason"] == "duplicate"
        assert result["run_id"] == "existing"
        mock_run.assert_not_called()

    def test_skips_duplicate_running(self) -> None:
        fake_store = _FakeStore(
            existing_runs=[
                {
                    "run_id": "running-id",
                    "start_ts": datetime.now().isoformat(),
                    "status": "running",
                }
            ]
        )
        with (
            patch("alpha_quant.app.scheduler.is_market_day", return_value=True),
            patch("alpha_quant.app.scheduler.load_config", return_value=_mock_config()),
            patch("alpha_quant.app.scheduler.CanonicalStore", return_value=fake_store),
            patch("alpha_quant.app.scheduler.run_pipeline") as mock_run,
        ):
            result = run_daily_pipeline()
        assert result["status"] == "skipped"
        assert result["reason"] == "duplicate"
        assert result["run_id"] == "running-id"
        mock_run.assert_not_called()

    def test_runs_pipeline_on_market_day(self) -> None:
        fake_store = _FakeStore(existing_runs=[])
        mock_result = _mock_run_result(decisions=3, fills=2, events=10)
        with (
            patch("alpha_quant.app.scheduler.is_market_day", return_value=True),
            patch("alpha_quant.app.scheduler.load_config", return_value=_mock_config()),
            patch("alpha_quant.app.scheduler.CanonicalStore", return_value=fake_store),
            patch("alpha_quant.app.scheduler.run_pipeline", return_value=mock_result),
        ):
            result = run_daily_pipeline()
        assert result["status"] == "completed"
        assert result["run_id"] == "test-run-id"
        assert result["decisions"] == 3
        assert result["fills"] == 2
        assert result["events"] == 10
        assert result["violations"] == 0
        assert fake_store.registered_run_id is not None
        assert fake_store.completed_status == "completed"

    def test_reports_halted_status(self) -> None:
        fake_store = _FakeStore(existing_runs=[])
        mock_result = _mock_run_result(halted=True)
        with (
            patch("alpha_quant.app.scheduler.is_market_day", return_value=True),
            patch("alpha_quant.app.scheduler.load_config", return_value=_mock_config()),
            patch("alpha_quant.app.scheduler.CanonicalStore", return_value=fake_store),
            patch("alpha_quant.app.scheduler.run_pipeline", return_value=mock_result),
        ):
            result = run_daily_pipeline()
        assert result["status"] == "halted"
        assert fake_store.completed_status == "halted"

    def test_reports_violations_status(self) -> None:
        fake_store = _FakeStore(existing_runs=[])
        mock_result = _mock_run_result(violations=[_mock_violation("I5")])
        with (
            patch("alpha_quant.app.scheduler.is_market_day", return_value=True),
            patch("alpha_quant.app.scheduler.load_config", return_value=_mock_config()),
            patch("alpha_quant.app.scheduler.CanonicalStore", return_value=fake_store),
            patch("alpha_quant.app.scheduler.run_pipeline", return_value=mock_result),
        ):
            result = run_daily_pipeline()
        assert result["status"] == "violations"
        assert result["violations"] == 1
        assert fake_store.completed_status == "violations"
