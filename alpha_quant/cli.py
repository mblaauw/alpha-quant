import argparse
import sys

from alpha_quant import __version__


def cmd_run(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: run (mode={args.mode})")


def cmd_replay(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: replay (from={args.from_date} to={args.to_date})")


def cmd_backtest(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: backtest (from={args.from_date} to={args.to_date})")


def cmd_bootstrap(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: bootstrap (fixture_only={args.fixture_only})")


def cmd_journal(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: journal (since={args.since})")


def cmd_ask(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: ask (query={args.query})")


def cmd_report(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: report (type={args.type})")


def cmd_status(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: status (json={args.json})")


def cmd_halt(args: argparse.Namespace) -> None:
    print(f"[alpha-quant] stub: halt (action={args.action})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alpha-quant",
        description="Deterministic, daily-cadence, long-only equity trading system",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.toml (default: $PWD/config.toml or ~/.alpha-quant/config.toml)",
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
    p_status.set_defaults(func=cmd_status)

    p_halt = sub.add_parser("halt", help="Halt or resume pipeline")
    p_halt.add_argument(
        "--resume",
        action="store_true",
        help="Resume after halt",
    )
    p_halt.set_defaults(func=cmd_halt, action="halt")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
