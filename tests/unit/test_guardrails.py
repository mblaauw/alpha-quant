"""Guardrail tests that verify no data-collection code remains in src/.

These tests scan the source tree for forbidden patterns that should not
exist after the Alpha-Lake data-plane extraction. All source-data reads
must go through Alpha-Lake, not through local connectors.
"""

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

_FORBIDDEN_NAMES: set[str] = {
    "eodhd_connector",
    "tiingo_connector",
    "sec_connector",
    "sec_fundamentals_connector",
    "openinsider_connector",
    "reddit_sentiment_connector",
    "alpaca_connector",
    "base_connector",
    "token_bucket",
    "vault",
}

_FORBIDDEN_IMPORTS: set[str] = {
    "eodhd_connector",
    "tiingo_connector",
    "sec_connector",
    "sec_fundamentals_connector",
    "openinsider_connector",
    "reddit_sentiment_connector",
    "alpaca_connector",
    "base_connector",
    "token_bucket",
    "vault",
}


def test_no_forbidden_file_names() -> None:
    """No file in src/ should match a forbidden connector/vault name."""
    errors: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name.startswith("."):
            continue
        stem = path.stem
        if stem in _FORBIDDEN_NAMES:
            errors.append(str(path.relative_to(SRC)))
    assert not errors, f"Forbidden file names found:\n  " + "\n  ".join(errors)


def test_no_forbidden_imports() -> None:
    """No file in src/ should import from a deleted module."""
    errors: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name.startswith(".") or path.name == "__init__.py":
            continue
        text = path.read_text()
        rel = path.relative_to(SRC)
        for forbidden in _FORBIDDEN_IMPORTS:
            if (
                f"import {forbidden}" in text
                or f"from .{forbidden}" in text
                or f"from {forbidden}" in text
            ):
                errors.append(f"{rel} -> {forbidden}")
    assert not errors, f"Forbidden imports found:\n  " + "\n  ".join(errors)


def test_no_selectolax_in_lock() -> None:
    """selectolax dependency should not be in uv.lock."""
    lock = Path(__file__).resolve().parents[2] / "uv.lock"
    text = lock.read_text()
    assert "selectolax" not in text, "selectolax still present in uv.lock"


def test_no_provider_api_keys_in_env_example() -> None:
    """No provider-specific data API key env vars in .env.example."""
    env = Path(__file__).resolve().parents[2] / ".env.example"
    text = env.read_text()
    for key in ("EODHD", "TIINGO", "REDDIT"):
        assert key not in text, f"Provider env var {key} still in .env.example"
