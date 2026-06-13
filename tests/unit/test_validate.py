"""Unit tests for validation gates."""

from datetime import date, timedelta

from alpha_quant.domain.models import Bar
from alpha_quant.domain.validate import validate_bars


def _make_bars(count: int, base_vol: float = 1_000_000) -> list[Bar]:
    base = date(2025, 1, 1)
    bars: list[Bar] = []
    for i in range(count):
        bars.append(
            Bar(
                symbol="AAPL",
                date=base + timedelta(days=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=base_vol,
            )
        )
    return bars


class TestValidateBars:
    def test_detects_volume_spike(self) -> None:
        bars = _make_bars(25, 1_000_000)
        bars[-1] = bars[-1].model_copy(update={"volume": 20_000_000})
        results = validate_bars(bars)
        spikes = [r for r in results if r.check == "bar_volume_spike"]
        assert len(spikes) == 1

    def test_detects_volume_drop(self) -> None:
        bars = _make_bars(25, 1_000_000)
        bars[-1] = bars[-1].model_copy(update={"volume": 50_000})
        results = validate_bars(bars)
        drops = [r for r in results if r.check == "bar_volume_drop"]
        assert len(drops) == 1

    def test_no_spurious_volume_anomalies(self) -> None:
        bars = _make_bars(25, 1_000_000)
        results = validate_bars(bars)
        anomalies = [r for r in results if r.check in ("bar_volume_spike", "bar_volume_drop")]
        assert len(anomalies) == 0
