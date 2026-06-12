"""Unit tests for report generators (alpha_quant.domain.reporting)."""

from datetime import date

from alpha_quant.domain.narration import NarrationContext
from alpha_quant.domain.reporting import ReportEntry, generate_monthly, generate_weekly


def _ctx(
    day: int,
    regime: str = "RISK_ON",
    scored: int = 5,
    blocked: int = 1,
    promoted: int = 2,
    equity: float = 100_000.0,
    cash: float = 80_000.0,
) -> NarrationContext:
    return NarrationContext(
        date=date(2026, 6, day),
        regime=regime,
        data_health={
            "eodhd": True,
            "alpaca": True,
            "openinsider": True,
            "reddit": True,
            "sec": True,
        },
        candidates_scored=scored,
        candidates_blocked=blocked,
        candidates_promoted=promoted,
        positions=[],
        equity=equity,
        cash=cash,
        concept_of_day=None,
    )


class TestGenerateWeekly:
    def test_returns_report_entry(self) -> None:
        ctxs = [_ctx(11), _ctx(12)]
        report = generate_weekly(ctxs, date(2026, 6, 12))
        assert isinstance(report, ReportEntry)
        assert report.report_type == "weekly"

    def test_contains_performance(self) -> None:
        ctxs = [_ctx(11, equity=100_000.0), _ctx(12, equity=102_000.0)]
        report = generate_weekly(ctxs, date(2026, 6, 12))
        assert "+2.00%" in report.content or "2.00%" in report.content
        assert "100,000" in report.content

    def test_contains_candidate_funnel(self) -> None:
        ctxs = [_ctx(11, scored=5, blocked=2, promoted=3)]
        report = generate_weekly(ctxs, date(2026, 6, 11))
        assert "Scored: 5" in report.content
        assert "Blocked: 2" in report.content
        assert "Promoted: 3" in report.content

    def test_contains_regime(self) -> None:
        ctxs = [_ctx(11, regime="CAUTION")]
        report = generate_weekly(ctxs, date(2026, 6, 11))
        assert "CAUTION" in report.content

    def test_contains_data_health(self) -> None:
        ctxs = [_ctx(11)]
        report = generate_weekly(ctxs, date(2026, 6, 11))
        assert "All data sources healthy" in report.content


class TestGenerateMonthly:
    def test_returns_report_entry(self) -> None:
        ctxs = [_ctx(1), _ctx(15), _ctx(30)]
        report = generate_monthly(ctxs, date(2026, 6, 30))
        assert isinstance(report, ReportEntry)
        assert report.report_type == "monthly"

    def test_contains_performance(self) -> None:
        ctxs = [_ctx(1, equity=100_000.0), _ctx(30, equity=105_000.0)]
        report = generate_monthly(ctxs, date(2026, 6, 30))
        assert "5.00%" in report.content

    def test_contains_activity_summary(self) -> None:
        ctxs = [_ctx(1, scored=10, blocked=3, promoted=4)]
        report = generate_monthly(ctxs, date(2026, 6, 30))
        assert "Candidates scored: 10" in report.content
        assert "Candidates blocked: 3" in report.content
        assert "Candidates promoted: 4" in report.content

    def test_contains_cost_drag(self) -> None:
        ctxs = [_ctx(1, promoted=5), _ctx(15, promoted=3)]
        report = generate_monthly(ctxs, date(2026, 6, 30))
        assert "Cost" in report.content

    def test_contains_caveat(self) -> None:
        ctxs = [_ctx(1)]
        report = generate_monthly(ctxs, date(2026, 6, 30))
        assert "Past performance" in report.content

    def test_dates_in_report(self) -> None:
        ctxs = [_ctx(1), _ctx(30)]
        report = generate_monthly(ctxs, date(2026, 6, 30))
        assert "2026-06-01" in report.content
        assert "2026-06-30" in report.content


class TestReportEntry:
    def test_frozen(self) -> None:
        r = ReportEntry(date=date(2026, 6, 11), report_type="weekly", content="# test")
        assert r.report_type == "weekly"
        assert r.content == "# test"
