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
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm as RichConfirm
from rich.table import Table

from app.config import AppConfig, ConfigError, load_config, redact_config

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

    from app.factory import (
        create_clock,
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sentiment_feed,
    )
    from app.halt import is_halted
    from app.pipeline import PipelineConfig, persist_run_result
    from app.pipeline import run as run_pipeline
    from app.store import CanonicalStore
    from app.vault import Vault
    from domain.fills import FillConfig
    from domain.risk import RiskConfig as DomainRiskConfig
    from domain.sizing import SizingConfig

    config = _load_config_cached(ctx)
    config.data.mode = mode

    if is_halted():
        _print_error("Pipeline Halted", "Use alpha-quant halt --resume to clear")
        return

    vault: Vault | None = None
    if config.data.mode == "live":
        vault = Vault(base_path=Path("vault"))

    clock = create_clock(config)
    market_data = create_market_data(config, vault)
    fundamentals = create_fundamentals(config, vault)
    insider = create_insider_feed(config, vault)
    sentiment = create_sentiment_feed(config, vault)

    adapter_names = [
        type(market_data).__name__,
        type(fundamentals).__name__,
        type(insider).__name__,
        type(sentiment).__name__,
        type(clock).__name__,
    ]
    _print_panel(
        "Daily Pipeline Run",
        [
            ("Mode", f"[cyan]{mode}[/cyan]"),
            ("Adapters", ", ".join(adapter_names)),
        ],
    )

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


# ── Replay ─────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Run")
def replay(
    ctx: typer.Context,
    from_date: str = typer.Option(  # noqa: B008
        ...,
        "--from-date",
        help="Start date: YYYY-MM-DD or relative like 7d, 3m, 1y",
    ),
    to_date: str = typer.Option(  # noqa: B008
        ...,
        "--to-date",
        help="End date: YYYY-MM-DD or relative",
    ),
    fixture: str | None = typer.Option(  # noqa: B008
        None,
        "--fixture",
        help="Fixture bundle path (default: ./fixtures/v1)",
    ),
    output: str | None = typer.Option(  # noqa: B008
        None,
        "--output",
        help="Write golden output to this file",
    ),
) -> None:
    """Full-DAG replay over fixture data.

    Runs the entire pipeline against deterministic fixture data for a
    historical period. Add --output to write a golden file that CI
    can hash-check.
    """

    from app.replay import run_replay, write_golden

    config = _load_config_cached(ctx)
    fd = _parse_date(from_date)
    td = _parse_date(to_date)

    with console.status(f"[cyan]Replaying {fd} \u2192 {td}...", spinner="dots"):
        result = run_replay(config, from_date, to_date, fixture)

    if output:
        path = write_golden(result, output)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        _print_panel(
            "Golden Replay",
            [
                ("Period", f"{fd} \u2192 {td}"),
                ("Fixture", fixture or "fixtures/v1"),
                ("Output", f"[green]{path}[/green]"),
                ("SHA256", f"[dim]{digest}[/dim]"),
            ],
            border_style="green",
        )
    else:
        _print_panel(
            "Replay Complete",
            [
                ("Period", f"{fd} \u2192 {td}"),
                ("Fixture", fixture or "fixtures/v1"),
            ],
            border_style="green",
        )


# ── Backtest ────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Run")
def backtest(
    ctx: typer.Context,
    from_date: str = typer.Option(  # noqa: B008
        ...,
        "--from-date",
        help="Start date: YYYY-MM-DD or relative like 7d, 3m, 1y",
    ),
    to_date: str = typer.Option(  # noqa: B008
        ...,
        "--to-date",
        help="End date: YYYY-MM-DD or relative",
    ),
) -> None:
    """Run the event-driven historical backtester.

    Uses the same fill model, risk management, and decision engine as the live
    pipeline. Results are comparable by design.
    """
    from pathlib import Path

    from app.backtest import BacktestConfig, run_backtest
    from app.store import CanonicalStore
    from domain.fills import FillConfig
    from domain.risk import RiskConfig as DomainRiskConfig
    from domain.sizing import SizingConfig

    config = _load_config_cached(ctx)
    store = CanonicalStore(base_path=Path("data"))
    fd = _parse_date(from_date)
    td = _parse_date(to_date)

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
        start_date=fd,
        end_date=td,
        initial_equity=config.paper.starting_equity,
        symbols=config.bootstrap.symbols + config.bootstrap.include_benchmarks,
    )

    with console.status(f"[cyan]Backtesting {fd} \u2192 {td}...", spinner="dots"):
        result = run_backtest(
            config=bt_config,
            store=store,
            fill_config=fill_config,
            risk_config=risk_config,
            sizing_config=sizing_config,
        )

    metrics = result.metrics
    return_pct = metrics.total_return_pct
    sharpe = metrics.sharpe
    dd = metrics.max_drawdown_pct

    return_color = "green" if return_pct > 0 else "red"
    sharpe_color = "green" if sharpe > 1.0 else "yellow" if sharpe > 0 else "red"
    dd_color = "green" if dd > -5 else "yellow" if dd > -15 else "red"

    _print_panel(
        "Backtest Results",
        [
            ("Period", f"{fd} \u2192 {td}"),
            ("Return", f"[{return_color}]{return_pct:+.1f}%[/{return_color}]"),
            ("Sharpe", f"[{sharpe_color}]{sharpe:.2f}[/{sharpe_color}]"),
            ("Max DD", f"[{dd_color}]{dd:.1f}%[/{dd_color}]"),
            ("Trades", str(metrics.num_trades)),
        ],
        border_style="green" if return_pct > 0 else "yellow",
    )


