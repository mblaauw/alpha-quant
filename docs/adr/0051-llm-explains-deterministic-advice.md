# ADR-0051: LLM Explains Deterministic Advice — Never Computes It

## Status

Accepted

## Date

2026-06-27

## Context

LLMs are unreliable for numerical computation (stop prices, position sizes,
risk calculations). However, they are effective at explaining structured data
in natural language. The advice workflow needed a way to generate human-readable
explanations for deterministic scorecard results.

## Decision

The LLM ONLY explains outputs from the deterministic scorecard engine. It never
sets stops, sizes, cash allocation, or risk state.

Architecture:
- **Input packet**: Strict JSON schema containing scorecard, portfolio context,
  deterministic recommendation, risk controls, and allowed actions.
- **Output schema**: Validated JSON with headline, summary, recommended_action,
  confidence_label, key_reasons, main_risks, what_changed, override_guidance.
- **Validation**: Output is parsed into AdviceRecommendation Pydantic model.
  Rejected if schema-invalid (falls back to deterministic recommendation).
- **Deterministic differ flag**: If LLM action differs from deterministic
  recommendation, `deterministic_differs=True` is persisted.
- **Audit trail**: prompt_version, input_hash, output_hash, and validation_status
  are persisted with every advice artifact.

## Consequences

Positive:
- LLM errors are contained to the explanation layer — no incorrect price/stops.
- Schema validation catches malformed output before it reaches the user.
- Input/output hashes provide a complete audit trail for every explanation.
- The system degrades gracefully: if the LLM is unavailable or returns garbage,
  the deterministic recommendation is shown directly.

Negative:
- LLM adds latency (1-3 seconds per symbol) to the advice flow.
- API key and provider configuration required for LLM features.
