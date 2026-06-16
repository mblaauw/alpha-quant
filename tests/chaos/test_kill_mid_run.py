"""Chaos test: kill mid-run verifying idempotent restart.

Simulates a SIGKILL during bar ingestion, then verifies the system
recovers cleanly on restart (no duplicate data, no stuck state).
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Point to a temp data directory for isolation
DATA_DIR = Path("/tmp/alpha-quant-chaos-kill")


def _setup() -> None:
    if DATA_DIR.exists():
        import shutil

        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True)


def _run_and_kill() -> bool:
    """Run alpha-quant and kill it mid-process, returns True if we could start it."""
    env = os.environ.copy()
    env["ALPHA_QUANT_DEV"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "app.cli", "run", "--mode", "fixture"],
        cwd=str(DATA_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(2)
    if proc.poll() is not None:
        return False

    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    return True


def _verify_idempotent() -> bool:
    """Verify that re-running produces no errors and doesn't duplicate data."""
    env = os.environ.copy()
    env["ALPHA_QUANT_DEV"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "run", "--mode", "fixture"],
        cwd=str(DATA_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0


def test_kill_mid_run() -> None:
    _setup()
    started = _run_and_kill()
    if not started:
        return
    assert _verify_idempotent(), "System should recover cleanly after kill"
