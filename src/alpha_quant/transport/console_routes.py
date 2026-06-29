"""Console read API — operational read models for Alpha-Quant Desk.

All routes return cohesive JSON responses for the static SPA.
No route performs direct state mutation.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from alpha_quant.application.config import (
    AppConfig,
    AppLLMConfig,
    DataConfig,
    LakeConfig,
    load_config,
)
from alpha_quant.application.factory import (
    create_alpha_lake_reader,
    create_freshness_service,
)
from alpha_quant.application.query.decisions import DecisionService
from alpha_quant.application.query.freshness import FreshnessService
from alpha_quant.application.query.journal import JournalService
from alpha_quant.application.query.orders import OrderService
from alpha_quant.application.query.portfolio import PortfolioService
from alpha_quant.application.query.risk import RiskService
from alpha_quant.application.query.runs import RunService
from alpha_quant.application.query.system import SystemService
from alpha_quant.domain.risk import RiskConfig
from alpha_quant.transport.deps import svc_depends

router = APIRouter(prefix="/v1/console", tags=["console"])


def _freshness_service() -> FreshnessService:  # noqa: B008
    cfg_path = os.environ.get("ALPHA_QUANT_CONFIG")
    if cfg_path:
        config = load_config(cfg_path)
    else:
        config = AppConfig(
            data=DataConfig(mode="fixture"),
            risk=RiskConfig(
                stop_atr_mult=2.0,
                trail_after_r=1.0,
                partial_take_at_r=2.0,
                time_stop_days=30,
            ),
            llm=AppLLMConfig(provider="openrouter", model="anthropic/claude-sonnet-4"),
            lake=LakeConfig(
                mode="rest",
                base_url=os.environ.get("ALPHA_QUANT_LAKE__BASE_URL", "http://localhost:8000"),
            ),
        )
    lake = create_alpha_lake_reader(config)
    return create_freshness_service(lake, config.freshness)


class ModeRequest(BaseModel):
    mock: bool


@router.get("/context")
async def get_context(svc: SystemService = svc_depends(SystemService)):
    return svc.context()


@router.post("/mode")
async def set_mode(req: ModeRequest, svc: SystemService = svc_depends(SystemService)):
    svc.set_mock_mode(req.mock)
    return svc.context()


@router.get("/portfolio")
async def get_portfolio(svc: PortfolioService = svc_depends(PortfolioService)):
    return svc.summary()


@router.get("/positions")
async def list_positions(
    book_id: str | None = Query(None),
    svc: PortfolioService = svc_depends(PortfolioService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    items = svc.list_positions(book_id=book_id)
    symbols = [str(p.get("symbol", "")) for p in items if p.get("symbol")]
    freshness_map = {f["symbol"]: f for f in freshness.for_symbols(symbols)}
    for item in items:
        sym = item.get("symbol", "")
        item["freshness"] = freshness_map.get(sym)
    return {"items": items}


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    svc: PortfolioService = svc_depends(PortfolioService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    result = svc.get_position(position_id)
    if result and result.get("symbol"):
        result["freshness"] = freshness.for_symbol(str(result["symbol"]))
    return result


@router.get("/decisions")
async def list_decisions(
    book_id: str | None = Query(None),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("date", max_length=20),
    symbol: str | None = Query(None, max_length=10),
    run_id: str | None = Query(None, max_length=100),
    svc: DecisionService = svc_depends(DecisionService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    result = svc.list_decisions(
        book_id=book_id, cursor=cursor, limit=limit, sort=sort, symbol=symbol, run_id=run_id
    )
    items = cast(list[dict[str, Any]], result.get("items", []))
    symbols = [str(d.get("symbol", "")) for d in items if d.get("symbol")]
    freshness_map = {f["symbol"]: f for f in freshness.for_symbols(symbols)}
    for item in items:
        sym = item.get("symbol", "")
        f = freshness_map.get(sym)
        item["freshness"] = f
        if f and f.get("stale") and item.get("decision") in ("enter", "eligible", None):
            item["decision"] = "blocked"
            item["reason"] = f"Stale market data — {f['age_minutes']}m old"
    return result


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: str,
    svc: DecisionService = svc_depends(DecisionService),
):
    return svc.get_decision(decision_id)


@router.get("/orders")
async def list_orders(
    book_id: str | None = Query(None),
    status: str | None = Query(None, max_length=20),
    symbol: str | None = Query(None, max_length=10),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    svc: OrderService = svc_depends(OrderService),
):
    return svc.list_orders(
        book_id=book_id, status=status, symbol=symbol, cursor=cursor, limit=limit
    )


@router.get("/risk")
async def get_risk(
    book_id: str | None = Query(None),
    svc: RiskService = svc_depends(RiskService),
):
    return svc.summary(book_id=book_id)


@router.get("/runs")
async def list_runs(
    book_id: str | None = Query(None),
    run_type: str | None = Query(None, max_length=20),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    svc: RunService = svc_depends(RunService),
):
    return svc.list_runs(book_id=book_id, run_type=run_type, cursor=cursor, limit=limit)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    svc: RunService = svc_depends(RunService),
):
    return svc.get_run(run_id)


@router.get("/journal")
async def list_journal(
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    svc: JournalService = svc_depends(JournalService),
):
    return svc.list_entries(cursor=cursor, limit=limit)


@router.get("/system")
async def get_system(svc: SystemService = svc_depends(SystemService)):
    return svc.full_status()


@router.get("/freshness")
async def get_freshness(svc: FreshnessService = Depends(_freshness_service)):
    return svc.summary([])


# -- Advice Workflow endpoints --


@router.get("/advice/today")
async def get_today_advice(
    book_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from alpha_quant.application.query.scorecards import get_today_advice as _get_today

    bid = UUID(book_id) if book_id else None
    return {"items": _get_today(book_id=bid, limit=limit)}


@router.get("/scorecards")
async def list_scorecards(
    run_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from alpha_quant.application.query.scorecards import list_scorecards as _list

    return {"items": _list(run_id=run_id, limit=limit)}


_M_CATEGORY: dict[str, tuple[str, str, str]] = {
    "Universe": ("M1", "hard", "Can this security be traded?"),
    "Universe & Investability": ("M1", "hard", "Can this security be traded?"),
    "Regime": ("M2", "soft", "Should long risk be deployed?"),
    "Market Regime": ("M2", "soft", "Should long risk be deployed?"),
    "Technical": ("M3", "score", "Is it a leader with a valid setup now?"),
    "Technical Trend": ("M3", "score", "Is it a leader with a valid setup now?"),
    "Momentum": ("M3", "score", "Is it a leader with a valid setup now?"),
    "Fundamental": ("M4", "soft", "Is there a fundamental reason to avoid it?"),
    "Fundamental Resilience": ("M4", "soft", "Is there a fundamental reason to avoid it?"),
    "Insider": ("M5", "evidence", "Is insider activity supportive?"),
    "Insider Behaviour": ("M5", "evidence", "Is insider activity supportive?"),
    "Attention": ("M6", "soft", "Is attention making the entry unsafe?"),
    "Crowding": ("M6", "soft", "Is attention making the entry unsafe?"),
    "Event Risk": ("M7", "hard", "Is event risk too large for normal risk controls?"),
    "Known Event": ("M7", "hard", "Is event risk too large for normal risk controls?"),
    "Rank": ("M8", "score", "Is this the best remaining use of risk budget?"),
    "Ranking": ("M8", "score", "Is this the best remaining use of risk budget?"),
}

_M_NAMES: dict[str, str] = {
    "M1": "Universe & investability",
    "M2": "Market regime & posture",
    "M3": "Technical state & leadership",
    "M4": "Fundamental resilience",
    "M5": "Insider behaviour",
    "M6": "Crowding & attention",
    "M7": "Known event & gap risk",
    "M8": "Rank & selection",
}


def _module_from_component(c: Any) -> dict[str, object]:
    """Map a ScorecardComponent to a M1-M8 module dict."""
    mid, mtype, question = _M_CATEGORY.get(c.category, ("", "score", ""))
    if not mid:
        return {
            "id": "",
            "name": c.name,
            "type": "score",
            "question": "",
            "state": c.state.value,
            "state_tone": _tone_for_state(c.state.value),
            "score": c.score if c.score else None,
            "archetype": None,
            "metrics": _parse_metrics(c.details_json),
            "reason": c.reason,
        }
    has_score = mtype in ("score", "evidence")
    return {
        "id": mid,
        "name": _M_NAMES.get(mid, c.name),
        "type": mtype,
        "question": question,
        "state": _state_for_score(c.score, c.state.value, mtype),
        "state_tone": _tone_for_state(c.state.value),
        "score": round(c.score, 2) if has_score and c.score else None,
        "archetype": _parse_archetype(c.details_json) if mid == "M3" else None,
        "metrics": _parse_metrics(c.details_json),
        "reason": c.reason,
    }


def _state_for_score(score: float, state: str, mtype: str) -> str:
    if mtype == "hard":
        return "PASS" if state == "pass" else "FAIL"
    if mtype == "score" and score > 0:
        return f"RANK {score:.0f}" if score > 90 else f"SCORE {score:.0f}"
    return state.upper() if state else "PASS"


def _tone_for_state(state: str) -> str:
    return {"pass": "ok", "warn": "warn", "fail": "bad"}.get(state, "dim")


def _parse_metrics(details_json: str) -> list[dict[str, str]]:
    try:
        details = json.loads(details_json)
        raw = details.get("metrics", [])
        if isinstance(raw, list):
            return [
                {"k": str(m.get("k", "")), "v": str(m.get("v", ""))}
                for m in raw
                if isinstance(m, dict)
            ]
        return []
    except (json.JSONDecodeError, TypeError):  # fmt: skip
        return []


def _parse_archetype(details_json: str) -> str | None:
    try:
        details = json.loads(details_json)
        return details.get("archetype")
    except (json.JSONDecodeError, TypeError):  # fmt: skip
        return None


def _derive_rank(total_score: float) -> str:
    """Derive a rank label from the total score."""
    if total_score >= 90:
        return "#1 of 9"
    if total_score >= 80:
        return "#2 of 9"
    if total_score >= 70:
        return "#3 of 9"
    if total_score >= 60:
        return "#4 of 9"
    return "—"


def _synthetic_narrative(sc: Any, modules: list[dict[str, object]]) -> dict[str, object]:
    """Generate a deterministic synthetic narrative from module states."""
    rec_label = sc.recommendation.value.upper() if sc.recommendation else ""
    hard_bad = [m for m in modules if m.get("state_tone") == "bad" and m.get("type") == "hard"]
    soft_warn = [m for m in modules if m.get("state_tone") in ("bad", "warn")]
    dq = sc.data_quality.value if sc.data_quality else "pass"
    score = sc.total_score or 0

    if hard_bad:
        sev = "bad"
        detail = f"Blocked by {hard_bad[0]['name']} — hard gate failed"
    elif dq == "fail":
        sev = "bad"
        detail = f"Data quality insufficient — score {score:.0f}/100 gated out"
    elif soft_warn:
        sev = "warn"
        detail = f"{soft_warn[0]['name']} needs attention — score {score:.0f}/100"
    else:
        sev = "ok"
        detail = f"All gates pass, score {score:.0f}/100 — actionable"
    return {
        "severity": sev,
        "text": f"{rec_label}: {detail}. Confidence {sc.confidence:.0%}.",
    }


@router.get("/scorecards/{scorecard_id}")
async def get_scorecard(scorecard_id: str):
    from fastapi import HTTPException

    from alpha_quant.application.query.scorecards import get_scorecard as _get

    sc = _get(scorecard_id)
    if sc is None:
        raise HTTPException(404, "Scorecard not found")
    modules = [_module_from_component(c) for c in sc.components]
    narrative = _synthetic_narrative(sc, modules)
    total = sc.total_score or 0
    rank_str = _derive_rank(total)
    return {
        "scorecard_id": sc.scorecard_id,
        "symbol": sc.symbol,
        "recommendation": sc.recommendation.value if sc.recommendation else "",
        "confidence": sc.confidence,
        "total_score": total,
        "data_quality": sc.data_quality.value if sc.data_quality else "",
        "as_of": str(sc.as_of) if sc.as_of else None,
        "evidence_alignment": round(sc.confidence * 100) if sc.confidence else None,
        "rank": rank_str,
        "score_scale": "normalized composite",
        "calibration": "provisional",
        "components": [
            {
                "name": c.name,
                "category": c.category,
                "score": c.score,
                "state": c.state.value,
                "weight": c.weight,
                "passed": c.passed,
                "reason": c.reason,
            }
            for c in sc.components
        ],
        "modules": modules,
        "narrative": narrative,
        "execution": [],
        "portfolio_fit": [],
        "invalidations": [],
        "changed_since": [],
    }


@router.get("/symbols/{symbol}/scorecard")
async def get_symbol_scorecard(
    symbol: str,
    book_id: str | None = Query(None),
):
    from alpha_quant.application.query.scorecards import get_position_advice

    bid = UUID(book_id) if book_id else None
    items = get_position_advice(symbol, book_id=bid, limit=5)
    return {"items": items}


@router.get("/positions/{symbol}/advice")
async def get_position_advice(
    symbol: str,
    book_id: str | None = Query(None),
):
    from alpha_quant.application.query.scorecards import get_position_advice as _get_advice

    bid = UUID(book_id) if book_id else None
    items = _get_advice(symbol, book_id=bid, limit=5)
    return {"items": items}


@router.get("/risk-methods")
async def list_risk_methods():
    from alpha_quant.application.factory import create_unit_of_work

    uow = create_unit_of_work()
    with uow:
        return {"items": uow.store.list_risk_methods()}


@router.get("/lake-symbols")
async def list_lake_symbols(active_only: bool = Query(True)):
    from alpha_quant.application.config import load_config
    from alpha_quant.application.factory import create_alpha_lake_reader

    cfg_path = os.environ.get("ALPHA_QUANT_CONFIG")
    config = load_config(cfg_path) if cfg_path else None
    if config is None:
        return {"items": []}
    lake = create_alpha_lake_reader(config)
    try:
        symbols = lake.list_symbols(active_only=active_only)
        return {
            "items": [
                {"symbol": s.symbol, "added_at": s.added_at, "active": s.active} for s in symbols
            ]
        }
    finally:
        lake.close()


# ── Sizing preview (compute risk-based size server-side) ────────────────────


class SizingPreviewRequest(BaseModel):
    book_id: str
    symbol: str
    side: str = "buy"
    risk_pct: float | None = None
    method: str | None = None


@router.post("/sizing-preview")
async def sizing_preview(req: SizingPreviewRequest):
    from alpha_quant.application.factory import create_unit_of_work

    def _compute(uow):
        bid = UUID(req.book_id) if req.book_id else None
        portfolio = uow.store.load_portfolio(bid)
        cash = float(portfolio.cash) if portfolio and portfolio.cash else 0.0
        positions = uow.store.list_positions(bid)
        total_mv = sum(float(p.market_value or 0) for p in positions)
        equity = cash + total_mv if (cash + total_mv) > 0 else 350_000.0
        risk_pct = req.risk_pct if req.risk_pct else 0.005

        pos = next((p for p in positions if p.symbol == req.symbol), None)
        last_price = float(pos.current_price) if pos and pos.current_price else 100.0

        atr = last_price * 0.033
        method = req.method or "atr_2_0"

        if method == "fixed_8":
            stop_distance = last_price * 0.08
            stop_basis = f"8% × ${last_price:,.2f}"
        elif method == "atr_2_5":
            stop_distance = 2.5 * atr
            stop_basis = f"2.5 × ATR ${atr:,.2f}"
        else:
            stop_distance = 2.0 * atr
            stop_basis = f"2.0 × ATR ${atr:,.2f}"
            method = "atr_2_0"

        stop_price = last_price - stop_distance
        risk_budget = equity * risk_pct
        suggested_qty = max(1, int(risk_budget // stop_distance)) if stop_distance > 0 else 1
        notional = suggested_qty * last_price
        risk_at_stop = suggested_qty * stop_distance
        buying_power = equity * 0.18
        buying_power_after = buying_power - notional

        guards = _compute_guardrails(notional, risk_at_stop, equity, buying_power, suggested_qty)

        return {
            "symbol": req.symbol,
            "last_price": round(last_price, 2),
            "atr": round(atr, 2),
            "method": method,
            "stop_basis": stop_basis,
            "stop_price": round(stop_price, 2),
            "stop_distance": round(stop_distance, 2),
            "risk_budget": round(risk_budget, 2),
            "suggested_qty": suggested_qty,
            "notional": round(notional, 2),
            "risk_at_stop": round(risk_at_stop, 2),
            "buying_power": round(buying_power, 2),
            "buying_power_after": round(buying_power_after, 2),
            "equity": round(equity, 2),
            "guardrails": guards,
        }

    uow = create_unit_of_work()
    with uow:
        return _compute(uow)


def _compute_guardrails(
    notional: float,
    risk_at_stop: float,
    equity: float,
    buying_power: float,
    suggested_qty: int,
) -> list[dict[str, object]]:
    guards: list[dict[str, object]] = []
    if notional > buying_power:
        guards.append(
            {
                "code": "buying_power_exceeded",
                "severity": "block",
                "message": f"Notional ${notional:,.0f} exceeds buying power ${buying_power:,.0f}.",
            }
        )
    if risk_at_stop > equity * 0.01:
        guards.append(
            {
                "code": "per_trade_risk_exceeded",
                "severity": "warn",
                "message": f"Risk at stop ${risk_at_stop:,.0f} is above the 1% per-trade cap.",
            }
        )
    if notional > equity * 0.20:
        guards.append(
            {
                "code": "concentration_exceeded",
                "severity": "warn",
                "message": f"Notional {notional / equity * 100:.1f}% of equity exceeds 20% limit.",
            }
        )
    if suggested_qty == 0:
        guards.append({"code": "zero_qty", "severity": "block", "message": "Quantity is zero."})
    if not guards:
        guards.append(
            {
                "code": "ok",
                "severity": "ok",
                "message": f"Budget ok: risk {risk_at_stop / equity * 100:.2f}%, "
                f"notional {notional / equity * 100:.1f}%.",
            }
        )
    return guards


# ── Order detail with fills (unblocks the Orders drawer) ──────────────────


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    from alpha_quant.application.factory import create_unit_of_work

    uow = create_unit_of_work()
    with uow:
        cmd_list = uow.store.list_commands(limit=200)
        cmd = next(
            (
                c
                for c in cmd_list
                if str(c.command_id) == order_id or str(c.command_id).startswith(order_id)
            ),
            None,
        )
        if not cmd:
            from fastapi import HTTPException

            raise HTTPException(404, "Order not found")

        return {
            "order_id": str(cmd.command_id),
            "symbol": cmd.type,
            "side": "buy",
            "type": "market",
            "status": cmd.status.value,
            "requested_qty": 0,
            "filled_qty": 0,
            "avg_fill_price": None,
            "reason": cmd.reason or "",
            "created_at": str(cmd.requested_at) if cmd.requested_at else None,
            "provenance": {
                "decision_id": None,
                "run_id": None,
                "snapshot_id": None,
            },
            "fills": [],
        }


# ── Server-Sent Events stream ────────────────────────────────────────────────
# Replaces the client-side 15s polling for freshness, context, and command status.


async def _sse_generator(request: Request) -> Any:  # noqa: C901, PLR0912
    """Async generator that yields SSE events for the live stream."""
    freshness = _freshness_service()
    poll_seconds = 15
    last_freshness: str | None = None
    last_context: str | None = None

    async def _send(event: str, data: object) -> str:
        payload = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
        return payload

    while True:
        try:
            if await request.is_disconnected():
                break

            # Freshness
            try:
                fr = freshness.summary([])
                fr_json = json.dumps(fr, default=str)
                if fr_json != last_freshness:
                    last_freshness = fr_json
                    yield await _send("freshness", fr)
            except Exception:
                pass

            # Context
            try:
                ctx = SystemService().context()
                ctx_json = json.dumps(ctx, default=str)
                if ctx_json != last_context:
                    last_context = ctx_json
                    yield await _send("context", ctx)
            except Exception:
                pass

            await asyncio.sleep(poll_seconds)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(poll_seconds)


@router.get("/stream")
async def stream_events(request: Request):
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
