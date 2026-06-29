from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from sqlalchemy import text as _sql

from alpha_quant.adapters.postgres import create_engine, create_session

MOCK_BOOK_ID = "00000000-0000-0000-0000-000000000002"
DEFAULT_BOOK_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_STRATEGY_VERSION_ID = "00000000-0000-0000-0000-000000000001"

MOCK_URL = "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"

TICKERS = [
    ("AAPL", "Apple Inc.", "Technology"),
    ("MSFT", "Microsoft Corp.", "Technology"),
    ("GOOGL", "Alphabet Inc.", "Communication"),
    ("NVDA", "NVIDIA Corp.", "Technology"),
    ("AMZN", "Amazon.com Inc.", "Consumer Cyclical"),
    ("SPY", "SPDR S&P 500 ETF", "ETF"),
    ("TSLA", "Tesla Inc.", "Consumer Cyclical"),
    ("JPM", "JPMorgan Chase & Co.", "Financial"),
    ("XOM", "Exxon Mobil Corp.", "Energy"),
    ("BRK.B", "Berkshire Hathaway B", "Financial"),
]


def _now() -> datetime:
    return datetime.now(UTC)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


TABLE_ORDER_REVERSE = [
    "audit.operator_override",
    "audit.risk_event",
    "audit.halt_transition",
    "audit.audit_event",
    "trade.cash_ledger_entry",
    "trade.corporate_action_booking",
    "trade.paper_fill",
    "trade.paper_order",
    "trade.portfolio_mark",
    "run.advice_artifact",
    "run.scorecard_component",
    "run.scorecard",
    "run.policy_evaluation",
    "run.candidate_evaluation",
    "run.alpha_lake_manifest",
    "run.decision_run",
    "projection.position_risk_current",
    "projection.position_current",
    "projection.portfolio_current",
    "ops.current_halt",
    "ops.command",
    "ops.run_lock_audit",
    "core.book_risk_profile",
    "core.security_reference",
]


