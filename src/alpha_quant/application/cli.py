import hashlib
import json
import os
import re
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from importlib.metadata import version as _version
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm as RichConfirm
from rich.table import Table

from alpha_quant.application.config import AppConfig, ConfigError, load_config, redact_config

__version__ = _version("alpha-quant")

log = structlog.get_logger()
console = Console()

app = typer.Typer(
    name="alpha-quant",
    help="Deterministic, daily-cadence, long-only equity trading system",
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


RELATIVE_DATE_RE = re.compile(r"^(\d+)([dmy])\s*$")


def _configure_logging() -> None:
    is_dev = (
        os.environ.get("ALPHA_QUANT_DEV", "").strip() in ("1", "true", "yes") or sys.stderr.isatty()
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.dev.set_exc_info,
    ]

    if is_dev:
        processors = [
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


def _parse_date(value: str) -> date:
    """Parse ISO date or relative string like ``7d``, ``30d``, ``3m``, ``1y``."""
    value = value.strip()
    if m := RELATIVE_DATE_RE.match(value):
        amount = int(m.group(1))
        unit = m.group(2)
        today = date.today()
        if unit == "d":
            return today - timedelta(days=amount)
        elif unit == "m":
            return today - timedelta(days=amount * 30)
        elif unit == "y":
            return today - timedelta(days=amount * 365)
    return date.fromisoformat(value)


def _print_panel(
    title: str, items: Sequence[tuple[str, str]], *, border_style: str = "cyan"
) -> None:
    content = "\n".join(f"  {k:<12} {v}" for k, v in items)
    console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style=border_style))


def _print_error(title: str, message: str) -> None:
    log.error("cli_error", title=title, message=message)
    console.print(
        Panel(f"[red]{message}[/red]", title=f"[red]\u2717 {title}[/red]", border_style="red")
    )


def _check_connection(source: str, ok: bool, table: Table) -> None:
    status = "[green]\u25cf OK[/green]" if ok else "[red]\u25cf FAIL[/red]"
    table.add_row(source, status)


