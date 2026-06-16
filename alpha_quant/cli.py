import argparse
import contextlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import structlog

from alpha_quant import __version__
from alpha_quant.app.bootstrap import run_bootstrap
from alpha_quant.app.config import ConfigError, load_config, redact_config
from alpha_quant.app.replay import run_replay, write_golden


def _configure_logging() -> None:
    is_dev = os.environ.get("ALPHA_QUANT_DEV", "").strip() in ("1", "true", "yes")

    shared_processors: list[structlog.typing.Processor] = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.dev.set_exc_info,
    ]

    if is_dev:
        processors: list[structlog.typing.Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def cmd_run(args: argparse.Namespace) -> None:
    import hashlib
    from datetime import date
    from pathlib import Path

    from alpha_quant.app.factory import (
        create_clock,
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sentiment_feed,
    )
    from alpha_quant.app.halt import is_halted
    from alpha_quant.app.pipeline import PipelineConfig, persist_run_result
    from alpha_quant.app.pipeline import run as run_pipeline
    from alpha_quant.app.store import CanonicalStore
    from alpha_quant.app.vault import Vault
    from alpha_quant.domain.fills import FillConfig
    from alpha_quant.domain.risk import RiskConfig as DomainRiskConfig
    from alpha_quant.domain.sizing import SizingConfig

    config = load_config(args.config)
    config.data.mode = args.mode

    if is_halted():
        print("[alpha-quant] run: pipeline halted — use `alpha-quant halt --resume` to clear")
        return

    vault = None
    if config.data.mode == "live":
        vault = Vault(base_path=Path("vault"))

    clock = create_clock(config)
    market_data = create_market_data(config, vault)
    fundamentals = create_fundamentals(config, vault)
    insider = create_insider_feed(config, vault)
    sentiment = create_sentiment_feed(config, vault)

    print(
        f"[alpha-quant] run: mode={config.data.mode},"
        f" {type(market_data).__name__},"
        f" {type(fundamentals).__name__},"
        f" {type(insider).__name__},"
        f" {type(sentiment).__name__},"
        f" {type(clock).__name__}"
    )
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))

    store = CanonicalStore(base_path=Path("data"))
    cfg_redacted = redact_config(config)
    config_hash = hashlib.sha256(json.dumps(cfg_redacted, sort_keys=True).encode()).hexdigest()[:16]
    run_id = store.register_run("cli", config_hash, config.data.fixture_version)

    universe = config.bootstrap.symbols + config.bootstrap.include_benchmarks
    pipeline_cfg = PipelineConfig(run_id=run_id)

    fill_config = FillConfig(slippage_bps=float(config.paper.slippage_bps))
    risk_config = DomainRiskConfig(
        stop_atr_mult=config.risk.stop_atr_mult,
        trail_after_r=config.risk.trail_after_r,
        partial_take_at_r=config.risk.partial_take_at_r,
        time_stop_days=config.risk.time_stop_days,
        dd_ladder=config.risk.dd_ladder,
        daily_loss_halt_pct=config.risk.daily_loss_halt_pct,
    )
    sizing_config = SizingConfig(
        risk_per_trade_pct=config.portfolio.risk_per_trade_pct,
        max_position_pct=config.portfolio.max_position_pct,
        max_gross_exposure=config.portfolio.max_gross_exposure,
    )

    prev = store.load_latest_portfolio_snapshot()
    prev_equity = prev.equity if prev else None
    prev_regime = prev.regime if prev else "CAUTION"

    run_date = date.today()

    result = run_pipeline(
        run_date=run_date,
        store=store,
        universe=universe,
        config=pipeline_cfg,
        fill_config=fill_config,
        risk_config=risk_config,
        sizing_config=sizing_config,
        market_data=market_data,
        prev_equity=prev_equity,
        prev_regime=prev_regime,
    )

    status = "completed"
    if result.halted:
        status = "halted"
    elif result.violations:
        status = "violations"

    persist_run_result(store, result)
    store.complete_run(run_id, status=status)

    print(
        f"[alpha-quant] run: {status},"
        f" decisions={len(result.decisions)},"
        f" fills={len(result.fills)},"
        f" events={len(result.events)},"
        f" violations={len(result.violations)}"
    )


def _check_connection(source: str, ok: bool) -> None:
    status = "OK" if ok else "FAIL"
    print(f"  {source}: {status}")


