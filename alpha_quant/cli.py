import argparse
import json
import os
import sys

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
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def cmd_run(args: argparse.Namespace) -> None:
    from pathlib import Path

    from alpha_quant.app.factory import (
        create_clock,
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sentiment_feed,
    )
    from alpha_quant.app.halt import is_halted
    from alpha_quant.app.vault import Vault

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
    config = load_config(args.config)
    print("[alpha-quant] backtest: not yet implemented (planned for P2.13 Backtester)")
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


def cmd_journal(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print("[alpha-quant] journal: not yet implemented (planned for P4.5 Daily journal generator)")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_ask(args: argparse.Namespace) -> None:
    from pathlib import Path

    from alpha_quant.app.store import CanonicalStore
    from alpha_quant.domain.ask import ask

    query = " ".join(args.query)
    store = CanonicalStore(base_path=Path("data"))
    concepts_dir = Path(__file__).resolve().parent / "concepts"
    result = ask(query, store, concepts_dir=concepts_dir)
    print(result)


def cmd_report(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print("[alpha-quant] report: not yet implemented (planned for P4.6 Weekly & monthly reports)")
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
