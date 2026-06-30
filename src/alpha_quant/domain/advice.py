"""Advice domain models — structured output from the LLM explanation layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from alpha_quant.domain._base import FrozenModel
from alpha_quant.domain.scorecard import Recommendation


class ExplanationScope(StrEnum):
    scorecard_stage = "scorecard_stage"
    scorecard_overall = "scorecard_overall"
    risk_category = "risk_category"
    risk_overall = "risk_overall"
    final_output = "final_output"


class ExplanationStatus(StrEnum):
    current = "current"
    recalculating = "recalculating"
    stale = "stale"
    unavailable = "unavailable"


class CalculationSnapshot(FrozenModel):
    snapshot_id: str = ""
    facts_hash: str = ""
    config_hash: str = ""
    policy_config_hash: str = ""
    as_of: datetime | None = None
    scoring_version: str = ""
    risk_model_version: str = ""


class AdviceRecommendation(FrozenModel):
    recommendation: Recommendation = Recommendation.do_nothing
    confidence_label: str = "medium"
    headline: str = ""
    summary: str = ""
    interpretation: str = ""
    educational_context: str = ""
    key_reasons: list[str] = Field(default_factory=list)
    key_evidence: list[str] = Field(default_factory=list)
    key_caveats: list[str] = Field(default_factory=list)
    main_risks: list[str] = Field(default_factory=list)
    data_quality_notes: str = ""
    decision_context: str = ""
    what_changed: list[str] = Field(default_factory=list)
    what_could_change: list[str] = Field(default_factory=list)
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
    scope: str = ExplanationScope.scorecard_overall
    scope_id: str = ""
    snapshot_id: str = ""
    input_fingerprint: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    prompt_version: str = ""
    input_hash: str = ""
    output_hash: str = ""
    validation_status: str = ""
    recommendation: AdviceRecommendation = Field(default_factory=AdviceRecommendation)
    deterministic_differs: bool = False
    stale: bool = False
    created_at: datetime | None = None
