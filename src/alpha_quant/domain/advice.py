"""Advice domain models — structured output from the LLM explanation layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from alpha_quant.domain._base import FrozenModel
from alpha_quant.domain.scorecard import Recommendation


class AdviceRecommendation(FrozenModel):
    recommendation: Recommendation = Recommendation.do_nothing
    confidence_label: str = "medium"
    headline: str = ""
    summary: str = ""
    key_reasons: list[str] = Field(default_factory=list)
    main_risks: list[str] = Field(default_factory=list)
    what_changed: list[str] = Field(default_factory=list)
    override_guidance: list[str] = Field(default_factory=list)


class AdviceAction(StrEnum):
    follow = "follow"
    modify = "modify"
    reject = "reject"


class OperatorOverride(FrozenModel):
    override_id: str = ""
    scorecard_id: str = ""
    command_id: str = ""
    actor_id: str = ""
    original_recommendation: Recommendation = Recommendation.do_nothing
    original_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    override_action: AdviceAction = AdviceAction.follow
    modified_recommendation: Recommendation | None = None
    reason: str = ""
    created_at: datetime | None = None


class AdviceArtifact(FrozenModel):
    advice_id: str = ""
    scorecard_id: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    prompt_version: str = ""
    input_hash: str = ""
    output_hash: str = ""
    validation_status: str = ""
    recommendation: AdviceRecommendation = Field(default_factory=AdviceRecommendation)
    deterministic_differs: bool = False
    created_at: datetime | None = None
