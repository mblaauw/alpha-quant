from __future__ import annotations

import pytest

from alpha_quant.adapters.fake.canned_llm import CannedLLM
from alpha_quant.adapters.fake.virtual_clock import VirtualClock
from alpha_quant.adapters.real.clock import SystemClock
from alpha_quant.adapters.real.llm_adapter import OpenAILikeLLM
from alpha_quant.application.config import AppConfig
from alpha_quant.application.factory import (
    create_alpha_lake_reader,
    create_clock,
    create_llm,
)


def _fixture_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "bootstrap": {"symbols": ["AAPL", "SPY"]},
            "data": {"mode": "fixture"},
            "universe": {},
            "portfolio": {},
            "paper": {},
            "risk": {},
            "shadow": {},
            "llm": {},
            "alpaca": {},
            "dashboard": {},
        }
    )


def _live_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "bootstrap": {"symbols": ["AAPL", "SPY"]},
            "data": {"mode": "live"},
            "universe": {},
            "portfolio": {},
            "paper": {},
            "risk": {},
            "shadow": {},
            "llm": {},
            "alpaca": {"api_key": "test_key", "secret_key": "test_secret"},
            "dashboard": {},
        }
    )


class TestCreateClock:
    def test_fixture_mode_returns_virtual_clock(self) -> None:
        clock = create_clock(_fixture_config())
        assert isinstance(clock, VirtualClock)

    def test_live_mode_returns_system_clock(self) -> None:
        clock = create_clock(_live_config())
        assert isinstance(clock, SystemClock)


class TestCreateLLM:
    def test_fixture_mode_returns_canned_llm(self) -> None:
        llm = create_llm(_fixture_config())
        assert isinstance(llm, CannedLLM)

    def test_live_mode_returns_openai_like_llm(self) -> None:
        llm = create_llm(_live_config())
        assert isinstance(llm, OpenAILikeLLM)


class TestCreateAlphaLakeReader:
    def test_fixture_mode(self) -> None:
        from alpha_quant.adapters.fake.alpha_lake_http_fixture import (
            AlphaLakeHttpFixtureClient,
        )

        config = _fixture_config()
        reader = create_alpha_lake_reader(config)
        assert isinstance(reader, AlphaLakeHttpFixtureClient)

    def test_rest_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from alpha_quant.adapters.real.alpha_lake_rest import AlphaLakeRestClient

        captured: dict[str, object] = {}

        def fake_init(
            self: AlphaLakeRestClient,
            base_url: str = "",
            api_key: str = "",
        ) -> None:
            _ = self
            captured["base_url"] = base_url

        monkeypatch.setattr(AlphaLakeRestClient, "__init__", fake_init)
        config = AppConfig.model_validate(
            {
                **_fixture_config().model_dump(mode="json"),
                "lake": {"mode": "rest"},
            }
        )
        create_alpha_lake_reader(config)
        assert captured["base_url"] == config.lake.base_url