# ── Bootstrap ───────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Data")
def bootstrap(
    ctx: typer.Context,
    fixture_only: bool = typer.Option(  # noqa: B008
        False,
        "--fixture-only",
        help="Skip API fetch, regenerate fixture bundle from existing vault",
    ),
    vault: str | None = typer.Option(  # noqa: B008
        None,
        "--vault",
        help="Vault directory path (default: ./vault)",
    ),
) -> None:
    """Fetch and freeze a fixture bundle for development.

    Downloads historical data for all configured symbols, then freezes a
    deterministic fixture bundle used by replay and run --mode fixture.
    """
    import time
    from pathlib import Path

    from app.bootstrap import run_bootstrap

    config = _load_config_cached(ctx)
    t0 = time.perf_counter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        if fixture_only:
            progress.add_task("[cyan]Freezing fixture bundle from vault...", total=1)
        else:
            progress.add_task("[cyan]Fetching data and freezing fixture bundle...", total=1)

        result = run_bootstrap(
            config=config,
            vault_base=Path(vault or "vault"),
            fixture_base=Path("."),
            fixture_only=fixture_only,
        )

    elapsed = time.perf_counter() - t0

    _print_panel(
        "Bootstrap Complete",
        [
            ("Symbols", str(result["symbols_processed"])),
            ("Bars", f"{result['total_bars']:,}"),
            ("Bundle", result["bundle_path"]),
            ("Time", f"{elapsed:.1f}s"),
        ],
        border_style="green",
    )


