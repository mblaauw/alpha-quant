"""ExplanationService — generates per-stage and overall LLM explanations for scorecards."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from alpha_quant.application.prompts import (
    ALLOWED_ACTIONS,
    PROMPT_VERSION,
    risk_category_prompt,
    risk_overall_prompt,
    scorecard_overall_prompt,
    scorecard_stage_prompt,
)
from alpha_quant.domain.advice import (
    AdviceArtifact,
    AdviceRecommendation,
    ExplanationScope,
)
from alpha_quant.domain.categories import module_from_component
from alpha_quant.domain.scorecard import Recommendation, Scorecard, ScorecardComponent
from alpha_quant.ports.llm import LLM

logger = structlog.get_logger()
_MAX_RETRIES = 2


@dataclass
class PortfolioSummary:
    equity: float = 0.0
    cash: float = 0.0
    position_count: int = 0
    regime: str = "RISK_ON"


class ExplanationService:
    """Generates structured LLM explanations for scorecard stages and overall results.

    Produces one AdviceArtifact per M-stage (M1-M8), one overall scorecard
    explanation, and one final deterministic output explanation.

    All artifacts carry snapshot_id and input_fingerprint for
    stale-result detection and lifecycle management.
    """

    def __init__(self, llm: LLM, prompt_version: str = PROMPT_VERSION) -> None:
        self._llm = llm
        self._prompt_version = prompt_version

    @staticmethod
    def compute_input_fingerprint(context: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(context, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    @staticmethod
    def make_snapshot(scorecard: Scorecard) -> dict[str, str]:
        return {
            "snapshot_id": hashlib.sha256(
                json.dumps(
                    {
                        "facts_hash": scorecard.facts_hash,
                        "config_hash": scorecard.config_hash,
                        "scorecard_id": scorecard.scorecard_id,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:16],
            "facts_hash": scorecard.facts_hash,
            "config_hash": scorecard.config_hash,
        }

    def generate_stage_explanations(
        self,
        scorecard: Scorecard,
    ) -> list[AdviceArtifact]:
        """Generate one explanation per M-stage (M1-M8)."""
        now = datetime.now(UTC)
        artifacts: list[AdviceArtifact] = []
        seen_mids: set[str] = set()
        snapshot = self.make_snapshot(scorecard)
        snapshot_id = snapshot["snapshot_id"]

        for component in scorecard.components:
            module = module_from_component(component)
            mid = module.get("id", "")
            if not mid or mid in seen_mids:
                continue
            seen_mids.add(mid)

            stage_context = self._build_stage_context(component, module, scorecard)
            fingerprint = self.compute_input_fingerprint(stage_context)
            prompt = scorecard_stage_prompt(stage_context)
            rec, status = self._call_llm_with_retry(prompt, scorecard.recommendation)
            input_json = json.dumps(stage_context, indent=2, default=str)
            input_hash = hashlib.sha256(input_json.encode()).hexdigest()[:16]
            output_json = json.dumps(
                rec.model_dump() if hasattr(rec, "model_dump") else {}, default=str
            )
            output_hash = hashlib.sha256(output_json.encode()).hexdigest()[:16]

            artifacts.append(
                AdviceArtifact(
                    scorecard_id=scorecard.scorecard_id,
                    scope=ExplanationScope.scorecard_stage,
                    scope_id=mid,
                    snapshot_id=snapshot_id,
                    input_fingerprint=fingerprint,
                    llm_provider=getattr(self._llm, "_provider", ""),
                    llm_model=getattr(self._llm, "_model", ""),
                    prompt_version=self._prompt_version,
                    input_hash=input_hash,
                    output_hash=output_hash,
                    validation_status=status,
                    recommendation=rec,
                    deterministic_differs=False,
                    created_at=now,
                )
            )

        logger.info(
            "explanations_generated",
            scope="scorecard_stage",
            scorecard_id=scorecard.scorecard_id,
            count=len(artifacts),
            snapshot_id=snapshot_id,
        )
        return artifacts

    def generate_scorecard_explanation(
        self,
        scorecard: Scorecard,
        portfolio: PortfolioSummary | None = None,
    ) -> AdviceArtifact:
        """Generate an overall explanation for a complete scorecard."""
        now = datetime.now(UTC)
        context = self._build_scorecard_context(scorecard, portfolio)
        fingerprint = self.compute_input_fingerprint(context)
        snapshot = self.make_snapshot(scorecard)
        snapshot_id = snapshot["snapshot_id"]
        prompt = scorecard_overall_prompt(context)
        rec, status = self._call_llm_with_retry(prompt, scorecard.recommendation)

        input_json = json.dumps(context, indent=2, default=str)
        input_hash = hashlib.sha256(input_json.encode()).hexdigest()[:16]
        output_json = json.dumps(
            rec.model_dump() if hasattr(rec, "model_dump") else {}, default=str
        )
        output_hash = hashlib.sha256(output_json.encode()).hexdigest()[:16]

        logger.info(
            "explanations_generated",
            scope="scorecard_overall",
            scorecard_id=scorecard.scorecard_id,
            snapshot_id=snapshot_id,
            validation_status=status,
        )
        return AdviceArtifact(
            scorecard_id=scorecard.scorecard_id,
            scope=ExplanationScope.scorecard_overall,
            snapshot_id=snapshot_id,
            input_fingerprint=fingerprint,
            llm_provider=getattr(self._llm, "_provider", ""),
            llm_model=getattr(self._llm, "_model", ""),
            prompt_version=self._prompt_version,
            input_hash=input_hash,
            output_hash=output_hash,
            validation_status=status,
            recommendation=rec,
            deterministic_differs=False,
            created_at=now,
        )

    def generate_risk_category_explanations(
        self,
        risk_report: dict[str, Any],
        scorecard_id: str = "",
    ) -> list[AdviceArtifact]:
        """Generate one explanation per risk limit/category."""
        now = datetime.now(UTC)
        artifacts: list[AdviceArtifact] = []
        limits = risk_report.get("limits", [])
        as_of = str(risk_report.get("as_of", ""))
        snapshot_id = hashlib.sha256(f"risk:{as_of}".encode()).hexdigest()[:16]

        for limit in limits:
            name = limit.get("name", "Unknown")
            cat_id = name.lower().replace(" ", "_").replace("—", "_")
            category_context = {
                "name": name,
                "current": limit.get("current", ""),
                "limit": limit.get("limit", ""),
                "utilization": limit.get("utilization", 0.0),
                "breach": limit.get("breach", False),
                "as_of": as_of,
            }
            fingerprint = self.compute_input_fingerprint(category_context)
            prompt = risk_category_prompt(category_context)
            fb_rec = Recommendation.watch if not limit.get("breach") else Recommendation.do_nothing
            rec, status = self._call_llm_with_retry(prompt, fb_rec)
            input_json = json.dumps(category_context, indent=2, default=str)
            input_hash = hashlib.sha256(input_json.encode()).hexdigest()[:16]
            output_json = json.dumps(
                rec.model_dump() if hasattr(rec, "model_dump") else {}, default=str
            )
            output_hash = hashlib.sha256(output_json.encode()).hexdigest()[:16]

            artifacts.append(
                AdviceArtifact(
                    scorecard_id=scorecard_id,
                    scope=ExplanationScope.risk_category,
                    scope_id=cat_id,
                    snapshot_id=snapshot_id,
                    input_fingerprint=fingerprint,
                    llm_provider=getattr(self._llm, "_provider", ""),
                    llm_model=getattr(self._llm, "_model", ""),
                    prompt_version=self._prompt_version,
                    input_hash=input_hash,
                    output_hash=output_hash,
                    validation_status=status,
                    recommendation=rec,
                    deterministic_differs=False,
                    created_at=now,
                )
            )

        logger.info(
            "explanations_generated",
            scope="risk_category",
            count=len(artifacts),
            snapshot_id=snapshot_id,
        )
        return artifacts

    def generate_risk_overall_explanation(
        self,
        risk_report: dict[str, Any],
        scorecard_id: str = "",
    ) -> AdviceArtifact:
        """Generate an overall explanation for a complete risk assessment."""
        now = datetime.now(UTC)
        context = self._build_risk_context(risk_report)
        fingerprint = self.compute_input_fingerprint(context)
        as_of = str(risk_report.get("as_of", ""))
        snapshot_id = hashlib.sha256(f"risk:{as_of}".encode()).hexdigest()[:16]
        prompt = risk_overall_prompt(context)

        decisions = risk_report.get("decisions", [])
        primary_action = decisions[0].get("action", "allow") if decisions else "allow"
        fb_action_map = {
            "halt": Recommendation.do_nothing,
            "block": Recommendation.do_nothing,
            "reduce": Recommendation.reduce,
            "allow": Recommendation.hold,
        }
        fb_rec = fb_action_map.get(primary_action, Recommendation.hold)

        rec, status = self._call_llm_with_retry(prompt, fb_rec)
        input_json = json.dumps(context, indent=2, default=str)
        input_hash = hashlib.sha256(input_json.encode()).hexdigest()[:16]
        output_json = json.dumps(
            rec.model_dump() if hasattr(rec, "model_dump") else {}, default=str
        )
        output_hash = hashlib.sha256(output_json.encode()).hexdigest()[:16]

        return AdviceArtifact(
            scorecard_id=scorecard_id,
            scope=ExplanationScope.risk_overall,
            snapshot_id=snapshot_id,
            input_fingerprint=fingerprint,
            llm_provider=getattr(self._llm, "_provider", ""),
            llm_model=getattr(self._llm, "_model", ""),
            prompt_version=self._prompt_version,
            input_hash=input_hash,
            output_hash=output_hash,
            validation_status=status,
            recommendation=rec,
            deterministic_differs=False,
            created_at=now,
        )

    def _build_risk_context(self, risk_report: dict[str, Any]) -> dict[str, Any]:
        limits = [
            {
                "name": lim.get("name", ""),
                "current": lim.get("current", ""),
                "limit": lim.get("limit", ""),
                "utilization": lim.get("utilization", 0.0),
                "breach": lim.get("breach", False),
            }
            for lim in risk_report.get("limits", [])
        ]
        decisions = [
            {
                "action": d.get("action", ""),
                "reason": d.get("reason", ""),
                "limit_name": d.get("limit_name", ""),
            }
            for d in risk_report.get("decisions", [])
        ]
        posture = risk_report.get("posture", {})
        headline = risk_report.get("headline", {})
        var = risk_report.get("var", {})
        concentration = risk_report.get("concentration", {})

        return {
            "as_of": str(risk_report.get("as_of", "")),
            "posture": posture,
            "headline": {
                "var_1d_99_pct": headline.get("var_1d_99_pct", ""),
                "var_1d_99_usd": headline.get("var_1d_99_usd", ""),
                "es_975_pct": headline.get("es_975_pct", ""),
                "es_975_usd": headline.get("es_975_usd", ""),
                "ann_vol": headline.get("ann_vol", ""),
                "beta": headline.get("beta", ""),
                "drawdown": headline.get("drawdown", ""),
                "max_drawdown": headline.get("max_drawdown", ""),
                "gross_exposure": headline.get("gross_exposure", ""),
                "effective_bets": headline.get("effective_bets", ""),
            },
            "var_levels": {
                k: {"pct": v.get("pct", ""), "usd": v.get("usd", "")}
                for k, v in var.get("levels", {}).items()
            }
            if isinstance(var.get("levels"), dict)
            else {},
            "limits": limits,
            "decisions": decisions,
            "concentration": {
                "effective_bets": concentration.get("effective_bets", ""),
                "hhi": concentration.get("hhi", ""),
            },
        }

    def _build_stage_context(
        self,
        component: ScorecardComponent,
        module: dict[str, Any],
        scorecard: Scorecard,
    ) -> dict[str, Any]:
        return {
            "id": module.get("id", ""),
            "name": module.get("name", component.name),
            "type": module.get("type", "score"),
            "question": module.get("question", ""),
            "score": component.score,
            "state": component.state.value,
            "reason": component.reason,
            "metrics": module.get("metrics", []),
            "total_score": scorecard.total_score,
            "recommendation": scorecard.recommendation.value,
            "symbol": scorecard.symbol,
        }

    def _build_scorecard_context(
        self, scorecard: Scorecard, portfolio: PortfolioSummary | None = None
    ) -> dict[str, Any]:
        stages = []
        portfolio = portfolio or PortfolioSummary()
        seen_mids: set[str] = set()
        for component in scorecard.components:
            module = module_from_component(component)
            mid = module.get("id", "")
            if not mid or mid in seen_mids:
                continue
            seen_mids.add(mid)
            stages.append(
                {
                    "id": mid,
                    "name": module.get("name", component.name),
                    "type": module.get("type", ""),
                    "score": component.score,
                    "state": component.state.value,
                    "passed": component.passed,
                }
            )

        return {
            "symbol": scorecard.symbol,
            "total_score": scorecard.total_score,
            "recommendation": scorecard.recommendation.value,
            "confidence": scorecard.confidence,
            "data_quality": scorecard.data_quality.value,
            "stages": stages,
            "facts_hash": scorecard.facts_hash,
            "config_hash": scorecard.config_hash,
            "strategy_version": scorecard.strategy_version,
            "portfolio_equity": portfolio.equity,
            "portfolio_cash": portfolio.cash,
            "portfolio_position_count": portfolio.position_count,
            "portfolio_regime": portfolio.regime,
        }

    def _call_llm_with_retry(
        self,
        prompt: str,
        fallback_rec: Recommendation,
    ) -> tuple[AdviceRecommendation, str]:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._llm.explain(prompt)
                parsed = self._parse_llm_response(response)
                if parsed is not None:
                    status = self._validate_recommendation(parsed)
                    return parsed, status
            except Exception:
                if attempt == _MAX_RETRIES:
                    fb = self._fallback_recommendation(fallback_rec)
                    return fb, "failed"
        fb = self._fallback_recommendation(fallback_rec)
        return fb, "failed"

    @staticmethod
    def _validate_recommendation(rec: AdviceRecommendation) -> str:
        if rec.recommendation.value not in ALLOWED_ACTIONS:
            return "failed"
        if rec.confidence_label not in ("low", "medium", "high"):
            return "failed"
        return "verified"

    def _parse_llm_response(self, raw: str) -> AdviceRecommendation | None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        try:
            return AdviceRecommendation(
                recommendation=data.get("recommended_action", Recommendation.do_nothing.value),
                confidence_label=data.get("confidence_label", "medium"),
                headline=data.get("headline", ""),
                summary=data.get("summary", ""),
                interpretation=data.get("interpretation", ""),
                educational_context=data.get("educational_context", ""),
                key_reasons=data.get("key_reasons", []),
                key_evidence=data.get("key_evidence", []),
                key_caveats=data.get("key_caveats", []),
                main_risks=data.get("main_risks", []),
                data_quality_notes=data.get("data_quality_notes", ""),
                decision_context=data.get("decision_context", ""),
                what_changed=data.get("what_changed_since_previous_run", []),
                what_could_change=data.get("what_could_change", []),
                override_guidance=data.get("override_guidance", []),
            )
        except (ValueError, TypeError):  # fmt: skip
            return None

    @staticmethod
    def _fallback_recommendation(rec: Recommendation) -> AdviceRecommendation:
        return AdviceRecommendation(
            recommendation=rec,
            confidence_label="low",
            headline=f"Deterministic recommendation: {rec.value}",
            summary="LLM explanation unavailable; showing deterministic result.",
        )
