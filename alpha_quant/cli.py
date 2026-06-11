import argparse
import json
import sys

from alpha_quant import __version__
from alpha_quant.app.bootstrap import run_bootstrap
from alpha_quant.app.config import ConfigError, load_config, redact_config
from alpha_quant.app.replay import run_replay, write_golden


def cmd_run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print(f"[alpha-quant] run (mode={args.mode})")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


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
    print(f"[alpha-quant] backtest (from={args.from_date} to={args.to_date})")
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
    print(f"[alpha-quant] journal (since={args.since})")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_ask(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print(f"[alpha-quant] ask (query={' '.join(args.query)})")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_report(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print(f"[alpha-quant] report (type={args.type})")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


def cmd_status(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if args.show_config:
        if args.json:
            print(json.dumps(redact_config(config), indent=2, default=str))
        else:
            for section, fields in redact_config(config).items():
                print(f"[{section}]")
                for key, value in fields.items():
                    print(f"  {key} = {value}")
                print()
    else:
        print("[alpha-quant] status: OK")


def cmd_halt(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    action = "resume" if args.resume else "halt"
    print(f"[alpha-quant] {action}")
    if args.verbose_config:
        print(json.dumps(redact_config(config), indent=2, default=str))


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
        "--resume",
        action="store_true",
        help="Resume after halt",
    )
    p_halt.set_defaults(func=cmd_halt)

    return parser


def main(argv: list[str] | None = None) -> int:
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
