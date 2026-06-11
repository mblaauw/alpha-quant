import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BootstrapConfig(BaseModel):
    symbols: list[str]
    history_years: int = 3
    include_benchmarks: list[str] = ["SPY", "^VIX"]

    @field_validator("history_years")
    @classmethod
    def _history_years_bounds(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("history_years must be between 1 and 20")
        return v


class DataConfig(BaseModel):
    raw_tail_days: int = 50
    indicator_state: bool = True
    staleness_halt_hours: int = 30
    fixture_version: str = "fx-2026-06-v1"

    @field_validator("raw_tail_days")
    @classmethod
    def _raw_tail_days_bounds(cls, v: int) -> int:
        if not 5 <= v <= 500:
            raise ValueError("raw_tail_days must be between 5 and 500")
        return v

    @field_validator("staleness_halt_hours")
    @classmethod
    def _staleness_halt_hours_bounds(cls, v: int) -> int:
        if not 1 <= v <= 168:
            raise ValueError("staleness_halt_hours must be between 1 and 168")
        return v


class UniverseConfig(BaseModel):
    min_price: float = 5.0
    min_adv_usd: float = 5_000_000
    index_base: str = "sp500_plus_midcap400"

    @field_validator("min_price")
    @classmethod
    def _min_price_bounds(cls, v: float) -> float:
        if not 0.1 <= v <= 1000:
            raise ValueError("min_price must be between 0.1 and 1000")
        return v

    @field_validator("min_adv_usd")
    @classmethod
    def _min_adv_usd_bounds(cls, v: float) -> float:
        if not 100_000 <= v <= 1_000_000_000:
            raise ValueError("min_adv_usd must be between 100_000 and 1_000_000_000")
        return v


class PortfolioConfig(BaseModel):
    max_positions: int = 8
    max_position_pct: float = 0.15
    max_gross_exposure: float = 0.80
    risk_per_trade_pct: float = 0.01
    max_sector_positions: int = 2

    @field_validator("max_positions")
    @classmethod
    def _max_positions_bounds(cls, v: int) -> int:
        if not 1 <= v <= 100:
            raise ValueError("max_positions must be between 1 and 100")
        return v

    @field_validator("max_position_pct", "max_gross_exposure", "risk_per_trade_pct")
    @classmethod
    def _pct_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("percentage must be between 0.0 and 1.0")
        return v


class PaperConfig(BaseModel):
    starting_equity: float = 100_000.0
    slippage_bps: int = 5
    spread_model: str = "half_spread_estimate"

    @field_validator("starting_equity")
    @classmethod
    def _starting_equity_bounds(cls, v: float) -> float:
        if not 1_000 <= v <= 100_000_000:
            raise ValueError("starting_equity must be between 1_000 and 100_000_000")
        return v

    @field_validator("slippage_bps")
    @classmethod
    def _slippage_bps_bounds(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("slippage_bps must be between 0 and 100")
        return v


class RiskConfig(BaseModel):
    stop_atr_mult: float = 2.0
    trail_after_r: float = 1.0
    partial_take_at_r: float = 2.0
    time_stop_days: int = 30
    dd_ladder: list[list[float]] = [[0.10, 0.5], [0.15, 0.0]]
    daily_loss_halt_pct: float = 0.03

    @field_validator("stop_atr_mult", "trail_after_r", "partial_take_at_r")
    @classmethod
    def _r_multiple_bounds(cls, v: float) -> float:
        if not 0.1 <= v <= 10:
            raise ValueError("R-multiple must be between 0.1 and 10")
        return v

    @field_validator("time_stop_days")
    @classmethod
    def _time_stop_days_bounds(cls, v: int) -> int:
        if not 1 <= v <= 365:
            raise ValueError("time_stop_days must be between 1 and 365")
        return v

    @field_validator("daily_loss_halt_pct")
    @classmethod
    def _daily_loss_halt_pct_bounds(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("daily_loss_halt_pct must be between 0.0 and 1.0")
        return v


class ShadowConfig(BaseModel):
    books: list[str] = ["RULES_ONLY", "NO_INSIDER", "NO_CROWDING_VETO"]


class LLMConfig(BaseModel):
    provider: str = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    base_url: str = ""
    timeout_s: int = 30

    @field_validator("timeout_s")
    @classmethod
    def _timeout_s_bounds(cls, v: int) -> int:
        if not 1 <= v <= 300:
            raise ValueError("timeout_s must be between 1 and 300")
        return v


class EducationConfig(BaseModel):
    level: str = "beginner"
    concept_repeat_limit: int = 3

    @field_validator("concept_repeat_limit")
    @classmethod
    def _concept_repeat_limit_bounds(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("concept_repeat_limit must be between 1 and 10")
        return v


class EODHDConfig(BaseModel):
    api_key: SecretStr = SecretStr("")
    base_url: str = "https://eodhd.com/api"


class AlpacaConfig(BaseModel):
    api_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    base_url: str = "https://data.alpaca.markets"


class ConnectorConfig(BaseModel):
    user_agent: str = "AlphaQuant/0.1.0 (research project; contact m@mblaauw.dev)"
    tokens_per_second: float = 10.0
    max_burst: float = 20.0
    default_timeout_s: float = 30.0


class DashboardConfig(BaseModel):
    host: str = "localhost"
    port: int = 8501
    refresh_seconds: int = 60

    @field_validator("port")
    @classmethod
    def _port_bounds(cls, v: int) -> int:
        if not 1024 <= v <= 65535:
            raise ValueError("port must be between 1024 and 65535")
        return v

    @field_validator("refresh_seconds")
    @classmethod
    def _refresh_seconds_bounds(cls, v: int) -> int:
        if not 5 <= v <= 3600:
            raise ValueError("refresh_seconds must be between 5 and 3600")
        return v


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ALPHA_QUANT_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    bootstrap: BootstrapConfig
    data: DataConfig
    universe: UniverseConfig
    portfolio: PortfolioConfig
    paper: PaperConfig
    risk: RiskConfig
    shadow: ShadowConfig
    llm: LLMConfig
    education: EducationConfig
    connector: ConnectorConfig
    eodhd: EODHDConfig
    alpaca: AlpacaConfig
    dashboard: DashboardConfig


class ConfigError(Exception):
    def __init__(self, message: str, source: str = "") -> None:
        self.source = source
        super().__init__(message)


def _resolve_config_path(path: str | None) -> str:
    if path is not None:
        return path
    for candidate in [Path("config.toml"), Path.home() / ".alpha-quant" / "config.toml"]:
        if candidate.exists():
            return str(candidate)
    msg = "No config.toml found in $PWD or ~/.alpha-quant/"
    raise ConfigError(msg)


def _merge_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    prefix = "ALPHA_QUANT_"
    delimiter = "__"
    result = {k: dict(v) if isinstance(v, dict) else v for k, v in data.items()}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix) :].lower().split(delimiter)
        target = result
        for part in path[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[path[-1]] = value
    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | None = None) -> AppConfig:
    config_path = _resolve_config_path(path)
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        msg = f"Invalid TOML in {config_path}: {e}"
        raise ConfigError(msg, source=config_path) from e
    except FileNotFoundError as e:
        msg = f"Config file not found: {config_path}"
        raise ConfigError(msg, source=config_path) from e

    # Layer local overrides on top if they exist
    local_path = Path(config_path).parent / "config.local.toml"
    if local_path.exists():
        try:
            with local_path.open("rb") as f:
                local_data = tomllib.load(f)
            data = _deep_merge(data, local_data)
        except tomllib.TOMLDecodeError as e:
            msg = f"Invalid TOML in {local_path}: {e}"
            raise ConfigError(msg, source=str(local_path)) from e

    merged = _merge_env_overrides(data)
    try:
        return AppConfig.model_validate(merged)
    except Exception as e:
        errors = getattr(e, "errors", lambda: None)()
        if errors:
            parts = []
            for err in errors:
                loc = ".".join(str(p) for p in err.get("loc", []))
                parts.append(f"{loc}: {err.get('msg', err.get('type', '?'))}")
            details = "; ".join(parts)
            msg = f"Invalid config in {config_path}: {details}"
        else:
            msg = f"Invalid config in {config_path}: {e}"
        raise ConfigError(msg, source=config_path) from e


def redact_config(config: AppConfig) -> dict[str, Any]:
    return config.model_dump(mode="json")
