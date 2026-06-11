import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alpha_quant.app.catalog import compute_manifest_hash
from alpha_quant.app.config import AppConfig, redact_config

if TYPE_CHECKING:
    from alpha_quant.app.store import CanonicalStore


def run_replay(
    config: AppConfig,
    from_date: str,
    to_date: str,
    fixture_path: str | None = None,
    store: CanonicalStore | None = None,
) -> dict[str, Any]:
    """Stub replay — builds a static metadata dict, runs no DAG.

    Currently this function produces a synthetic "golden_pass" result without
    actually running any pipeline stages. This gives false confidence in I7.

    Stages to wire incrementally as they land (tracked in #97):
      1. indicator engine (derive.py) — load fixture bars, run backfill, emit events
      2. universe selection (universe.py) — M1 filter against fixture data
      3. regime detection (domain/regime.py when it exists)
      4. risk management (domain/risk.py when it exists)
      5. decision engine gates + scoring (M3-M8 when they exist)
      6. order simulation + fill model
      7. paper book + shadow books
      8. narration

    Each wiring step:
      - Replaces the static claim (e.g. "ingest": true) with an actual run
      - Changes the golden output hash (expected — re-bless via make bless-golden)
      - Must be deterministic (I7) — same fixture + config = same output
    """
    cfg_redacted = redact_config(config)
    config_hash = hashlib.sha256(json.dumps(cfg_redacted, sort_keys=True).encode()).hexdigest()[:16]

    fixture_hash = ""
    if fixture_path:
        fixture_hash = compute_manifest_hash(fixture_path)

    run_id: str | None = None
    if store is not None:
        fv = config.data.fixture_version if hasattr(config.data, "fixture_version") else ""
        run_id = store.register_run("replay", config_hash, fv)

    output: dict[str, Any] = {
        "meta": {
            "command": "replay",
            "from_date": from_date,
            "to_date": to_date,
            "fixture_path": fixture_path,
            "fixture_hash": fixture_hash,
            "config_hash": config_hash,
            "run_id": run_id,
        },
        "system": {
            "python": "3.14",
            "platform": "deterministic",
            "config_version": config_hash,
        },
        "symbols": {
            "total": len(config.bootstrap.symbols) + len(config.bootstrap.include_benchmarks),
            "primary": len(config.bootstrap.symbols),
            "benchmarks": len(config.bootstrap.include_benchmarks),
        },
        "pipeline": {
            "status": "golden_pass",
            "stages": [
                "ingest",
                "validate",
                "derive",
                "regime",
                "risk",
                "decide",
                "simulate",
                "persist",
                "narrate",
            ],
            "completed": 9,
        },
    }

    if store is not None and run_id is not None:
        store.complete_run(run_id, "golden_pass", fixture_hash)

    return output


def write_golden(output: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True))
    return path


def golden_hash(output: dict[str, Any]) -> str:
    raw = json.dumps(output, indent=2, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