def cmd_replay(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    fixture = args.fixture_path
    from_date = args.from_date
    to_date = args.to_date
    output = run_replay(config, from_date, to_date, fixture)
    if args.output:
        path = write_golden(output, args.output)
        digest = __import__("hashlib").sha256(path.read_bytes()).hexdigest()[:16]
        print(f"[alpha-quant] replay: golden output written to {path} (sha256={digest})")
    else:
        print(f"[alpha-quant] replay (from={from_date} to={to_date}, fixture={fixture})")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_backtest(args: argparse.Namespace) -> None:
    from datetime import date
    from pathlib import Path

    from alpha_quant.app.backtest import BacktestConfig, run_backtest
    from alpha_quant.app.store import CanonicalStore
    from alpha_quant.domain.fills import FillConfig
    from alpha_quant.domain.risk import RiskConfig as DomainRiskConfig
    from alpha_quant.domain.sizing import SizingConfig

    config = load_config(args.config)
    store = CanonicalStore(base_path=Path("data"))
    from_date = date.fromisoformat(args.from_date)
    to_date = date.fromisoformat(args.to_date)
    fill_config = FillConfig(slippage_bps=float(config.paper.slippage_bps))
    risk_config = DomainRiskConfig(
        stop_atr_mult=config.risk.stop_atr_mult,
        trail_after_r=config.risk.trail_after_r,
        partial_take_at_r=config.risk.partial_take_at_r,
        time_stop_days=config.risk.time_stop_days,
        dd_ladder=config.risk.dd_ladder,
        daily_loss_halt_pct=config.risk.daily_loss_halt_pct,
    )
    sizing_config = SizingConfig(
        risk_per_trade_pct=config.portfolio.risk_per_trade_pct,
        max_position_pct=config.portfolio.max_position_pct,
        max_gross_exposure=config.portfolio.max_gross_exposure,
    )
    bt_config = BacktestConfig(
        start_date=from_date,
        end_date=to_date,
        initial_equity=config.paper.starting_equity,
        symbols=config.bootstrap.symbols + config.bootstrap.include_benchmarks,
    )
    result = run_backtest(
        config=bt_config,
        store=store,
        fill_config=fill_config,
        risk_config=risk_config,
        sizing_config=sizing_config,
    )
    print(
        f"[alpha-quant] backtest: {from_date} → {to_date},"
        f" {result.metrics.total_return_pct:.1f}% return,"
        f" {result.metrics.sharpe:.2f} sharpe,"
        f" {result.metrics.max_drawdown_pct:.1f}% max dd,"
        f" {result.metrics.num_trades} trades"
    )
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_bootstrap(args: argparse.Namespace) -> None:
    import time
    from pathlib import Path

    config = load_config(args.config)
    t0 = time.perf_counter()
    result = run_bootstrap(
        config=config,
        vault_base=Path(args.vault or "vault"),
        fixture_base=Path("."),
        fixture_only=args.fixture_only,
    )
    elapsed = time.perf_counter() - t0
    print(
        f"[alpha-quant] bootstrap: {result['symbols_processed']} symbols, "
        f"{result['total_bars']} bars, "
        f"bundle at {result['bundle_path']} "
        f"({elapsed:.1f}s)"
    )
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_ingest(args: argparse.Namespace) -> None:
    """Fetch and normalize live data into the canonical store."""
    from datetime import date, timedelta
    from pathlib import Path

    from alpha_quant.app.factory import (
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sentiment_feed,
    )
    from alpha_quant.app.store import CanonicalStore
    from alpha_quant.app.vault import Vault

    config = load_config(args.config)
    config.data.mode = "live"

    vault = Vault(base_path=Path("vault"))
    market_data = create_market_data(config, vault)
    fundamentals = create_fundamentals(config, vault)
    insider = create_insider_feed(config, vault)
    sentiment = create_sentiment_feed(config, vault)

    store = CanonicalStore(base_path=Path("data"))
    universe = config.bootstrap.symbols + config.bootstrap.include_benchmarks

    today = date.today()
    lookback = today - timedelta(days=args.days or 400)
    results: dict[str, list[str]] = {}

    for symbol in universe:
        sym_results: list[str] = []

        # Market data
        try:
            bars = market_data.daily_bars(symbol, lookback, today)
            if bars:
                store.save_bars(symbol, bars)
                sym_results.append(f"bars={len(bars)}")
        except Exception as e:
            sym_results.append(f"bars=FAIL({e})")

        # Fundamentals
        try:
            snap = fundamentals.snapshot(symbol)
            if snap is not None:
                store.save_fundamentals(symbol, [snap])
                sym_results.append("fundamentals=OK")
        except Exception as e:
            sym_results.append(f"fundamentals=FAIL({e})")

        # Insider transactions
        try:
            txns = insider.cluster_transactions(symbol)
            if txns:
                store.save_insider_transactions(symbol, txns)
                sym_results.append(f"insider={len(txns)}")
        except Exception as e:
            sym_results.append(f"insider=FAIL({e})")

        # Sentiment
        try:
            mentions = sentiment.mention_counts(symbol)
            if mentions:
                store.save_mentions(symbol, mentions)
                sym_results.append(f"mentions={len(mentions)}")
        except Exception as e:
            sym_results.append(f"mentions=FAIL({e})")

        results[symbol] = sym_results
        print(f"  {symbol}: {', '.join(sym_results)}")

    total_bars = 0
    for rr in results.values():
        for r in rr:
            if r.startswith("bars="):
                value = r.split("=", 1)[1]
                with contextlib.suppress(ValueError):
                    total_bars += int(value)
    ok = sum(1 for rr in results.values() for r in rr if "FAIL" not in r)
    fail = sum(1 for rr in results.values() for r in rr if "FAIL" in r)
    print(
        f"[alpha-quant] ingest: {len(universe)} symbols,"
        f" {total_bars} bars total,"
        f" {ok} ok, {fail} failed"
    )


def cmd_journal(args: argparse.Namespace) -> None:
    from pathlib import Path

    from alpha_quant.app.store import CanonicalStore

    config = load_config(args.config)
    store = CanonicalStore(base_path=Path("data"))
    runs = store.list_runs()
    if not runs:
        print("[alpha-quant] journal: no runs found")
    else:
        for r in runs[:10]:
            print(
                f"  {str(r.get('start_ts', ''))[:10]}"
                f"  {r.get('run_id', '')[:8]}"
                f"  {r.get('status', '')}"
            )
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_ask(args: argparse.Namespace) -> None:
    from pathlib import Path

    from alpha_quant.app.store import CanonicalStore
    from alpha_quant.domain.ask import ask, is_concept_query

    query = " ".join(args.query)
    store = CanonicalStore(base_path=Path("data"))

    concept_card: str | None = None
    if is_concept_query(query):
        concepts_dir = Path(__file__).resolve().parent / "concepts"
        concept_card = _load_concept_card(query, concepts_dir)

    result = ask(query, store, concept_card=concept_card, ref_date=date.today())
    print(result)


def _load_concept_card(query: str, concepts_dir: Path) -> str | None:
    import json

    manifest_path = concepts_dir / "concepts.json"
    if not manifest_path.exists():
        return None

    with manifest_path.open() as f:
        cards = json.load(f)

    for word in query.lower().split():
        for card in cards:
            if word in card["id"] or word in card["title"].lower():
                card_path = concepts_dir / f"{card['id']}.md"
                if card_path.exists():
                    return card_path.read_text()
    return None


def cmd_report(args: argparse.Namespace) -> None:
    from pathlib import Path

    from alpha_quant.app.store import CanonicalStore

    config = load_config(args.config)
    store = CanonicalStore(base_path=Path("data"))

    row = store._state_conn.execute(
        "SELECT report_date, content FROM reports"
        " WHERE report_type = ? ORDER BY report_date DESC LIMIT 1",
        [args.type],
    ).fetchone()

    if row is not None:
        report_date, content = row
        print(f"[alpha-quant] report ({args.type}) — {report_date}:")
        print()
        print(content)
    else:
        snap = store.load_latest_portfolio_snapshot()
        if snap is not None:
            print(f"[alpha-quant] report ({args.type}): no stored report found")
            print(
                f"  Latest snapshot: equity={snap.equity:.2f},"
                f" cash={snap.cash:.2f}, date={snap.date}"
            )
        else:
            print("[alpha-quant] report: no portfolio data found")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_status(args: argparse.Namespace) -> None:
    from pathlib import Path

    from alpha_quant.adapters.real.base_connector import BaseConnector
    from alpha_quant.app.factory import (
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sec_connector,
        create_sentiment_feed,
    )
    from alpha_quant.app.halt import is_halted, read_halt
    from alpha_quant.app.store import CanonicalStore
    from alpha_quant.app.vault import Vault

    config = load_config(args.config)

    if args.show_alerts:
        from alpha_quant.app.alerts import get_recent_alerts

        recent = get_recent_alerts()
        if not recent:
            print("[alpha-quant] alerts: none")
        else:
            print("[alpha-quant] alerts:")
            for a in recent[-10:]:
                print(f"  [{a['level']}] {a['title']}: {a['message']} ({a['timestamp'][:19]})")
        return

    if args.check_connections:
        vault = Vault(base_path=Path("vault")) if config.data.mode == "live" else None
        connectors: list[tuple[str, object]] = [
            ("market_data", create_market_data(config, vault)),
            ("fundamentals", create_fundamentals(config, vault)),
            ("insider_feed", create_insider_feed(config, vault)),
            ("sentiment_feed", create_sentiment_feed(config, vault)),
            ("sec", create_sec_connector(config, vault)),
        ]
        print("[alpha-quant] connections:")
        for name, conn in connectors:
            ok = conn.check_connection() if isinstance(conn, BaseConnector) else True
            _check_connection(name, ok)
        return

    store = CanonicalStore(base_path=Path("data"))

    halted = is_halted()
    halt_info = read_halt()
    last_runs = store.list_runs()
    portfolio = store.load_latest_portfolio_snapshot()
    positions = store.load_positions()

    status: dict[str, object] = {
        "halted": halted,
        "halt_reason": halt_info.get("reason") if halt_info else None,
        "halt_timestamp": halt_info.get("timestamp") if halt_info else None,
        "last_run": last_runs[0] if last_runs else None,
        "portfolio": {
            "equity": portfolio.equity if portfolio else None,
            "cash": portfolio.cash if portfolio else None,
            "date": str(portfolio.date) if portfolio else None,
            "positions": len([p for p in positions if p.quantity > 0]),
        },
    }

    if args.json:
        print(json.dumps(status, indent=2, default=str))
    elif args.show_config:
        print(json.dumps(redact_config(config), indent=2, default=str))
    else:
        print("[alpha-quant] status:")
        print(f"  halted: {halted}")
        if halt_info:
            print(f"  halt reason: {halt_info.get('reason', 'unknown')}")
            print(f"  halt at: {halt_info.get('timestamp', '')}")
        if last_runs:
            r = last_runs[0]
            print(f"  last run: {r['run_id']} ({r['status']}) at {r['start_ts']}")
        if portfolio:
            print(f"  equity: {portfolio.equity:.2f}")
            print(f"  cash: {portfolio.cash:.2f}")
        active = [p for p in positions if p.quantity > 0]
        print(f"  positions: {len(active)}")


def cmd_halt(args: argparse.Namespace) -> None:
    from alpha_quant.app.halt import clear_halt, is_halted, read_halt, write_halt

    if args.resume:
        if not is_halted():
            print("[alpha-quant] resume: not halted")
            return
        info = read_halt() or {}
        if not args.yes:
            msg = info.get("reason", "unknown")
            ts = info.get("timestamp", "")
            answer = input(f"Clear halt (reason: {msg}, at: {ts})? [y/N] ")
            if answer.strip().lower() != "y":
                print("[alpha-quant] resume: cancelled")
                return
        clear_halt()
        print("[alpha-quant] resume: halted cleared")
        return

    reason = " ".join(args.reason) if args.reason else "manual halt"
    write_halt(reason=reason)
    print(f"[alpha-quant] halt: {reason}")
    if is_halted():
        print("[alpha-quant] halt: use `alpha-quant halt --resume` to clear")


def cmd_schedule(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    config.data.mode = args.mode

    from alpha_quant.app.scheduler import setup_scheduler

    scheduler = setup_scheduler(config_path=args.config, mode=args.mode)
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("[alpha-quant] scheduler: stopped")
        scheduler.shutdown(wait=False)


def cmd_backup(args: argparse.Namespace) -> None:
    from alpha_quant.app.backup import run_backup

    path = run_backup(config_path=args.config)
    print(f"[alpha-quant] backup: created {path}")

    if args.prune:
        from alpha_quant.app.backup import prune_backups

        removed = prune_backups()
        for r in removed:
            print(f"[alpha-quant] backup: pruned {r.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alpha-quant",
        description="Deterministic, daily-cadence, long-only equity trading system",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.toml (default: $PWD/config.toml or ~/.alpha-quant/config.toml)",
    )
    parser.add_argument(
        "--verbose-config",
        action="store_true",
        help="Print resolved config on every command",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Execute daily pipeline")
    p_run.add_argument(
        "--mode",
        choices=["live", "fixture"],
        default="live",
        help="Run mode (default: live)",
    )
    p_run.set_defaults(func=cmd_run)

    p_replay = sub.add_parser("replay", help="Replay historical period")
    p_replay.add_argument("--from-date", type=str, required=True)
    p_replay.add_argument("--to-date", type=str, required=True)
    p_replay.add_argument(
        "--fixture",
        type=str,
        dest="fixture_path",
        default=None,
        help="Fixture bundle path (default: ./fixtures/v1)",
    )
    p_replay.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write golden output to this file",
    )
    p_replay.set_defaults(func=cmd_replay)

    p_backtest = sub.add_parser("backtest", help="Run event-driven backtester")
    p_backtest.add_argument("--from-date", type=str, required=True)
    p_backtest.add_argument("--to-date", type=str, required=True)
    p_backtest.set_defaults(func=cmd_backtest)

    p_bootstrap = sub.add_parser("bootstrap", help="Fetch and freeze fixture bundle")
    p_bootstrap.add_argument(
        "--fixture-only",
        action="store_true",
        help="Skip fetch, regenerate fixture bundle from existing vault",
    )
    p_bootstrap.add_argument(
        "--vault",
        type=str,
        default=None,
        help="Vault directory path (default: ./vault)",
    )
    p_bootstrap.set_defaults(func=cmd_bootstrap)

    p_ingest = sub.add_parser("ingest", help="Fetch and normalize live data into canonical store")
    p_ingest.add_argument(
        "--days",
        type=int,
        default=400,
        help="Lookback days (default: 400)",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_journal = sub.add_parser("journal", help="Display recent journal entries")
    p_journal.add_argument(
        "--since",
        type=str,
        default="7d",
        help="Show entries since (e.g. 7d, 30d, YYYY-MM-DD)",
    )
    p_journal.set_defaults(func=cmd_journal)

    p_ask = sub.add_parser("ask", help="Query recorded decisions")
    p_ask.add_argument("query", type=str, nargs="+", help="Natural language query")
    p_ask.set_defaults(func=cmd_ask)

    p_report = sub.add_parser("report", help="Generate weekly or monthly report")
    p_report.add_argument(
        "--type",
        choices=["weekly", "monthly"],
        default="weekly",
        help="Report type (default: weekly)",
    )
    p_report.set_defaults(func=cmd_report)

    p_status = sub.add_parser("status", help="Full system status")
    p_status.add_argument(
        "--check-connections",
        action="store_true",
        dest="check_connections",
        help="Ping each data source",
    )
    p_status.add_argument(
        "--alerts",
        action="store_true",
        dest="show_alerts",
        help="Show recent alerts",
    )
    p_status.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    p_status.add_argument(
        "--show-config",
        action="store_true",
        dest="show_config",
        help="Print resolved config (secrets redacted)",
    )
    p_status.set_defaults(func=cmd_status)

    p_halt = sub.add_parser("halt", help="Halt or resume pipeline")
    p_halt.add_argument(
        "reason",
        type=str,
        nargs="*",
        default=None,
        help="Reason for halting (optional)",
    )
    p_halt.add_argument(
        "--resume",
        action="store_true",
        help="Resume after halt",
    )
    p_halt.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation for resume",
    )
    p_halt.set_defaults(func=cmd_halt)

    p_schedule = sub.add_parser("schedule", help="Start daily scheduler daemon")
    p_schedule.add_argument(
        "--mode",
        choices=["live", "fixture"],
        default="live",
        help="Run mode (default: live)",
    )
    p_schedule.set_defaults(func=cmd_schedule)

    p_backup = sub.add_parser("backup", help="Create backup archive")
    p_backup.add_argument("--prune", action="store_true", help="Remove old backups per policy")
    p_backup.set_defaults(func=cmd_backup)

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
