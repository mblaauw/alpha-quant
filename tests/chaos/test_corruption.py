"""Chaos test: DuckDB state corruption is detected and triggers consistency halt.

Corrupts the state DB and verifies the system detects it.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

DATA_DIR = Path("/tmp/alpha-quant-chaos-corruption")


def _setup() -> None:
    import shutil

    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True)
    env = os.environ.copy()
    env["ALPHA_QUANT_DEV"] = "1"
    subprocess.run(
        [sys.executable, "-m", "alpha_quant.application.cli", "run", "--mode", "fixture"],
        cwd=str(DATA_DIR),
        env=env,
        capture_output=True,
        timeout=60,
    )


def _corrupt_db() -> None:
    db_path = DATA_DIR / "state.db"
    if db_path.exists():
        db_path.write_bytes(b"CORRUPTED_DATA_" * 100)


def _run_after_corruption() -> int:
    env = os.environ.copy()
    env["ALPHA_QUANT_DEV"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "alpha_quant.application.cli", "run", "--mode", "fixture"],
        cwd=str(DATA_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode


@pytest.mark.chaos
def test_corruption_detected() -> None:
    _setup()
    _corrupt_db()
    time.sleep(1)
    rc = _run_after_corruption()
    assert rc != 0, "System should exit with error on corrupted DB"
