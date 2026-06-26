"""Populate data/state.db with demo data for dashboard testing."""

from datetime import date, datetime, timedelta
from pathlib import Path

from alpha_quant.application.store import CanonicalStore
from alpha_quant.domain.events import CandidateBlocked, CandidatePromoted, CandidateScored
from alpha_quant.domain.journal import generate_journal
from alpha_quant.domain.models import PortfolioSnapshot, Position
from alpha_quant.domain.narration import NarrationContext, PositionNarration
from alpha_quant.domain.reporting import generate_monthly, generate_weekly

store = CanonicalStore(base_path=Path("data"))

equity = 100_000.0
start = date(2026, 4, 1)
for i in range(60):
    d = start + timedelta(days=i)
    if d.weekday() >= 5:
        continue
    change = equity * (0.002 * (i % 5 - 2))
    equity += change
    cash = equity * (0.2 + 0.1 * (i % 3))
    store.save_portfolio_snapshot(PortfolioSnapshot(date=d, cash=cash, equity=equity))

store._state_conn.execute(
    "INSERT OR REPLACE INTO runs (run_id, run_type, config_hash, start_ts, status)"
    " VALUES (?, ?, ?, ?, ?)",
    ["demo-run", "fixture", "demo", datetime(2026, 6, 11, 12, 0, 0), "completed"],
)

positions = [
    Position(
        symbol="AAPL",
        quantity=100.0,
        entry_price=185.0,
        avg_cost=185.0,
        current_price=192.0,
        stop_price=178.0,
        market_value=19_200.0,
        unrealized_pl=700.0,
    ),
    Position(
        symbol="MSFT",
        quantity=80.0,
        entry_price=420.0,
        avg_cost=420.0,
        current_price=435.0,
        stop_price=405.0,
        market_value=34_800.0,
        unrealized_pl=1_200.0,
    ),
    Position(
        symbol="GOOGL",
        quantity=60.0,
        entry_price=165.0,
        avg_cost=165.0,
        current_price=158.0,
        stop_price=150.0,
        market_value=9_480.0,
        unrealized_pl=-420.0,
    ),
]
for p in positions:
    store.save_position(p)

for sym in ("AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"):
    store.save_event(
        CandidateScored(
            event_id=f"scored-{sym}",
            timestamp=datetime(2026, 6, 11, 12, 0, 0),
            run_id="demo-run",
            source="pipeline",
            symbol=sym,
            composite_score=0.75,
            components={"technical": 0.8, "momentum": 0.6},
        )
    )
for sym, reason in [("AMZN", "low composite"), ("META", "RSI too high"), ("NVDA", "gap too large")]:
    store.save_event(
        CandidateBlocked(
            event_id=f"blocked-{sym}",
            timestamp=datetime(2026, 6, 11, 12, 0, 0),
            run_id="demo-run",
            source="pipeline",
            symbol=sym,
            reason=reason,
            gate="ranking",
        )
    )
store.save_event(
    CandidatePromoted(
        event_id="promoted-aapl",
        timestamp=datetime(2026, 6, 11, 12, 0, 0),
        run_id="demo-run",
        source="pipeline",
        symbol="AAPL",
        score=0.75,
        target_weight=0.05,
    )
)

positions_narr = [
    PositionNarration(
        symbol=p.symbol,
        shares=p.quantity,
        entry_price=p.entry_price,
        current_price=p.current_price,
        avg_cost=p.avg_cost,
        unrealized_pl=p.unrealized_pl,
        stop_price=p.stop_price,
        risk_pct=round((p.current_price - p.stop_price) / p.avg_cost * 100, 2)
        if p.stop_price
        else None,
    )
    for p in positions
]
ctx = NarrationContext(
    date=date(2026, 6, 11),
    regime="RISK_ON",
    data_health={"eodhd": True, "alpaca": True, "openinsider": True, "reddit": True, "sec": True},
    candidates_scored=6,
    candidates_blocked=3,
    candidates_promoted=1,
    positions=positions_narr,
    equity=100_000.0,
    cash=36_520.0,
    concept_of_day="moving averages",
)
store.save_journal(generate_journal(ctx))
store.save_report(generate_weekly([ctx], date(2026, 6, 11)))
store.save_report(generate_monthly([ctx], date(2026, 6, 30)))

print("Demo data seeded: data/state.db")
print(f"  Equity curve: 60 entries")
print(f"  Positions: {len(positions)}")
print(f"  Journal: {ctx.date}")
print(f"  Reports: weekly + monthly")