def _load_config_cached(ctx: typer.Context) -> AppConfig:
    config_path: str | None = ctx.obj.get("config_path")
    config = load_config(config_path)
    if ctx.obj.get("verbose"):
        console.print_json(data=redact_config(config))
    return config


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"alpha-quant [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: str | None = typer.Option(  # noqa: B008
        None,
        "--config",
        "-c",
        help="Path to config.toml (default: ./config.toml or ~/.alpha-quant/config.toml)",
        envvar="ALPHA_QUANT_CONFIG",
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False,
        "--verbose",
        "-v",
        help="Show resolved configuration (secrets redacted)",
    ),
    version: bool = typer.Option(  # noqa: B008
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Alpha-Quant CLI — deterministic, daily-cadence, long-only equity system."""
    _configure_logging()
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


# ── Run ────────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Run")
def run(
    ctx: typer.Context,
    mode: str = typer.Option(  # noqa: B008
        "live",
        "--mode",
        "-m",
        help="Run mode: live (needs API keys) or fixture (deterministic replay)",
    ),
) -> None:
    """Execute the daily pipeline.

    Runs the full decision engine (M1-M8), paper fills, shadow books, and
    journal narration for today's date.
    """
    from datetime import date
    from pathlib import Path

    from alpha_quant.application.factory import create_alpha_lake_reader
    from alpha_quant.application.halt import is_halted
    from alpha_quant.application.pipeline_v2 import PipelineConfig, persist_run_result, run_v2
    from alpha_quant.application.store import CanonicalStore
    from alpha_quant.domain.fills import FillConfig
    from alpha_quant.domain.risk import RiskConfig as DomainRiskConfig
    from alpha_quant.domain.sizing import SizingConfig

    config = _load_config_cached(ctx)

    if is_halted():
        _print_error("Pipeline Halted", "Use alpha-quant halt --resume to clear")
        return

    store = CanonicalStore(base_path=Path("data"))
    cfg_redacted = redact_config(config)
    config_hash = hashlib.sha256(json.dumps(cfg_redacted, sort_keys=True).encode()).hexdigest()[:16]
    run_id = store.register_run("cli", config_hash, config.data.fixture_version)
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
    )

    prev = store.load_latest_portfolio_snapshot()
    prev_equity = prev.equity if prev else None
    prev_regime = prev.regime if prev else "CAUTION"

    run_date = date.today()
    universe = config.bootstrap.symbols + config.bootstrap.include_benchmarks

    alpha_lake = create_alpha_lake_reader(config)
    _print_panel(
        "Daily Pipeline Run (Alpha-Lake)",
        [("Mode", f"[cyan]{mode}[/cyan]"), ("Adapters", type(alpha_lake).__name__)],
    )
    result = run_v2(
        run_date=run_date,
        store=store,
        universe=universe,
        alpha_lake=alpha_lake,
        config=pipeline_cfg,
        fill_config=fill_config,
        risk_config=risk_config,
        sizing_config=sizing_config,
        prev_equity=prev_equity,
        prev_regime=prev_regime,
    )

    status_text = "completed"
    if result.halted:
        status_text = "halted"
    elif result.violations:
        status_text = "violations"

    status_styles = {
        "completed": "[green]completed[/green]",
        "halted": "[red]halted[/red]",
        "violations": "[yellow]violations[/yellow]",
    }

    persist_run_result(store, result)
    store.complete_run(run_id, status=status_text)

    border = (
        "green"
        if status_text == "completed"
        else "yellow"
        if status_text == "violations"
        else "red"
    )
    _print_panel(
        "Pipeline Result",
        [
            ("Status", status_styles.get(status_text, status_text)),
            ("Run ID", run_id[:8]),
            ("Decisions", str(len(result.decisions))),
            ("Fills", str(len(result.fills))),
            ("Events", str(len(result.events))),
            ("Violations", str(len(result.violations))),
        ],
        border_style=border,
    )


# ── Bootstrap ───────────────────────────────────────────────────────────────────────────


# ── Journal ─────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Query")
def journal(
    ctx: typer.Context,
    since: str = typer.Option(  # noqa: B008
        "7d",
        "--since",
        "-s",
        help="Show entries since: 7d, 30d, or YYYY-MM-DD",
    ),
) -> None:
    """Display recent daily journal entries.

    Shows trading journal entries with LLM narration. Use --since to control
    the lookback window.
    """
    from pathlib import Path

    from alpha_quant.application.store import CanonicalStore

    _ = _load_config_cached(ctx)  # handles --verbose
    store = CanonicalStore(base_path=Path("data"))
    runs = store.list_runs()

    if not runs:
        console.print("[yellow]No journal entries found.[/yellow]")
    else:
        table = Table(title="Recent Runs", border_style="cyan")
        table.add_column("Date", style="cyan")
        table.add_column("Run ID", style="dim")
        table.add_column("Status")

        for r in runs[:10]:
            run_date = str(r.get("start_ts", ""))[:10]
            run_id = r.get("run_id", "")[:8]
            run_status = r.get("status", "")
            status_styles = {
                "completed": "[green]completed[/green]",
                "halted": "[red]halted[/red]",
                "violations": "[yellow]violations[/yellow]",
            }
            table.add_row(run_date, run_id, status_styles.get(run_status, run_status))

        console.print(table)


# ── Ask ─────────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Query")
def ask(
    ctx: typer.Context,
    query: list[str] = typer.Argument(  # noqa: B008
        ...,
        help="Natural-language query about decisions and events",  # fmt: skip
    ),
) -> None:
    """Query recorded decisions and events in natural language.

    Ask questions about why decisions were made, what the system is thinking,
    or get concept explanations.
    """
    from datetime import UTC, datetime
    from pathlib import Path

    from alpha_quant.application.store import CanonicalStore
    from alpha_quant.domain.ask import ask as ask_domain
    from alpha_quant.domain.ask import is_concept_query
    from alpha_quant.domain.events import CandidateBlocked

    query_text = " ".join(query)
    store = CanonicalStore(base_path=Path("data"))

    concept_card: str | None = None
    if is_concept_query(query_text):
        concepts_dir = Path(__file__).resolve().parent / "concepts"
        concept_card = _load_concept_card(query_text, concepts_dir)

    cutoff_dt = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
    all_events = store.load_events(since=cutoff_dt)
    blocked_events = [e for e in all_events if isinstance(e, CandidateBlocked)]

    result = ask_domain(query_text, blocked_events, concept_card=concept_card)
    console.print(result)


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


# ── Report ──────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Query")
def report(
    ctx: typer.Context,
    report_type: str = typer.Option(  # noqa: B008
        "weekly",
        "--type",
        "-t",
        help="Report type: weekly or monthly",
    ),
) -> None:
    """Generate weekly or monthly performance report.

    Reads persisted report data from the state store. Falls back to the latest
    portfolio snapshot if no stored report exists.
    """
    from pathlib import Path

    from alpha_quant.application.store import CanonicalStore

    _ = _load_config_cached(ctx)  # handles --verbose
    store = CanonicalStore(base_path=Path("data"))

    row = store._state_conn.execute(
        "SELECT report_date, content FROM reports"
        " WHERE report_type = ? ORDER BY report_date DESC LIMIT 1",
        [report_type],
    ).fetchone()

    if row is not None:
        report_date, content = row
        _print_panel(
            f"{report_type.title()} Report \u2014 {report_date}",
            [
                ("Content", content[:500] + ("..." if len(content) > 500 else "")),
            ],
        )
    else:
        snap = store.load_latest_portfolio_snapshot()
        if snap is not None:
            _print_panel(
                "No Stored Report",
                [
                    (
                        "Latest Snapshot",
                        f"equity={snap.equity:.2f}, cash={snap.cash:.2f}, date={snap.date}",
                    ),
                ],
                border_style="yellow",
            )
        else:
            _print_panel(
                "No Data",
                [
                    ("Message", "No portfolio data found"),
                ],
                border_style="yellow",
            )


# ── Status ──────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Ops")
def status(
    ctx: typer.Context,
    alerts: bool = typer.Option(  # noqa: B008
        False,
        "--alerts",
        help="Show recent system alerts",
    ),
    json_output: bool = typer.Option(  # noqa: B008
        False,
        "--json",
        help="Output status as JSON",
    ),
    show_config: bool = typer.Option(  # noqa: B008
        False,
        "--show-config",
        help="Print resolved configuration (secrets redacted)",
    ),
) -> None:
    """Display full system status.

    Shows halt state, last run, portfolio equity/cash, and active positions.
    """
    from pathlib import Path

    from alpha_quant.application.halt import is_halted, read_halt
    from alpha_quant.application.store import CanonicalStore

    config = _load_config_cached(ctx)

    if alerts:
        from alpha_quant.application.alerts import get_recent_alerts

        recent = get_recent_alerts()
        if not recent:
            console.print("[green]No alerts.[/green]")
        else:
            table = Table(title="Recent Alerts", border_style="yellow")
            table.add_column("Level", style="bold")
            table.add_column("Title")
            table.add_column("Message")
            table.add_column("Time", style="dim")
            for a in recent[-10:]:
                table.add_row(a["level"], a["title"], a["message"], a["timestamp"][:19])
            console.print(table)
        return

    store = CanonicalStore(base_path=Path("data"))

    halted = is_halted()
    halt_info = read_halt()
    last_runs = store.list_runs()
    portfolio = store.load_latest_portfolio_snapshot()
    positions = store.load_positions()

    if json_output:
        status_data: dict[str, object] = {
            "halted": halted,
            "halt_reason": halt_info.get("reason") if halt_info else None,
            "halt_timestamp": str(halt_info.get("timestamp")) if halt_info else None,
            "last_run": {
                "run_id": last_runs[0].get("run_id") if last_runs else None,
                "status": last_runs[0].get("status") if last_runs else None,
                "start_ts": str(last_runs[0].get("start_ts")) if last_runs else None,
            }
            if last_runs
            else None,
            "portfolio": {
                "equity": portfolio.equity if portfolio else None,
                "cash": portfolio.cash if portfolio else None,
                "date": str(portfolio.date) if portfolio else None,
                "positions": len([p for p in positions if p.quantity > 0]),
            },
        }
        console.print_json(data=status_data)
        return

    if show_config:
        console.print_json(data=redact_config(config))
        return

    halt_symbol = "[green]\u25cf No[/green]" if not halted else "[red]\u25cf Yes[/red]"
    items: list[tuple[str, str]] = [("Halted", halt_symbol)]

    if halt_info:
        items.append(("Halt Reason", halt_info.get("reason", "unknown")))
        items.append(("Halt At", str(halt_info.get("timestamp", ""))))

    if last_runs:
        r = last_runs[0]
        items.append(
            ("Last Run", f"{r['run_id'][:8]} ({r['status']}) at {str(r['start_ts'])[:19]}")
        )

    if portfolio:
        items.append(("Equity", f"[green]${portfolio.equity:,.2f}[/green]"))
        items.append(("Cash", f"${portfolio.cash:,.2f}"))
    else:
        items.append(("Equity", "[yellow]No data[/yellow]"))

    active = [p for p in positions if p.quantity > 0]
    items.append(("Positions", str(len(active))))

    if active:
        pos_lines = []
        for p in active:
            price = p.current_price or 0
            pos_lines.append(f"  [cyan]{p.symbol}[/cyan]  {p.quantity} shares  ${price:.2f}")
        items.append(("Holdings", "\n" + "\n".join(pos_lines)))

    _print_panel("System Status", items)


# ── Halt ────────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Ops")
def halt(
    reason: list[str] = typer.Argument(  # noqa: B008
        None,
        help="Reason for halting (optional, multiple words supported)",
    ),
    resume: bool = typer.Option(  # noqa: B008
        False,
        "--resume",
        help="Resume pipeline after a halt",
    ),
    yes: bool = typer.Option(  # noqa: B008
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Halt or resume the pipeline.

    Puts a halt lock in place that blocks pipeline execution. Use --resume
    to clear it.
    """
    from alpha_quant.application.halt import clear_halt, is_halted, read_halt, write_halt

    if resume:
        if not is_halted():
            _print_error("Not Halted", "Pipeline is not currently halted")
            return
        info = read_halt() or {}
        msg = info.get("reason", "unknown")
        ts = info.get("timestamp", "")
        if not yes:
            prompt = (
                f"[yellow]Clear halt?[/yellow]\n  Reason: [bold]{msg}[/bold]\n  At: [dim]{ts}[/dim]"
            )
            confirm = RichConfirm.ask(prompt, default=False)
            if not confirm:
                console.print("[yellow]Resume cancelled.[/yellow]")
                return
        clear_halt()
        _print_panel(
            "Pipeline Resumed",
            [
                ("Status", "[green]Halt cleared[/green]"),
            ],
            border_style="green",
        )
        return

    reason_text = " ".join(reason) if reason else "manual halt"
    write_halt(reason=reason_text)
    _print_panel(
        "Pipeline Halted",
        [
            ("Reason", f"[yellow]{reason_text}[/yellow]"),
            ("Resume", "Use alpha-quant halt --resume to clear"),
        ],
        border_style="red",
    )


# ── Schedule ─────────────────────────────────────────────────────────────────────────────


# ── Backup ──────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Ops")
def backup(
    prune: bool = typer.Option(  # noqa: B008
        False,
        "--prune",
        help="Remove old backups per retention policy",
    ),
) -> None:
    """Create a backup archive of the state store.

    Compresses the DuckDB state database into a single archive.
    Use --prune to clean up old backups after creating a new one.
    """
    from alpha_quant.application.backup import prune_backups, run_backup

    path = run_backup(config_path=None)
    _print_panel(
        "Backup Created",
        [
            ("Path", str(path)),
        ],
        border_style="green",
    )

    if prune:
        removed = prune_backups()
        if removed:
            table = Table(title="Pruned Backups", border_style="yellow")
            table.add_column("File", style="dim")
            for r in removed:
                table.add_row(r.name)
            console.print(table)
        else:
            console.print("[green]No old backups to prune.[/green]")


# ── Database ────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Database")
def db_health(
    database_url: str = typer.Option(  # noqa: B008
        "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant",
        "--database-url",
        "-d",
        envvar="DATABASE_URL",
        help="PostgreSQL connection string",
    ),
) -> None:
    """Check PostgreSQL database connectivity."""
    from alpha_quant.adapters.postgres import create_engine
    from alpha_quant.adapters.postgres.health import health_check

    engine = create_engine(database_url)
    result = health_check(engine)
    if result["status"] == "healthy":
        _print_panel(
            "Database Health", [("Status", "[green]healthy[/green]"), ("DB", str(result["db"]))]
        )
    else:
        err = result.get("error") or "unknown error"
        _print_error("Unhealthy", str(err))


@app.command(rich_help_panel="Database")
def db_migrate(
    database_url: str = typer.Option(  # noqa: B008
        "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant",
        "--database-url",
        "-d",
        envvar="DATABASE_URL",
        help="PostgreSQL connection string",
    ),
) -> None:
    """Run pending Alembic migrations."""
    from alpha_quant.application.factory import run_migrations

    run_migrations(database_url)
    _print_panel("Migration", [("Status", "[green]up to date[/green]")])


@app.command(rich_help_panel="Database")
def db_seed(
    database_url: str = typer.Option(  # noqa: B008
        "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant",
        "--database-url",
        "-d",
        envvar="DATABASE_URL",
        help="PostgreSQL connection string",
    ),
) -> None:
    """Seed default strategy and portfolio book records."""
    from alpha_quant.application.factory import seed_default_data

    seed_default_data(database_url)
    _print_panel("Seed", [("Status", "[green]default records created[/green]")])


@app.command(rich_help_panel="Database")
def db_import(
    duckdb_path: str = typer.Option(  # noqa: B008
        "data/state.db",
        "--duckdb-path",
        help="Path to legacy DuckDB state database",
    ),
    database_url: str = typer.Option(  # noqa: B008
        "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant",
        "--database-url",
        "-d",
        envvar="DATABASE_URL",
        help="PostgreSQL connection string",
    ),
) -> None:
    """Import legacy DuckDB state into PostgreSQL operational store."""
    from alpha_quant.application.import_legacy_duckdb import run_import

    count = run_import(duckdb_path=duckdb_path, postgres_url=database_url)
    _print_panel("Import", [("Rows imported", f"[green]{count}[/green]")])


@app.command(rich_help_panel="Dashboard")
def dashboard(
    host: str = typer.Option("localhost", "--host", help="Bind address"),
    port: int = typer.Option(8501, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code change"),
) -> None:
    """Start the FastAPI dashboard server."""
    import uvicorn

    from alpha_quant.application.dashboard import app as dashboard_app

    uvicorn.run(dashboard_app, host=host, port=port, reload=reload)


# ── Entry point ─────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    try:
        app(args=argv, standalone_mode=False)
        return 0
    except SystemExit as e:
        code = e.code
        if isinstance(code, int):
            return code
        return 0
    except ConfigError as e:
        _print_error("Configuration Error", str(e))
        return 1
    except typer._click.exceptions.NoArgsIsHelpError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
