# ADR-69: Structured Output and Validation Contract for Explanations

## Status

Accepted

## Date

2026-06-30

## Context

Free-form LLM text is not suitable for a deterministic trading system. Explanations must follow a validated schema that the API and GUI can reliably consume. ADR-0051 defined the initial advice output schema; this ADR extends it to cover all explanation scopes.

## Decision

All LLM-generated explanations use the `AdviceRecommendation` pydantic model as their output schema, which has been extended with:

- `interpretation`: what the result means in plain language
- `educational_context`: what the indicator/score/risk category measures
- `key_evidence`: specific evidence items that contributed
- `key_caveats`: data-quality, freshness, or assumption caveats
- `data_quality_notes`: specific data quality or freshness concerns
- `decision_context`: why the final weight, position, or action is what it is
- `what_could_change`: conditions that would change this result

Schema validation is enforced via `_validate_recommendation()`:

- `recommended_action` must be in `ALLOWED_ACTIONS = ["add", "hold", "reduce", "exit", "watch", "consider_entry", "do_nothing"]`
- `confidence_label` must be in `{"low", "medium", "high"}`
- On valid parse: `validation_status = "verified"`
- On invalid parse or schema violation: `validation_status = "failed"`, fallback to deterministic content

## Consequences

Positive: Guaranteed parseable output; clear validation status; safe fallback on failure.

Negative: Schema must be versioned alongside prompts; LLM may produce valid JSON that does not answer the question asked.