# ── Ingest ──────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Data")
def ingest(
    ctx: typer.Context,
    days: int = typer.Option(  # noqa: B008
        400,
        "--days",
        "-d",
        help="Lookback days for historical data",
    ),
) -> None:
    """Fetch live data from APIs into the canonical store.

    Downloads daily bars, fundamentals snapshots, insider transactions, and
    social sentiment for all universe symbols. Run this before alpha-quant run.
    """
    from datetime import date, timedelta
    from pathlib import Path

    from app.factory import (
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sentiment_feed,
    )
    from app.store import CanonicalStore
    from app.vault import Vault

    config = _load_config_cached(ctx)
    config.data.mode = "live"

    vault = Vault(base_path=Path("vault"))
    market_data = create_market_data(config, vault)
    fundamentals = create_fundamentals(config, vault)
    insider = create_insider_feed(config, vault)
    sentiment = create_sentiment_feed(config, vault)

    store = CanonicalStore(base_path=Path("data"))
    universe = config.bootstrap.symbols + config.bootstrap.include_benchmarks

    today = date.today()
    lookback = today - timedelta(days=days)
    results: dict[str, list[str]] = {}

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )

    totals = {
        "bars": 0,
        "fundamentals": 0,
        "insider": 0,
        "mentions": 0,
        "bars_fail": 0,
        "fundamentals_fail": 0,
        "insider_fail": 0,
        "mentions_fail": 0,
    }

    with progress:
        ingest_task = progress.add_task(
            f"[cyan]Ingesting {len(universe)} symbols...",
            total=len(universe),
        )

        for symbol in universe:
            sym_results: list[str] = []

            try:
                bars = market_data.daily_bars(symbol, lookback, today)
                if bars:
                    store.save_bars(symbol, bars)
                    totals["bars"] += len(bars)
                    sym_results.append(f"bars={len(bars)}")
                else:
                    totals["bars_fail"] += 1
                    sym_results.append("bars=[red]0[/red]")
            except Exception:
                totals["bars_fail"] += 1
                sym_results.append("bars=[red]FAIL[/red]")

            try:
                snap = fundamentals.snapshot(symbol)
                if snap is not None:
                    store.save_fundamentals(symbol, [snap])
                    totals["fundamentals"] += 1
                    sym_results.append("fundamentals=[green]OK[/green]")
                else:
                    totals["fundamentals_fail"] += 1
                    sym_results.append("fundamentals=[yellow]-[/yellow]")
            except Exception:
                totals["fundamentals_fail"] += 1
                sym_results.append("fundamentals=[red]FAIL[/red]")

            try:
                txns = insider.cluster_transactions(symbol)
                if txns:
                    store.save_insider_transactions(symbol, txns)
                    totals["insider"] += len(txns)
                    sym_results.append(f"insider={len(txns)}")
                else:
                    totals["insider_fail"] += 1
                    sym_results.append("insider=[yellow]0[/yellow]")
            except Exception:
                totals["insider_fail"] += 1
                sym_results.append("insider=[red]FAIL[/red]")

            try:
                mentions = sentiment.mention_counts(symbol)
                if mentions:
                    store.save_mentions(symbol, mentions)
                    totals["mentions"] += len(mentions)
                    sym_results.append(f"mentions={len(mentions)}")
                else:
                    totals["mentions_fail"] += 1
                    sym_results.append("mentions=[yellow]0[/yellow]")
            except Exception:
                totals["mentions_fail"] += 1
                sym_results.append("mentions=[red]FAIL[/red]")

            results[symbol] = sym_results
            progress.console.print(f"  [cyan]{symbol}[/cyan]  {'  '.join(sym_results)}")
            progress.advance(ingest_task)

    source_table = Table(title="Ingest Summary", border_style="cyan")
    source_table.add_column("Source", style="bold")
    source_table.add_column("OK", style="green")
    source_table.add_column("Failed")
    source_table.add_column("Records")

    def fmt(n: int) -> str:
        return f"[red]{n}[/red]" if n > 0 else f"[green]{n}[/green]"

    source_table.add_row(
        "Bars",
        fmt(len(universe) - totals["bars_fail"]),
        fmt(totals["bars_fail"]),
        str(totals["bars"]),
    )
    source_table.add_row(
        "Fundamentals",
        fmt(len(universe) - totals["fundamentals_fail"]),
        fmt(totals["fundamentals_fail"]),
        str(totals["fundamentals"]),
    )
    source_table.add_row(
        "Insider",
        fmt(len(universe) - totals["insider_fail"]),
        fmt(totals["insider_fail"]),
        str(totals["insider"]),
    )
    source_table.add_row(
        "Sentiment",
        fmt(len(universe) - totals["mentions_fail"]),
        fmt(totals["mentions_fail"]),
        str(totals["mentions"]),
    )
    console.print(source_table)


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

    from app.store import CanonicalStore

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
    from pathlib import Path

    from app.store import CanonicalStore
    from domain.ask import ask as ask_domain
    from domain.ask import is_concept_query

    query_text = " ".join(query)
    store = CanonicalStore(base_path=Path("data"))

    concept_card: str | None = None
    if is_concept_query(query_text):
        concepts_dir = Path(__file__).resolve().parent / "concepts"
        concept_card = _load_concept_card(query_text, concepts_dir)

    result = ask_domain(query_text, store, concept_card=concept_card, ref_date=date.today())
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

    from app.store import CanonicalStore

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
    check_connections: bool = typer.Option(  # noqa: B008
        False,
        "--check-connections",
        help="Ping each data source to verify connectivity",
    ),
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
    Use flags to drill into connections, alerts, or configuration.
    """
    from pathlib import Path

    from adapters.real.base_connector import BaseConnector
    from app.factory import (
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sec_connector,
        create_sentiment_feed,
    )
    from app.halt import is_halted, read_halt
    from app.store import CanonicalStore
    from app.vault import Vault

    config = _load_config_cached(ctx)

    if alerts:
        from app.alerts import get_recent_alerts

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

    if check_connections:
        vault: Vault | None = Vault(base_path=Path("vault")) if config.data.mode == "live" else None
        connectors: list[tuple[str, object]] = [
            ("market_data", create_market_data(config, vault)),
            ("fundamentals", create_fundamentals(config, vault)),
            ("insider_feed", create_insider_feed(config, vault)),
            ("sentiment_feed", create_sentiment_feed(config, vault)),
            ("sec", create_sec_connector(config, vault)),
        ]
        table = Table(title="Connection Status", border_style="cyan")
        table.add_column("Source", style="bold")
        table.add_column("Status")
        for name, conn in connectors:
            ok = conn.check_connection() if isinstance(conn, BaseConnector) else True
            _check_connection(name, ok, table)
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
    from app.halt import clear_halt, is_halted, read_halt, write_halt

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


@app.command(rich_help_panel="Ops")
def schedule(
    ctx: typer.Context,
    mode: str = typer.Option(  # noqa: B008
        "live",
        "--mode",
        "-m",
        help="Schedule mode: live or fixture",
    ),
) -> None:
    """Start the daily scheduler daemon.

    Launches APScheduler to run the pipeline automatically every trading day
    at 17:30 ET.
    """
    config = _load_config_cached(ctx)
    config.data.mode = mode

    from app.scheduler import setup_scheduler

    scheduler = setup_scheduler(config_path=ctx.obj.get("config_path"), mode=mode)
    _print_panel(
        "Scheduler Started",
        [
            ("Mode", f"[cyan]{mode}[/cyan]"),
            ("Time", "17:30 ET"),
            ("Stop", "[dim]Ctrl+C to stop[/dim]"),
        ],
        border_style="green",
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        console.print("[yellow]Scheduler stopped.[/yellow]")
        scheduler.shutdown(wait=False)


# ── Sanity Check ────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Ops")
def sanity_check(
    ctx: typer.Context,
    symbol: str = typer.Option(  # noqa: B008
        "AAPL",
        "--symbol",
        "-s",
        help="Symbol to test against (default: AAPL)",
    ),
) -> None:
    """Test all ingestion adapters against a single symbol.

    Runs a quick check against every data source to verify connectivity
    and API keys are working. No data is written to the store.

    [bold]Examples:[/bold]
      \b
      alpha-quant sanity-check
      alpha-quant sanity-check --symbol MSFT
      alpha-quant sanity-check --symbol AAPL --verbose
    """
    import time
    from datetime import date, timedelta

    from app.factory import (
        create_fundamentals,
        create_insider_feed,
        create_market_data,
        create_sentiment_feed,
    )

    config = _load_config_cached(ctx)
    config.data.mode = "live"

    table = Table(title=f"Sanity Check — {symbol}", border_style="cyan")
    table.add_column("Source", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("Time", style="dim")

    results: list[tuple[str, str, str, str]] = []

    def run_check(name: str, fn) -> None:
        t0 = time.perf_counter()
        try:
            detail = fn()
            elapsed = time.perf_counter() - t0
            results.append((name, "[green]\u2713 OK[/green]", detail, f"{elapsed:.1f}s"))
        except Exception as e:
            elapsed = time.perf_counter() - t0
            msg = str(e)[:80]
            results.append((name, "[red]\u2717 FAIL[/red]", f"[red]{msg}[/red]", f"{elapsed:.1f}s"))

    def check_bars() -> str:
        md = create_market_data(config)
        today = date.today()
        bars = md.daily_bars(symbol, today - timedelta(days=10), today)
        return f"{len(bars)} bars" if bars else "[yellow]no bars returned[/yellow]"

    def check_eodhd() -> str:
        fd = create_fundamentals(config)
        snap = fd.snapshot(symbol)
        if snap is None:
            return "[yellow]no snapshot[/yellow]"
        fields = []
        if snap.market_cap:
            fields.append(f"mcap={snap.market_cap:,.0f}")
        if snap.pe_ratio:
            fields.append(f"pe={snap.pe_ratio:.1f}")
        return ", ".join(fields) if fields else "snapshot OK"

    def check_openinsider() -> str:
        insider = create_insider_feed(config)
        txns = insider.cluster_transactions(symbol)
        return f"{len(txns)} clusters" if txns else "[yellow]no clusters[/yellow]"

    def check_reddit() -> str:
        sentiment = create_sentiment_feed(config)
        mentions = sentiment.mention_counts(symbol)
        return f"{len(mentions)} mentions" if mentions else "[yellow]no mentions[/yellow]"

    run_check("Tiingo Bars", check_bars)
    run_check("EODHD Fundamentals", check_eodhd)
    run_check("OpenInsider", check_openinsider)
    run_check("Reddit Sentiment", check_reddit)

    for name, status, detail, elapsed in results:
        table.add_row(name, status, detail, elapsed)

    console.print(table)


# ── Backup ──────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Ops")
def backup(
    prune: bool = typer.Option(  # noqa: B008
        False,
        "--prune",
        help="Remove old backups per retention policy",
    ),
) -> None:
    """Create a backup archive of the state store and vault.

    Compresses the DuckDB state database and vault data into a single archive.
    Use --prune to clean up old backups after creating a new one.
    """
    from app.backup import prune_backups, run_backup

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
