"""DailyCycleService — unified PostgreSQL-backed decision run orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog

from alpha_quant.application.scorecards import (
    PortfolioContext,
    PositionContext,
    generate_scorecards,
)
from alpha_quant.contracts.alpha_lake import FactsBundle
from alpha_quant.contracts.operational import (
    PortfolioMark,
    RunKind,
    RunReservation,
    RunStatus,
)
from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.models import Decision, Fill, Position
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort

logger = structlog.get_logger()


@dataclass
class DailyCycleResult:
    decision_run_id: UUID
    run_key: str
    scorecard_count: int
    decisions: list[Decision]
    fills: list[Fill]
    events: list[DomainEvent]
    regime: str = "RISK_ON"
    prev_equity: Decimal = Decimal("0")
    new_equity: Decimal = Decimal("0")
    halted: bool = False


@dataclass
class _RunState:
    positions: dict[str, Position] = field(default_factory=dict)
    cash: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    regime: str = "RISK_ON"
    max_positions: int = 10


class DailyCycleService:
    """Orchestrates a daily decision run with PostgreSQL persistence.

    Flow: reserve_run → fetch_facts → scorecards → decide → mark → persist → complete
    """

    def __init__(
        self,
        alpha_lake: AlphaLakeReadPort,
        store: Any,
    ) -> None:
        self._alpha_lake = alpha_lake
        self._store = store

    def run(
        self,
        book_id: UUID,
        as_of: datetime | None = None,
        snapshot_id: str | None = None,
        run_key: str | None = None,
        run_kind: RunKind = RunKind.DAILY,
        discovery_symbols: list[str] | None = None,
        strategy_version_id: UUID | None = None,
    ) -> DailyCycleResult:
        now = as_of or datetime.now(UTC)
        today = now.date()

        strategy_version_id = strategy_version_id or UUID("00000000-0000-0000-0000-000000000001")

        # -- Load current portfolio --
        portfolio = self._store.load_portfolio(book_id)
        state = _RunState(
            cash=portfolio.cash,
            max_positions=10,
        )
        total_mv = 0.0
        for p in portfolio.positions:
            pos = Position(
                symbol=p.symbol,
                quantity=float(p.quantity),
                entry_price=float(p.avg_cost),
                avg_cost=float(p.avg_cost),
                current_price=float(p.current_price or p.avg_cost),
                stop_price=float(p.stop_price) if p.stop_price else None,
                market_value=float(p.market_value or 0),
                unrealized_pl=float(p.unrealized_pl or 0),
            )
            state.positions[p.symbol] = pos
            total_mv += float(p.market_value or 0)
        state.equity = state.cash + Decimal(str(total_mv))

        # -- Reserve run --
        run_key_str = run_key or f"daily-{today.isoformat()}-{uuid4().hex[:8]}"
        run = self._store.reserve_run(
            RunReservation(
                run_key=run_key_str,
                run_kind=run_kind,
                strategy_version_id=strategy_version_id,
                portfolio_book_id=book_id,
                decision_as_of=now,
                resolved_snapshot_id=snapshot_id or "",
                alpha_lake_api_version="1.0",
                alpha_lake_contract_version="1.0",
                config_hash="",
                request_hash="",
                response_hash="",
            )
        )
        self._store.start_run(run.decision_run_id)

        # -- Skip if halted --
        halt = self._store.current_halt(book_id)
        if halt and halt.halted:
            logger.warning("book_halted", book_id=str(book_id))
            self._store.complete_run(run.decision_run_id, RunStatus.HALTED.value)
            return DailyCycleResult(
                decision_run_id=run.decision_run_id,
                run_key=run_key_str,
                scorecard_count=0,
                decisions=[],
                fills=[],
                events=[],
                halted=True,
            )

        try:
            # -- Fetch observations from Alpha-Lake --
            symbols_in_portfolio = list(state.positions.keys()) or ["SPY"]
            discovery = discovery_symbols or []
            all_symbols = list(set(symbols_in_portfolio + discovery + ["SPY"]))

            self._alpha_lake.read_observations(all_symbols, as_of=now)

            # -- Fetch facts bundles for scoring --
            symbols_to_score = [s for s in all_symbols if s != "SPY"]
            facts_bundles: dict[str, FactsBundle] = {}
            spy_facts: FactsBundle | None = None
            for s in symbols_to_score + ["SPY"]:
                try:
                    fb = self._alpha_lake.read_facts_bundle(s, now)
                    if s == "SPY":
                        spy_facts = fb
                    else:
                        facts_bundles[s] = fb
                except Exception:
                    continue

            # -- Generate scorecards --
            portfolio_ctx = PortfolioContext(
                equity=float(state.equity),
                cash=float(state.cash),
                max_positions=state.max_positions,
                discovery_symbols=discovery,
            )
            for sym, pos in state.positions.items():
                if pos.quantity != 0:
                    portfolio_ctx.positions[sym] = PositionContext(
                        symbol=sym,
                        quantity=pos.quantity,
                        avg_cost=pos.avg_cost,
                        current_price=pos.current_price,
                        stop_price=pos.stop_price,
                        market_value=pos.market_value,
                        unrealized_pl=pos.unrealized_pl,
                    )

            scorecards = generate_scorecards(
                facts_bundles,
                portfolio_ctx,
                as_of=now,
                spy_bundle=spy_facts,
            )

            # -- Persist scorecards --
            run_id_str = str(run.decision_run_id)
            for sc in scorecards:
                self._store.save_scorecard(sc, run_id_str)

            # -- Persist portfolio mark --
            total_mv_end = sum(float(p.market_value or 0) for p in state.positions.values())
            new_equity = state.cash + Decimal(str(total_mv_end))
            mark = PortfolioMark(
                mark_id=uuid4(),
                portfolio_book_id=book_id,
                effective_date=today,
                cash=state.cash,
                equity=new_equity,
                gross_exposure=Decimal(str(total_mv_end)),
                regime=state.regime,
                mark_as_of=now,
            )
            self._store.save_portfolio_mark(mark)

            # -- Rebuild projections --
            self._store.rebuild_projections(book_id)

            # -- Complete run --
            self._store.complete_run(run.decision_run_id, RunStatus.COMPLETED.value)

            return DailyCycleResult(
                decision_run_id=run.decision_run_id,
                run_key=run_key_str,
                scorecard_count=len(scorecards),
                decisions=[],
                fills=[],
                events=[],
                regime=state.regime,
                prev_equity=state.equity,
                new_equity=new_equity,
            )

        except Exception as e:
            logger.exception("daily_cycle_failed", error=str(e))
            self._store.complete_run(
                run.decision_run_id,
                RunStatus.FAILED.value,
                failure_reason=str(e),
            )
            return DailyCycleResult(
                decision_run_id=run.decision_run_id,
                run_key=run_key_str,
                scorecard_count=0,
                decisions=[],
                fills=[],
                events=[],
            )
