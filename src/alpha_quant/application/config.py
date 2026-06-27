import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from alpha_quant.domain._base import FrozenModel
from alpha_quant.domain.risk import RiskConfig


class DataConfig(FrozenModel):
    mode: str = "fixture"
    fixture_version: str = "v1"

    @field_validator("mode")
    @classmethod
    def _mode_valid(cls, v: str) -> str:
        if v not in ("fixture", "live"):
            raise ValueError("mode must be 'fixture' or 'live'")
        return v


class LakeConfig(FrozenModel):
    mode: str = "fixture"
    base_url: str = "http://localhost:8000"
    api_key_env: str = "ALPHA_LAKE_API_KEY"
    fixture_version: str = "v1"

    @field_validator("mode")
    @classmethod
    def _mode_valid(cls, v: str) -> str:
        if v not in ("rest", "fixture"):
            raise ValueError("mode must be 'rest' or 'fixture'")
        return v


class AppLLMConfig(FrozenModel):
    provider: str = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    timeout_s: int = Field(default=30, ge=1, le=300)


class FreshnessConfig(FrozenModel):
    sla_minutes: int = Field(default=120, ge=1, le=1440)
    critical_minutes: int = Field(default=1440, ge=1, le=43200)
    gate_live_decisions: bool = True


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ALPHA_QUANT_",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=True,
    )

    config_version: int = 1

    @field_validator("config_version")
    @classmethod
    def _check_config_version(cls, v: int) -> int:
        if v != 1:
            cls._log_migration_warning(v)
        return v

    @classmethod
    def _log_migration_warning(cls, v: int) -> None:
        import logging as _logging

        _logging.warning(
            "Config version %d detected. Current version is 1. "
            "Run `alpha-quant --help` to see available CLI commands.",
            v,
        )

    data: DataConfig
    lake: LakeConfig = LakeConfig()
    risk: RiskConfig
    llm: AppLLMConfig
    freshness: FreshnessConfig = FreshnessConfig()


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

    local_path = Path(config_path).parent / "config.local.toml"
    if local_path.exists():
        try:
            with local_path.open("rb") as f:
                local_data = tomllib.load(f)
            data = _deep_merge(data, local_data)
        except tomllib.TOMLDecodeError as e:
            msg = f"Invalid TOML in {local_path}: {e}"
            raise ConfigError(msg, source=str(local_path)) from e

    try:
        import os as _os

        env_lake_mode = _os.environ.get("ALPHA_QUANT_LAKE__MODE")
        if env_lake_mode:
            data.setdefault("lake", {})["mode"] = env_lake_mode
        env_lake_url = _os.environ.get("ALPHA_QUANT_LAKE__BASE_URL")
        if env_lake_url:
            data.setdefault("lake", {})["base_url"] = env_lake_url

        return AppConfig.model_validate(data)
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