def seed_dev_data(database_url: str | None = None) -> tuple[int, int]:
    url = database_url or MOCK_URL
    engine = create_engine(url)
    _txt = _sql

    def _exec(s, **k):
        return session.execute(_txt(s), k)

    _clear_data(engine, _txt)
    book_id = _create_mock_book(engine, _txt)

    session_factory = create_session(engine)

    with session_factory() as session:
        rid_1 = str(uuid4())
        rid_2 = str(uuid4())
        rid_3 = str(uuid4())
        now = _now()
        bid = book_id
        svid = DEFAULT_STRATEGY_VERSION_ID

        # --- Security References ---
        sec_ids: dict[str, str] = {}
        for sym, name, sector in TICKERS:
            sid = str(uuid5(NAMESPACE_DNS, sym + ".com"))
            sec_ids[sym] = sid
            _exec(
                "INSERT INTO core.security_reference (security_id, symbol, display_name, sector) "
                "VALUES (:sid, :sym, :name, :sector) ON CONFLICT (security_id) DO NOTHING",
                sid=sid,
                sym=sym,
                name=name,
                sector=sector,
            )

        # --- Execution Profiles ---
        ep_default = str(uuid4())
        ep_aggressive = str(uuid4())
        session.execute(
            _txt(
                "INSERT INTO core.execution_profile (profile_id, name, slippage_bps, spread_model) "
                "VALUES (:pid, :name, :slippage, :model)"
            ),
            [
                {"pid": ep_default, "name": "default", "slippage": 1, "model": "fixed"},
                {"pid": ep_aggressive, "name": "aggressive", "slippage": 3, "model": "adaptive"},
            ],
        )

        # --- Risk Methods ---
        rm_param = str(uuid4())
        rm_hist = str(uuid4())
        rm_mc = str(uuid4())
        session.execute(
            _txt(
                "INSERT INTO core.risk_method (risk_method_id, name, description, method_type, "
                "default_params_json, is_active) "
                "VALUES (:rid, :name, :desc, :type, :params, :active)"
            ),
            [
                {
                    "rid": rm_param,
                    "name": "Parametric VaR",
                    "desc": "Variance-covariance with EWMA volatility",
                    "type": "parametric",
                    "params": '{"confidence": 0.99, "decay": 0.94}',
                    "active": True,
                },
                {
                    "rid": rm_hist,
                    "name": "Historical VaR",
                    "desc": "Historical simulation over 252-day window",
                    "type": "historical",
                    "params": '{"confidence": 0.99, "window": 252}',
                    "active": True,
                },
                {
                    "rid": rm_mc,
                    "name": "Monte Carlo VaR",
                    "desc": "Monte Carlo simulation with 10,000 paths",
                    "type": "monte_carlo",
                    "params": '{"confidence": 0.99, "paths": 10000}',
                    "active": True,
                },
            ],
        )

        # --- Decision Runs ---
        for _rid, _status, _started, _completed in [
            (rid_1, "completed", _days_ago(0), _now()),
            (rid_2, "completed", _days_ago(1), _days_ago(1) + timedelta(minutes=12)),
            (rid_3, "failed", _days_ago(2), _days_ago(2) + timedelta(minutes=3)),
        ]:
            _exec(
                "INSERT INTO run.decision_run (decision_run_id, run_key, run_kind, status, "
                "strategy_version_id, portfolio_book_id, decision_as_of, resolved_snapshot_id, "
                "alpha_lake_api_version, alpha_lake_contract_version, config_hash, request_hash, "
                "response_hash, started_at, completed_at) "
                "VALUES (:rid, :rk, 'daily', :status, :svid, :pbid, :dao, '', '1.0', '1.0', "
                "'', '', '', :start, :comp)",
                rid=_rid,
                rk=f"run-{_rid[:8]}",
                status=_status,
                svid=svid,
                pbid=bid,
                dao=_started,
                start=_started,
                comp=_completed,
            )
            if _status == "completed":
                _exec(
                    "INSERT INTO run.alpha_lake_manifest (manifest_id, decision_run_id, "
                    "request_body, response_body, snapshot_id, contract_version, api_version, "
                    "request_hash, response_hash, created_at) "
                    "VALUES (:mid, :rid, '{}', '{}', 'snap-001', '1.0', '1.0', '', '', :now)",
                    mid=str(uuid4()),
                    rid=_rid,
                    now=_started,
                )

        # --- Current Halt ---
        _exec(
            "INSERT INTO ops.current_halt (book_id, halted, reason, details, halted_at) "
            "VALUES (:bid, false, NULL, NULL, NULL) "
            "ON CONFLICT (book_id) DO UPDATE SET halted = false, reason = NULL",
            bid=bid,
        )

        # --- Portfolio Current ---
        _exec(
            "INSERT INTO projection.portfolio_current (book_id, cash, equity, gross_exposure, "
            "regime, updated_at) "
            "VALUES (:bid, 500000, 583550, 83550, 'RISK_ON', :now) "
            "ON CONFLICT (book_id) DO UPDATE SET cash = 500000, equity = 583550, "
            "gross_exposure = 83550, updated_at = :now",
            bid=bid,
            now=now,
        )

        # --- Positions ---
        for sym, ac, cp, upl, qty, mv in [
            ("AAPL", 150.00, 155.00, 500.00, 100, 15500),
            ("MSFT", 380.00, 395.00, 1500.00, 50, 19750),
            ("GOOGL", 165.00, 172.00, 700.00, 80, 13760),
            ("NVDA", 850.00, 910.00, 6000.00, 30, 27300),
            ("AMZN", 175.00, 181.00, 600.00, 40, 7240),
        ]:
            _exec(
                "INSERT INTO projection.position_current (book_id, security_id, symbol, "
                "quantity, avg_cost, current_price, market_value, unrealized_pl) "
                "VALUES (:bid, :sid, :sym, :qty, :ac, :cp, :mv, :upl)",
                bid=bid,
                sid=sec_ids[sym],
                sym=sym,
                qty=qty,
                ac=ac,
                cp=cp,
                mv=mv,
                upl=upl,
            )

        # --- Position Risk Current ---
        for sym in ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]:
            _exec(
                "INSERT INTO projection.position_risk_current (book_id, security_id, "
                "risk_method_id, stop_price, trail_price, trail_activation_pct, "
                "time_stop_date, auto_trail_enabled, last_adjusted_at, last_adjustment_reason) "
                "VALUES (:bid, :sid, :rmid, 140.00, NULL, NULL, NULL, true, :now, 'Initial')",
                bid=bid,
                sid=sec_ids[sym],
                rmid=rm_param,
                now=now,
            )

        # --- Candidates ---
        cand_ids: dict[str, str] = {}
        for sym, score, _blocked, reason in [
            ("AAPL", 82.5, False, None),
            ("MSFT", 76.3, False, None),
            ("GOOGL", 71.0, False, None),
            ("NVDA", 88.2, False, None),
            ("AMZN", 65.4, False, None),
            ("SPY", 45.0, True, "Not in universe"),
            ("TSLA", 92.1, False, None),
            ("JPM", 58.7, False, None),
            ("XOM", 43.2, False, None),
            ("BRK.B", 39.8, False, None),
        ]:
            cid = str(uuid4())
            cand_ids[sym] = cid
            _exec(
                "INSERT INTO run.candidate_evaluation (candidate_id, decision_run_id, "
                "portfolio_book_id, security_id, symbol, composite_score, regime, blocked, "
                "block_reason, gate_results) "
                "VALUES (:cid, :rid, :bid, :sid, :sym, :score, 'RISK_ON', :blocked, "
                ":reason, '{}')",
                cid=cid,
                rid=rid_1,
                bid=bid,
                sid=sec_ids[sym],
                sym=sym,
                score=score,
                blocked=bool(reason) if reason else False,
                reason=reason or "",
            )

        # --- Policy Evaluations ---
        for _sym, cid in cand_ids.items():
            for pname, pscore, ppassed in [
                ("Momentum Filter", 0.8, True),
                ("Value Screen", 0.6, True),
                ("Risk Cap", 0.9, True),
            ]:
                _exec(
                    "INSERT INTO run.policy_evaluation (evaluation_id, candidate_id, "
                    "policy_name, policy_version, score, passed, reason, details_json) "
                    "VALUES (:eid, :cid, :pname, 'v1', :pscore, :ppassed, '', '{}')",
                    eid=str(uuid4()),
                    cid=cid,
                    pname=pname,
                    pscore=pscore,
                    ppassed=ppassed,
                )

        # --- Scorecards ---
        scorecard_ids: dict[str, str] = {}
        for sym, rec, conf, total, dq in [
            ("NVDA", "consider_entry", 0.85, 88.2, "pass"),
            ("TSLA", "watch", 0.60, 72.5, "warn"),
            ("AAPL", "hold", 0.75, 79.0, "pass"),
            ("MSFT", "add", 0.80, 81.4, "pass"),
            ("AMZN", "watch", 0.55, 65.0, "warn"),
        ]:
            scid = str(uuid4())
            scorecard_ids[sym] = scid
            _exec(
                "INSERT INTO run.scorecard (scorecard_id, decision_run_id, portfolio_book_id, "
                "symbol, security_id, as_of, snapshot_id, facts_hash, config_hash, "
                "strategy_version, recommendation, confidence, total_score, data_quality, "
                "created_at) "
                "VALUES (:scid, :rid, :bid, :sym, :sid, :now, 'snap-001', '', '', 'v1', "
                ":rec, :conf, :total, :dq, :now)",
                scid=scid,
                rid=rid_1,
                bid=bid,
                sym=sym,
                sid=sec_ids[sym],
                now=now,
                rec=rec,
                conf=conf,
                total=total,
                dq=dq,
            )

            # --- Scorecard Components (M1-M8) ---
            for mname, mcat, mscore, mstate, mweight, mpassed, mreason, mdetail in [
                (
                    "Universe & Investability",
                    "Universe",
                    100,
                    "pass",
                    1.0,
                    True,
                    "Security is tradeable",
                    '{"metrics": [{"k":"Market Cap","v":"$2.8T"},{"k":"ADV","v":"$45B"}]}',
                ),
                (
                    "Market Regime",
                    "Market Regime",
                    85,
                    "pass",
                    1.0,
                    True,
                    "Regime is RISK_ON",
                    '{"metrics": [{"k":"VIX","v":"14.2"},{"k":"Trend","v":"Bull"}]}',
                ),
                (
                    "Technical Trend",
                    "Technical",
                    88,
                    "pass",
                    2.5,
                    True,
                    "Above 50/200 DMA, strong momentum",
                    '{"metrics": [{"k":"RSI(14)","v":"62"},'
                    '{"k":"50DMA","v":"$148"},{"k":"200DMA","v":"$135"}]}',
                ),
                (
                    "Fundamental Resilience",
                    "Fundamental",
                    75,
                    "pass",
                    1.5,
                    True,
                    "Strong margins, growing FCF",
                    '{"metrics": [{"k":"P/E","v":"28"},{"k":"FCF Yield","v":"3.2%"}]}',
                ),
                (
                    "Insider Behaviour",
                    "Insider",
                    60,
                    "warn",
                    1.0,
                    True,
                    "Minor insider selling detected",
                    '{"metrics": [{"k":"Insider 30d","v":"-0.02%"}]}',
                ),
                (
                    "Crowding & Attention",
                    "Attention",
                    70,
                    "warn",
                    1.0,
                    True,
                    "Elevated social volume",
                    '{"metrics": [{"k":"Social 7d","v":"+15%"}]}',
                ),
                (
                    "Known Event Risk",
                    "Event Risk",
                    100,
                    "pass",
                    1.0,
                    True,
                    "No events in window",
                    '{"metrics": [{"k":"Next Earnings","v":"28d"}]}',
                ),
                (
                    "Rank & Selection",
                    "Rank",
                    82,
                    "pass",
                    2.0,
                    True,
                    "Top quartile in peer group",
                    '{"metrics": [{"k":"Peer Rank","v":"3/10"},{"k":"Z-Score","v":"1.4"}]}',
                ),
            ]:
                _exec(
                    "INSERT INTO run.scorecard_component (component_id, scorecard_id, name, "
                    "category, score, state, weight, passed, reason, details_json) "
                    "VALUES (:compid, :scid, :name, :cat, :score, :state, :weight, "
                    ":passed, :reason, :details)",
                    compid=str(uuid4()),
                    scid=scid,
                    name=mname,
                    cat=mcat,
                    score=mscore,
                    state=mstate,
                    weight=mweight,
                    passed=mpassed,
                    reason=mreason,
                    details=mdetail,
                )

        # --- Advice Artifacts ---
        for sym, rec in [("NVDA", "consider_entry"), ("TSLA", "watch")]:
            scid = scorecard_ids.get(sym, str(uuid4()))
            _exec(
                "INSERT INTO run.advice_artifact (advice_id, scorecard_id, llm_provider, "
                "llm_model, prompt_version, input_hash, output_hash, validation_status, "
                "recommendation, headline, summary, rationale_json, risks_json, "
                "deterministic_differs, created_at) "
                "VALUES (:aid, :scid, 'anthropic', 'claude-sonnet-4', 'v1', '', '', "
                "'verified', :rec, :headline, :summary, :rationale, :risks, false, :now)",
                aid=str(uuid4()),
                scid=scid,
                rec=rec,
                headline=f"{sym}: compelling risk/reward setup",
                summary=f"{sym} shows strong technical momentum with supportive fundamentals.",
                rationale='{"factors":["Momentum > 80","Regime aligned","Low event risk"]}',
                risks='{"primary":"Rate sensitivity","secondary":"Sector rotation"}',
                now=now,
            )

        # --- Orders & Fills (needed by rebuild_projections) ---
        order_defs = [
            ("MSFT", 50, 395.00, "buy"),
            ("AAPL", 100, 150.00, "buy"),
            ("GOOGL", 80, 165.00, "buy"),
            ("NVDA", 30, 850.00, "buy"),
            ("AMZN", 40, 175.00, "buy"),
        ]
        order_ids: list[str] = []
        for sym, qty, price, side in order_defs:
            oid = str(uuid4())
            order_ids.append(oid)
            _exec(
                "INSERT INTO trade.paper_order (order_id, decision_run_id, portfolio_book_id, "
                "security_id, symbol, side, quantity, status, idempotency_key, "
                "filled_quantity, submitted_at) "
                "VALUES (:oid, :rid, :bid, :sid, :sym, :side, :qty, 'filled', :ik, :qty, :sub)",
                oid=oid,
                rid=rid_1,
                bid=bid,
                sid=sec_ids[sym],
                sym=sym,
                side=side,
                qty=qty,
                ik=f"ik-{oid[:8]}",
                sub=_days_ago(0),
            )
            _exec(
                "INSERT INTO trade.paper_fill (fill_id, order_id, security_id, symbol, side, "
                "quantity, price, fill_key, quality, fee, booked_at) "
                "VALUES (:fid, :oid, :sid, :sym, :side, :qty, :price, :fk, 'open', 0, :now)",
                fid=str(uuid4()),
                oid=oid,
                sid=sec_ids[sym],
                sym=sym,
                side=side,
                qty=qty,
                price=price,
                fk=f"fill-{sym.lower()}-1",
                now=now,
            )

        # --- Extra orders: pending sell AAPL + cancelled sell TSLA ---
        ord_extra_1 = str(uuid4())
        _exec(
            "INSERT INTO trade.paper_order (order_id, decision_run_id, portfolio_book_id, "
            "security_id, symbol, side, quantity, status, idempotency_key, "
            "filled_quantity, submitted_at) "
            "VALUES (:oid, :rid, :bid, :sid, :sym, 'sell', 25, 'pending', :ik, 0, :sub)",
            oid=ord_extra_1,
            rid=rid_1,
            bid=bid,
            sid=sec_ids["AAPL"],
            sym="AAPL",
            ik=f"ik-{ord_extra_1[:8]}",
            sub=_days_ago(0),
        )
        ord_extra_2 = str(uuid4())
        _exec(
            "INSERT INTO trade.paper_order (order_id, decision_run_id, portfolio_book_id, "
            "security_id, symbol, side, quantity, status, idempotency_key, "
            "filled_quantity, submitted_at) "
            "VALUES (:oid, :rid, :bid, :sid, :sym, 'sell', 10, 'cancelled', :ik, 0, :sub)",
            oid=ord_extra_2,
            rid=rid_2,
            bid=bid,
            sid=sec_ids["TSLA"],
            sym="TSLA",
            ik=f"ik-{ord_extra_2[:8]}",
            sub=_days_ago(1),
        )

        # --- Cash Ledger Entry ---
        for sym, qty, price in [
            ("MSFT", 50, 395.00),
            ("AAPL", 100, 150.00),
            ("GOOGL", 80, 165.00),
            ("NVDA", 30, 850.00),
            ("AMZN", 40, 175.00),
        ]:
            _exec(
                "INSERT INTO trade.cash_ledger_entry (entry_id, portfolio_book_id, fill_id, "
                "amount, currency, reason, booked_at) "
                "VALUES (:eid, :bid_outer, (SELECT fill_id FROM trade.paper_fill "
                "WHERE order_id = (SELECT order_id FROM trade.paper_order "
                "WHERE symbol = :sym AND portfolio_book_id = :bid_inner AND side = 'buy' "
                "ORDER BY submitted_at DESC LIMIT 1) LIMIT 1), "
                ":amt, 'USD', :reason, :now)",
                eid=str(uuid4()),
                bid_outer=bid,
                bid_inner=bid,
                sym=sym,
                amt=-(qty * price),
                reason=f"Buy {qty} {sym} @ ${price}",
                now=now,
            )

        # --- Portfolio Marks ---
        for mdate, meq, mcash, mexposure in [
            ("2026-06-25", 571000, 500000, 71000),
            ("2026-06-26", 577500, 500000, 77500),
            ("2026-06-27", 579000, 500000, 79000),
            ("2026-06-28", 581200, 500000, 81200),
            ("2026-06-29", 583550, 500000, 83550),
        ]:
            _exec(
                "INSERT INTO trade.portfolio_mark (mark_id, portfolio_book_id, effective_date, "
                "cash, equity, gross_exposure, regime, mark_as_of) "
                "VALUES (:mid, :bid, :edate, :cash, :eq, :gexp, 'RISK_ON', :now)",
                mid=str(uuid4()),
                bid=bid,
                edate=mdate,
                cash=mcash,
                eq=meq,
                gexp=mexposure,
                now=now,
            )

        # --- Journal Events ---
        for etype, emsg, ets in [
            ("run.started", f"Decision run {rid_1[:8]} started", _days_ago(0)),
            (
                "run.completed",
                f"Decision run {rid_1[:8]} completed — 12 candidates evaluated",
                _now(),
            ),
            ("order.created", "Buy order for 50 MSFT @ $395 placed", _days_ago(0)),
            ("order.filled", "Buy order MSFT filled — 50 shares @ $395", _days_ago(0)),
            ("system.halt_cleared", "Manual halt cleared — all systems nominal", _days_ago(1)),
        ]:
            _exec(
                "INSERT INTO audit.audit_event (event_id, decision_run_id, event_type, "
                "payload_json, created_at) "
                "VALUES (:eid, :rid, :type, :payload, :ts)",
                eid=str(uuid4()),
                rid=rid_1 if etype.startswith("run") else None,
                type=etype,
                payload='{"message":"' + emsg + '"}',
                ts=ets,
            )

        # --- Risk Events ---
        for severity, etype, msg in [
            ("info", "limit.breach_resolved", "VaR within policy limits again"),
            ("warn", "volatility.spike", "Intraday vol spike detected — monitoring"),
        ]:
            _exec(
                "INSERT INTO audit.risk_event (risk_event_id, decision_run_id, event_type, "
                "severity, details_json, created_at) "
                "VALUES (:eid, :rid, :etype, :sev, :details, :now)",
                eid=str(uuid4()),
                rid=rid_1,
                etype=etype,
                sev=severity,
                details='{"message":"' + msg + '"}',
                now=now,
            )

        # --- Halt Transition ---
        _exec(
            "INSERT INTO audit.halt_transition (halt_id, portfolio_book_id, reason, details, "
            "halted_at, resumed_at) "
            "VALUES (:hid, :bid, 'manual', 'Scheduled maintenance', :halted, :resumed)",
            hid=str(uuid4()),
            bid=bid,
            halted=_days_ago(2),
            resumed=_days_ago(1),
        )

        # --- Ops Command ---
        _exec(
            "INSERT INTO ops.command (command_id, type, idempotency_key, status, actor_id, "
            "actor_display_name, book_id, reason, payload_json, requested_at) "
            "VALUES (:cid, 'decision_run.create', :ik, 'queued', 'system', 'System', "
            ":bid, 'Scheduled daily cycle', '{}', :now)",
            cid=str(uuid4()),
            ik=f"dev-seed-cmd-{uuid4().hex[:8]}",
            bid=bid,
            now=now,
        )

        _exec(
            "INSERT INTO ops.app_config (key, value) VALUES ('mock_mode', 'true') "
            "ON CONFLICT (key) DO UPDATE SET value = 'true'",
        )

        session.commit()

    # -- Run decision cycle to compute scorecards, risk, and advice from fixture data --
    try:
        from alpha_quant.application.config import load_config
        from alpha_quant.application.daily_cycle import DailyCycleService
        from alpha_quant.application.factory import (
            create_alpha_lake_reader,
            create_unit_of_work,
        )

        uow = create_unit_of_work(url)
        with uow:
            config = load_config()
            fixture_lake = config.lake.model_copy(update={"mode": "fixture"})
            alpha_lake = create_alpha_lake_reader(config.model_copy(update={"lake": fixture_lake}))
            svc = DailyCycleService(alpha_lake, uow.store)
            cycle_result = svc.run(
                book_id=UUID(book_id),
                run_key=f"dev-seed-cycle-{uuid4().hex[:8]}",
            )
            alpha_lake.close()
            scorecard_count = cycle_result.scorecard_count
    except Exception as exc:
        print(f"  [warn] Decision cycle failed (fixtures may be incomplete): {exc}")
        scorecard_count = 0

    pos_count = (
        session_factory()
        .execute(_txt("SELECT COUNT(*) AS cnt FROM projection.position_current"))
        .one()
        ._mapping["cnt"]
    )

    return pos_count, scorecard_count


def _clear_data(engine, _txt):
    with engine.begin() as conn:
        existing = {
            r[0]
            for r in conn.execute(
                _txt(
                    "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
                )
            ).fetchall()
        }
        for table in TABLE_ORDER_REVERSE:
            if table in existing:
                conn.execute(_txt(f"DELETE FROM {table}"))
        conn.execute(_txt("DELETE FROM ops.app_config WHERE key = 'mock_mode'"))


def _create_mock_book(engine, _txt) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            _txt("SELECT book_id FROM core.portfolio_book WHERE book_id = :bid"),
            {"bid": MOCK_BOOK_ID},
        ).fetchone()
        if row:
            return MOCK_BOOK_ID
        conn.execute(
            _txt(
                "INSERT INTO core.portfolio_book (book_id, name, kind, created_at) "
                "VALUES (:bid, 'dev-seed', 'paper', :now)"
            ),
            {"bid": MOCK_BOOK_ID, "now": _now()},
        )
        conn.commit()
        return MOCK_BOOK_ID
