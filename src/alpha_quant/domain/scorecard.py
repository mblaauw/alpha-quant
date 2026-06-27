"""Scorecard domain models — immutable advice artifacts for the advice workflow."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from alpha_quant.domain._base import FrozenModel


class Recommendation(StrEnum):
    watch = "watch"
    consider_entry = "consider_entry"
    hold = "hold"
    add = "add"
    reduce = "reduce"
    exit_ = "exit"
    do_nothing = "do_nothing"


class ComponentState(StrEnum):
    pass_ = "pass"
    warn = "warn"
    fail = "fail"


class ScorecardComponent(FrozenModel):
    name: str
    category: str
    score: float = 0.0
    state: ComponentState = ComponentState.pass_
    weight: float = 1.0
    passed: bool = True
    reason: str = ""
    details_json: str = "{}"


class Scorecard(FrozenModel):
    scorecard_id: str = ""
    decision_run_id: str = ""
    portfolio_book_id: str = ""
    symbol: str = ""
    security_id: str = ""
    as_of: datetime | None = None
    snapshot_id: str | None = None
    facts_hash: str = ""
    config_hash: str = ""
    strategy_version: str = ""
    recommendation: Recommendation = Recommendation.do_nothing
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_score: float = Field(default=0.0, ge=0.0, le=100.0)
    data_quality: ComponentState = ComponentState.pass_
    components: list[ScorecardComponent] = Field(default_factory=list)
    created_at: datetime | None = None


class ScorecardEvidence(FrozenModel):
    source_type: str = ""
    source_id: str = ""
    description: str = ""
    value_json: str = "{}"
