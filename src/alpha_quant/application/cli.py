import os
import sys
from collections.abc import Sequence
from importlib.metadata import version as _version

import structlog
import typer
from rich.console import Console
from rich.panel import Panel

from alpha_quant.adapters.postgres.engine import DEFAULT_DATABASE_URL
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


def _database_url_opt() -> str:  # noqa: B008
    return typer.Option(
        DEFAULT_DATABASE_URL,
        "--database-url",
        "-d",
        envvar="DATABASE_URL",
        help="PostgreSQL connection string",
    )


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


# ── Database ────────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Database")
def db_health(
    database_url: str = _database_url_opt(),
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
    database_url: str = _database_url_opt(),
) -> None:
    """Run pending Alembic migrations."""
    from alpha_quant.application.factory import run_migrations

    run_migrations(database_url)
    _print_panel("Migration", [("Status", "[green]up to date[/green]")])


@app.command(rich_help_panel="Database")
def db_migrate_check(
    database_url: str = _database_url_opt(),
) -> None:
    """Check pending migrations without applying them (dry-run)."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    url = database_url or _database_url_opt()
    ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", url)
    command.check(cfg)


@app.command(rich_help_panel="Database")
def db_seed(
    database_url: str = _database_url_opt(),
) -> None:
    """Seed default strategy and portfolio book records."""
    from alpha_quant.application.factory import seed_default_data

    seed_default_data(database_url)
    _print_panel("Seed", [("Status", "[green]default records created[/green]")])


@app.command(rich_help_panel="Database")
def db_dev_seed(
    database_url: str = _database_url_opt(),
) -> None:
    """Seed comprehensive mock data for development (clears all data first)."""
    from alpha_quant.application.dev_seed import seed_dev_data

    pos_count, sc_count = seed_dev_data(database_url)
    _print_panel(
        "Dev Seed",
        [
            ("Status", "[green]mock data created[/green]"),
            ("Positions", f"[cyan]{pos_count}[/cyan]"),
            ("Scorecards", f"[cyan]{sc_count}[/cyan]"),
        ],
    )


@app.command(rich_help_panel="Database")
def db_import(
    duckdb_path: str = typer.Option(  # noqa: B008
        "data/state.db",
        "--duckdb-path",
        help="Path to legacy DuckDB state database",
    ),
    database_url: str = _database_url_opt(),
) -> None:
    """Import legacy DuckDB state into PostgreSQL operational store."""
    from alpha_quant.application.import_legacy_duckdb import run_import

    count = run_import(duckdb_path=duckdb_path, postgres_url=database_url)
    _print_panel("Import", [("Rows imported", f"[green]{count}[/green]")])


# ── Dashboard ───────────────────────────────────────────────────────────────────────────


@app.command(rich_help_panel="Dashboard")
def dashboard(
    host: str = typer.Option("localhost", "--host", help="Bind address"),
    port: int = typer.Option(8501, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code change"),
) -> None:
    """Start the Alpha-Quant operational console server."""
    import uvicorn

    from alpha_quant.transport.app import app as transport_app

    uvicorn.run(transport_app, host=host, port=port, reload=reload)


@app.command(rich_help_panel="Dashboard")
def worker(
    poll_interval: int = typer.Option(1, "--poll-interval", "-i", help="Seconds between polls"),
    one_shot: bool = typer.Option(False, "--one-shot", help="Process one command and exit"),
) -> None:
    """Run the background command worker."""
    import time

    import structlog
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from alpha_quant.adapters.postgres.engine import DEFAULT_DATABASE_URL
    from alpha_quant.application.commands import dispatch

    logger = structlog.get_logger("alpha_quant.worker")
    log = logger.info

    engine = create_engine(DEFAULT_DATABASE_URL, pool_size=2, max_overflow=4, pool_pre_ping=True)
    session_factory: sessionmaker[Session] = sessionmaker(bind=engine)

    def _claim() -> object | None:
        from alpha_quant.adapters.postgres.unit_of_work import OperationalUnitOfWork

        uow = OperationalUnitOfWork(session_factory)
        with uow:
            cmd = uow.store.claim_command()
            if cmd is None:
                return None
            log("claimed_command", command_id=str(cmd.command_id), type=cmd.type)
        result = dispatch(cmd)
        log("completed_command", command_id=str(result.command_id), status=result.status.value)
        return result

    log("worker_started", poll_interval=poll_interval, one_shot=one_shot)
    while True:
        try:
            result = _claim()
            if result is None:
                if one_shot:
                    log("worker_no_work")
                    return
                time.sleep(poll_interval)
        except Exception as e:
            log("worker_error", error=str(e))
            if one_shot:
                return
            time.sleep(poll_interval)


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
