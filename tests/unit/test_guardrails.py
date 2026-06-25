"""Guardrail tests enforcing the REST-only architecture.

These tests verify that:
1. No data-collection code remains
2. No raw indicator/fundamental/insider calculations exist
3. No direct Alpha-Lake Python imports occur
4. No provider SDKs are imported
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
    "lake_inprocess",
    "alpaca_broker",
    "fake_broker",
    "bootstrap",
    "scheduler",
}

_FORBIDDEN_IMPORTS: set[str] = {
    "eodhd",
    "tiingo",
    "sec_connector",
    "openinsider",
    "reddit_sentiment",
    "alpaca_connector",
    "base_connector",
    "token_bucket",
    "vault",
    "lake_inprocess",
    "alpaca_broker",
    "fake_broker",
    "bootstrap",
    "scheduler",
}

_FORBIDDEN_CALCULATION_PATTERNS: list[str] = [
    "calculate_rsi",
    "_rsi_score(",
    "calc_rsi",
    "calculate_macd",
    "_macd_score(",
    "calc_macd",
    "calculate_atr",
    "_atr_score(",
    "calc_atr",
    "calculate_sma",
    "_sma(",
    "calc_sma",
    "calculate_ema",
    "_trend_score(",
    "calc_ema",
    "calculate_bollinger",
    "bollinger_bands(",
    "np.isnan",
    "import numpy",
]


def test_no_forbidden_file_names() -> None:
    """No file in src/ should match a forbidden connector/vault name."""
    errors: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name.startswith("."):
            continue
        stem = path.stem
        if stem in _FORBIDDEN_NAMES:
            errors.append(str(path.relative_to(SRC)))
    assert not errors, "Forbidden file names found:\n  " + "\n  ".join(errors)


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
    assert not errors, "Forbidden imports found:\n  " + "\n  ".join(errors)


def test_no_raw_calculations() -> None:
    """No raw indicator/fundamental/insider calculation in policy code.

    Policy modules must consume pre-computed metrics from Alpha-Lake,
    not recalculate raw values from bars or statements.
    """
    errors: list[str] = []
    policy_dir = SRC / "alpha_quant" / "domain" / "policy"
    if not policy_dir.exists():
        return

    for path in policy_dir.rglob("*.py"):
        if path.name.startswith("."):
            continue
        text = path.read_text()
        rel = path.relative_to(SRC)
        for pattern in _FORBIDDEN_CALCULATION_PATTERNS:
            if pattern in text:
                errors.append(f"{rel} contains '{pattern}'")

    assert not errors, (
        "Forbidden calculation patterns found in policy code.\n"
        "Policy modules must consume Alpha-Lake metrics, not calculate raw values.\n"
        + "\n  ".join(errors)
    )


def test_no_alpha_lake_direct_import() -> None:
    """No file in src/ should import alpha_lake Python modules directly.

    All access to Alpha-Lake must go through the REST API client.
    """
    errors: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name.startswith("."):
            continue
        text = path.read_text()
        rel = path.relative_to(SRC)
        if "import alpha_lake" in text or "from alpha_lake" in text:
            errors.append(str(rel))
    assert not errors, (
        "Direct alpha_lake Python imports found. "
        "Use AlphaLakeRestClient via REST API instead:\n  " + "\n  ".join(errors)
    )


def test_no_duckdb_for_market_facts() -> None:
    """Verify DuckDB is only used for local decision/paper state, not market facts."""
    _ALLOWED_DUCKDB = frozenset({"store", "dashboard.py", "event_sink.py"})
    errors: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name.startswith("."):
            continue
        if any(allowed in str(path) for allowed in _ALLOWED_DUCKDB):
            continue
        text = path.read_text()
        rel = path.relative_to(SRC)
        if "import duckdb" in text or "from duckdb" in text:
            errors.append(str(rel))
    assert not errors, (
        "DuckDB imports found outside store/ and allowed files. "
        "Market facts must come from Alpha-Lake REST API:\n  " + "\n  ".join(errors)
    )


def test_no_selectolax_in_lock() -> None:
    """selectolax should not be in uv.lock."""
    lock = Path(__file__).resolve().parents[2] / "uv.lock"
    text = lock.read_text()
    assert "selectolax" not in text, "selectolax still present in uv.lock"


def test_no_provider_api_keys_in_env_example() -> None:
    """No provider-specific data API key env vars."""
    env = Path(__file__).resolve().parents[2] / ".env.example"
    text = env.read_text()
    for key in ("EODHD", "TIINGO", "REDDIT"):
        assert key not in text, f"Provider env var {key} still in .env.example"
