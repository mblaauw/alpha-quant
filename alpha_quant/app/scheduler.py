from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from alpha_quant.app.config import load_config, redact_config
from alpha_quant.app.halt import is_halted
from alpha_quant.app.pipeline import PipelineConfig
from alpha_quant.app.pipeline import run as run_pipeline
from alpha_quant.app.store import CanonicalStore
from alpha_quant.domain.calendar import is_market_day

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

    logger.info(
        "pipeline_start",
        run_id=run_id,
        date=str(run_date),
        mode=mode,
        symbols=len(universe),
    )

    try:
        result = run_pipeline(
            run_date=run_date,
            store=store,
            universe=universe,
            config=pipeline_cfg,
            prev_equity=prev_equity,
        )

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
        return {"status": status, "run_id": run_id}

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
