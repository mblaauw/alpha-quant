"""AdviceLLMService — converts deterministic scorecards into structured LLM explanations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from alpha_quant.domain.advice import AdviceArtifact, AdviceRecommendation
from alpha_quant.domain.scorecard import Recommendation, Scorecard
from alpha_quant.ports.llm import LLM

_PROMPT_VERSION = "1.0"
_MAX_RETRIES = 2


@dataclass
class PortfolioSummary:
    equity: float = 0.0
    cash: float = 0.0
    position_count: int = 0
    regime: str = "RISK_ON"


class AdviceLLMService:
    """Generates structured LLM advice explanations from deterministic scorecards.

    LLM input: strict JSON packet with scorecard + portfolio context + deterministic recommendation.
    LLM output: schema-validated JSON that maps to AdviceRecommendation.
    """

    def __init__(self, llm: LLM, prompt_version: str = _PROMPT_VERSION) -> None:
        self._llm = llm
        self._prompt_version = prompt_version

    def generate_advice(
        self,
        scorecard: Scorecard,
        portfolio: PortfolioSummary | None = None,
    ) -> AdviceArtifact:
        now = datetime.now(UTC)
        portfolio = portfolio or PortfolioSummary()

        # Build input packet
        scorecard_data = self._build_scorecard_dict(scorecard)

        input_packet = {
            "prompt_version": self._prompt_version,
            "scorecard": scorecard_data,
            "portfolio_context": {
                "equity": portfolio.equity,
                "cash": portfolio.cash,
                "position_count": portfolio.position_count,
                "regime": portfolio.regime,
            },
            "deterministic_recommendation": {
                "action": scorecard.recommendation.value,
                "confidence": scorecard.confidence,
                "total_score": scorecard.total_score,
            },
            "allowed_actions": [
                "add",
                "hold",
                "reduce",
                "exit",
                "watch",
            ],
        }

        input_json = json.dumps(input_packet, indent=2, default=str)
        input_hash = hashlib.sha256(input_json.encode()).hexdigest()[:16]

        prompt = _build_prompt(input_json)

        recommendation = self._call_llm_with_retry(prompt, scorecard.recommendation)
        output_json = json.dumps(
            recommendation.model_dump() if hasattr(recommendation, "model_dump") else {},
            default=str,
        )
        output_hash = hashlib.sha256(output_json.encode()).hexdigest()[:16]

        deterministic_differs = recommendation.recommendation != scorecard.recommendation

        return AdviceArtifact(
            scorecard_id=scorecard.scorecard_id,
            llm_provider=getattr(self._llm, "_provider", ""),
            llm_model=getattr(self._llm, "_model", ""),
            prompt_version=self._prompt_version,
            input_hash=input_hash,
            output_hash=output_hash,
            validation_status="valid",
            recommendation=recommendation,
            deterministic_differs=deterministic_differs,
            created_at=now,
        )

    def _build_scorecard_dict(self, scorecard: Scorecard) -> dict[str, Any]:
        return {
            "symbol": scorecard.symbol,
            "total_score": scorecard.total_score,
            "recommendation": scorecard.recommendation.value,
            "confidence": scorecard.confidence,
            "data_quality": scorecard.data_quality.value if scorecard.data_quality else "pass",
            "components": [
                {
                    "name": c.name,
                    "score": c.score,
                    "state": c.state.value if c.state else "pass",
                    "weight": c.weight,
                    "passed": c.passed,
                    "reason": c.reason,
                }
                for c in scorecard.components
            ],
        }

    def _call_llm_with_retry(
        self,
        prompt: str,
        fallback_rec: Recommendation,
    ) -> AdviceRecommendation:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._llm.explain(prompt)
                parsed = self._parse_llm_response(response)
                if parsed is not None:
                    return parsed
            except Exception:
                if attempt == _MAX_RETRIES:
                    return self._fallback_recommendation(fallback_rec)
        return self._fallback_recommendation(fallback_rec)

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
                key_reasons=data.get("key_reasons", []),
                main_risks=data.get("main_risks", []),
                what_changed=data.get("what_changed_since_previous_run", []),
                override_guidance=data.get("override_guidance", []),
            )
        except (ValueError, TypeError):  # fmt: skip
            return None

    def _fallback_recommendation(self, rec: Recommendation) -> AdviceRecommendation:
        return AdviceRecommendation(
            recommendation=rec,
            confidence_label="low",
            headline=f"Deterministic recommendation: {rec.value}",
            summary="LLM explanation unavailable; showing deterministic result.",
        )


_ADVICE_SYSTEM_PROMPT = """You are a quantitative trading advisor for a hobby investor.
You receive a data packet with a deterministic scorecard and portfolio context.
Your job is to EXPLAIN the scorecard results in a structured, actionable format.

Rules:
- Never compute prices, stops, or position sizes.
- Never recommend actions outside the allowed_actions list.
- Be concise and specific.
- If the deterministic recommendation says hold, do not recommend buying.
- Output MUST be valid JSON with no markdown wrapping."""


def _build_prompt(input_json: str) -> str:
    return f"""{_ADVICE_SYSTEM_PROMPT}

Return a JSON object with these fields:
- "headline": short one-line summary (max 80 chars)
- "summary": 2-3 sentence explanation
- "recommended_action": one of the allowed_actions
- "confidence_label": "low", "medium", or "high"
- "key_reasons": list of 2-4 reasons for the recommendation
- "main_risks": list of 1-3 risks to watch
- "what_changed_since_previous_run": list of notable changes (can be empty)
- "override_guidance": when the user should override this recommendation (can be empty)

Input packet:
{input_json}

JSON output:"""
