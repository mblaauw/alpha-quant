"""Backup & recovery for alpha-quant state."""

import hashlib
import json
import shutil
import tarfile
from datetime import date
from pathlib import Path
from typing import Any

import structlog
import zstandard

from alpha_quant.app.config import redact_config
from alpha_quant.app.store import CanonicalStore

logger = structlog.get_logger()

_BACKUP_DIR = Path("backups")
_RETENTION_DAILY = 30
_RETENTION_MONTHLY = 12


def _load_config_for_backup(config_path: str | None = None) -> Any:
    from alpha_quant.app.config import load_config, AppConfig

    return load_config(config_path)


def _backup_sqlite(store: CanonicalStore, tmp_dir: Path) -> Path:
    dest = tmp_dir / "state.db"
    store._state_conn.execute(f"BACKUP DATABASE '{dest}'")
    return dest


def _backup_vault_manifest(tmp_dir: Path, vault_base: Path = Path("vault")) -> Path | None:
    manifest_path = vault_base / "manifest.db"
    if not manifest_path.exists():
        return None
    dest = tmp_dir / "vault_manifest.db"
    shutil.copy2(manifest_path, dest)
    return dest


def _backup_config(tmp_dir: Path, config_path: str | None = None) -> Path:
    config = _load_config_for_backup(config_path)
    dest = tmp_dir / "config.json"
    dest.write_text(json.dumps(redact_config(config), indent=2, default=str))
    return dest


def run_backup(config_path: str | None = None) -> Path:

    from alpha_quant.app.store import CanonicalStore

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    store = CanonicalStore(base_path=Path("data"))
    today = date.today()
    date_str = today.isoformat()

    tmp_dir = _BACKUP_DIR / f".tmp_backup_{date_str}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        _backup_sqlite(store, tmp_dir)
        _backup_vault_manifest(tmp_dir)
        _backup_config(tmp_dir, config_path)

        sha = _compute_dir_hash(tmp_dir)
        archive_name = f"alpha-quant-{date_str}-{sha[:16]}.tar.zst"
        archive_path = _BACKUP_DIR / archive_name

        cctx = zstandard.ZstdCompressor(level=3)
        with tarfile.open(fileobj=cctx.stream_writer(open(archive_path, "wb")), mode="w|") as tar:
            for item in tmp_dir.iterdir():
                tar.add(item, arcname=item.name)

        logger.info("backup_complete", path=str(archive_path), sha=sha[:16])
        return archive_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _compute_dir_hash(dir_path: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(dir_path.iterdir()):
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


def prune_backups(
    daily: int = _RETENTION_DAILY,
    monthly: int = _RETENTION_MONTHLY,
) -> list[Path]:
    archives = sorted(_BACKUP_DIR.glob("alpha-quant-*.tar.zst"))
    if not archives:
        return []

    removed: list[Path] = []

    daily_keep: set[str] = set()
    monthly_keep: set[str] = set()

    for a in archives:
        parts = a.stem.split("-")
        if len(parts) >= 3:
            ds = parts[2]
            daily_keep.add(ds)

    daily_sorted = sorted(daily_keep)
    if len(daily_sorted) > daily:
        for old in daily_sorted[:-daily]:
            for a in archives:
                if old in a.stem:
                    removed.append(a)
                    a.unlink()

    remaining = sorted(_BACKUP_DIR.glob("alpha-quant-*.tar.zst"))
    for a in remaining:
        parts = a.stem.split("-")
        if len(parts) >= 3:
            ds = parts[2]
            month_key = ds[:7]
            monthly_keep.add(month_key)

    monthly_sorted = sorted(monthly_keep)
    if len(monthly_sorted) > monthly:
        for old in monthly_sorted[:-monthly]:
            for a in remaining:
                if old in a.stem:
                    removed.append(a)
                    a.unlink()

    return removed
