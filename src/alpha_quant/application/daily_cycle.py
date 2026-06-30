"""DailyCycleService — unified PostgreSQL-backed decision run orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import structlog
from sqlalchemy import text

from alpha_quant.application.advice_llm import AdviceLLMService, PortfolioSummary
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
from alpha_quant.ports.clock import Clock

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
        clock: Clock,
        llm: Any = None,
    ) -> None:
        self._alpha_lake = alpha_lake
        self._store = store
        self._clock = clock
        self._advice_service = AdviceLLMService(llm) if llm else None

    def _resolve_trading_day(self, as_of: datetime) -> datetime:
        """Walk back from as_of to find a date with sufficient technical readouts."""
        from datetime import timedelta

        candidate = as_of
        for _ in range(7):
            try:
                fb = self._alpha_lake.read_facts_bundle("AAPL", candidate)
                if len(fb.sections.readouts) >= 15:
                    return candidate
            except Exception:
                pass
            candidate = candidate - timedelta(days=1)
        return as_of

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
        now = self._resolve_trading_day(as_of or self._clock.now())
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
            symbols_in_portfolio = list(state.positions.keys())
            discovery = discovery_symbols or []
            if not symbols_in_portfolio and not discovery:
                discovery = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
            all_symbols = list(set(symbols_in_portfolio + discovery + ["SPY"]))

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

            # -- Determine market regime from SPY trend --
            if spy_facts:
                from alpha_quant.application.scorecards import _readout_value

                spy_regime = _readout_value(spy_facts, "trend.regime")
                if spy_regime is not None:
                    if spy_regime >= 40:
                        state.regime = "RISK_ON"
                    elif spy_regime >= 20:
                        state.regime = "CAUTION"
                    else:
                        state.regime = "RISK_OFF"

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
                strategy_version_id=str(strategy_version_id),
            )
            # -- Persist scorecards --
            run_id_str = str(run.decision_run_id)
            book_id_str = str(book_id)
            for sc in scorecards:
                sec_ref = self._store.session.execute(
                    text("SELECT security_id FROM core.security_reference WHERE symbol = :sym"),
                    {"sym": sc.symbol},
                ).fetchone()
                if sec_ref:
                    sec_id = str(sec_ref._mapping["security_id"])
                else:
                    sec_id = str(uuid5(NAMESPACE_DNS, sc.symbol + ".com"))
                    self._store.session.execute(
                        text("""
                            INSERT INTO core.security_reference (security_id, symbol)
                            VALUES (:sid, :sym)
                            ON CONFLICT (symbol) DO NOTHING
                        """),
                        {"sid": sec_id, "sym": sc.symbol},
                    )
                sc_with_ids = sc.model_copy(
                    update={
                        "portfolio_book_id": book_id_str,
                        "decision_run_id": run_id_str,
                        "security_id": sec_id,
                    }
                )
                self._store.save_scorecard(sc_with_ids, run_id_str)

                # Generate advice artifact for each scorecard
                if self._advice_service and sc_with_ids.scorecard_id:
                    try:
                        portfolio_summary = PortfolioSummary(
                            equity=float(state.equity),
                            cash=float(state.cash),
                            position_count=len(state.positions),
                            regime=state.regime,
                        )
                        advice = self._advice_service.generate_advice(
                            sc_with_ids, portfolio_summary
                        )
                        self._store.save_advice_artifact(advice)
                    except Exception:
                        logger.exception("advice_generation_failed", symbol=sc.symbol)

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
