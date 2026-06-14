"""Tests for golden replay determinism (I7)."""

import hashlib
import json
from pathlib import Path

from alpha_quant.app.config import load_config
from alpha_quant.app.replay import golden_hash, run_replay, write_golden


def test_replay_determinism(tmp_path: Path) -> None:
    """Same config + same fixture → same output hash."""
    config = load_config(None)
    fp = str(Path("fixtures/v1"))
    out1 = run_replay(config, "2024-01-01", "2024-01-03", fixture_path=fp)
    out2 = run_replay(config, "2024-01-01", "2024-01-03", fixture_path=fp)
    assert golden_hash(out1) == golden_hash(out2), "deterministic replay must produce identical hash"


def test_replay_output_structure(tmp_path: Path) -> None:
    """Replay output contains expected top-level keys."""
    config = load_config(None)
    fp = str(Path("fixtures/v1"))
    output = run_replay(config, "2024-01-01", "2024-01-03", fixture_path=fp)
    assert "meta" in output
    assert "decisions" in output
    assert "fills" in output
    assert "equity_curve" in output
    assert "metrics" in output


def test_write_golden_round_trip(tmp_path: Path) -> None:
    """write_golden produces a file whose hash matches golden_hash."""
    config = load_config(None)
    fp = str(Path("fixtures/v1"))
    output = run_replay(config, "2024-01-01", "2024-01-03", fixture_path=fp)
    path = write_golden(output, tmp_path / "golden.json")
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert file_hash == golden_hash(output), "written golden file hash must match computed hash"
