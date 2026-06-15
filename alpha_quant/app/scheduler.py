from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from alpha_quant.app.alerts import alert
from alpha_quant.app.config import load_config, redact_config
from alpha_quant.app.halt import is_halted
from alpha_quant.app.pipeline import PipelineConfig, persist_run_result
from alpha_quant.app.pipeline import run as run_pipeline
from alpha_quant.app.store import CanonicalStore
from alpha_quant.domain.ablation import SHADOW_CONFIGS, ShadowBook
from alpha_quant.domain.calendar import is_market_day
from alpha_quant.domain.fills import FillConfig
from alpha_quant.domain.risk import RiskConfig as DomainRiskConfig
from alpha_quant.domain.sizing import SizingConfig

# Module-level shadow book state (persists across daily calls)
_SHADOW_BOOKS: dict[str, ShadowBook] = {}

if TYPE_CHECKING:
    from apscheduler.schedulers.blocking import BlockingScheduler

logger = structlog.get_logger()


def _setup_scheduler_logging(log_dir: str | Path = "logs") -> None:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "scheduler.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=30,
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger("apscheduler").addHandler(handler)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


def _today() -> date:
    return date.today()


def run_daily_pipeline(
    config_path: str | None = None,
    mode: str = "live",
) -> dict[str, Any]:
    config = load_config(config_path)
    config.data.mode = mode

    if is_halted():
        logger.info("scheduler_skip_halted")
        return {"status": "skipped", "reason": "halted"}

    store = CanonicalStore(base_path=Path("data"))

    run_date = _today()
    if not is_market_day(run_date):
        logger.info("scheduler_skip_non_market_day", date=str(run_date))
        return {"status": "skipped", "reason": "non_market_day"}

    existing = store.list_runs(since_date=run_date)
    for r in existing:
        raw = r["start_ts"]
        r_date = datetime.fromisoformat(raw).date() if isinstance(raw, str) else raw
        if r_date == run_date and r["status"] in ("completed", "running"):
            logger.info("scheduler_skip_duplicate", date=str(run_date), run_id=r["run_id"])
            return {"status": "skipped", "reason": "duplicate", "run_id": r["run_id"]}

    cfg_redacted = redact_config(config)
    config_hash = hashlib.sha256(json.dumps(cfg_redacted, sort_keys=True).encode()).hexdigest()[:16]
    run_id = store.register_run("daily", config_hash, config.data.fixture_version)

    universe = config.bootstrap.symbols + config.bootstrap.include_benchmarks
    pipeline_cfg = PipelineConfig(run_id=run_id)

    prev = store.load_latest_portfolio_snapshot()
    prev_equity = prev.equity if prev else None
    prev_regime = prev.regime if prev else "CAUTION"

    logger.info(
        "pipeline_start",
        run_id=run_id,
        date=str(run_date),
        mode=mode,
        symbols=len(universe),
    )

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

    # Initialize shadow books on first run
    if not _SHADOW_BOOKS:
        for name, config in SHADOW_CONFIGS.items():
            _SHADOW_BOOKS[name] = ShadowBook(book_name=name, config=config)

    try:
        result = run_pipeline(
            run_date=run_date,
            store=store,
            universe=universe,
            config=pipeline_cfg,
            fill_config=fill_config,
            risk_config=risk_config,
            sizing_config=sizing_config,
            prev_equity=prev_equity,
            prev_regime=prev_regime,
            shadow_books=_SHADOW_BOOKS,
        )

        persist_run_result(store, result)

        status = "completed"
        if result.halted:
            status = "halted"
        elif result.violations:
            status = "violations"

    except Exception:
        logger.exception("pipeline_failed", run_id=run_id)
        status = "failed"
        result = None

    finally:
        store.complete_run(run_id, status=status)

    if result is None:
        alert("CRITICAL", "Pipeline failed", f"Run {run_id} failed", macos_notify=True)
        return {"status": status, "run_id": run_id}

    if result.halted:
        alert("CRITICAL", "Pipeline halted", f"Run {run_id} halted", macos_notify=True)
    elif result.violations:
        alert("WARNING", "Pipeline violations", f"Run {run_id}: {len(result.violations)}")

    logger.info(
        "pipeline_complete",
        run_id=run_id,
        status=status,
        decisions=len(result.decisions),
        fills=len(result.fills),
        events=len(result.events),
        violations=len(result.violations),
    )

    return {
        "status": status,
        "run_id": run_id,
        "decisions": len(result.decisions),
        "fills": len(result.fills),
        "events": len(result.events),
        "violations": len(result.violations),
    }


def setup_scheduler(
    config_path: str | None = None,
    mode: str = "live",
    log_dir: str | Path = "logs",
) -> BlockingScheduler:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    _setup_scheduler_logging(log_dir)

    scheduler = BlockingScheduler()
    trigger = CronTrigger(
        hour=17,
        minute=30,
        timezone="America/New_York",
    )

    scheduler.add_job(
        run_daily_pipeline,
        trigger=trigger,
        kwargs={"config_path": config_path, "mode": mode},
    )

    logger.info(
        "scheduler_started",
        trigger="cron 17:30 ET",
        mode=mode,
        config=config_path,
    )
    print(f"[alpha-quant] scheduler: started (17:30 ET daily, mode={mode})")

    return scheduler
