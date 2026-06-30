# ADR-71: Explanation Persistence and Provenance

## Status

Accepted

## Date

2026-06-30

## Context

Explanation results must be traceable to their exact deterministic input, generation parameters, and lifecycle state. Without persistence, explanations are ephemeral and cannot be audited or replayed.

## Decision

Explanation results are persisted in the `run.advice_artifact` table (extended by migration 0012 with columns for the new explanation model):

- `scope` (VARCHAR(32)): identifies the explanation scope (scorecard_stage, scorecard_overall, risk_category, risk_overall, final_output)
- `scope_id` (VARCHAR(64)): identifies the specific entity within the scope (M1-M8, risk limit name)
- `snapshot_id` (VARCHAR(64)): calculation snapshot identifier for stale-detection
- `input_fingerprint` (VARCHAR(64)): hash of the input context for cache matching
- `stale` (BOOLEAN): lifecycle flag indicating whether this explanation is outdated

Every explanation result carries provenance data:

- `prompt_version`: version of the prompt template used
- `model_identifier` / `provider_identifier`: LLM model and provider (via `llm_model`/`llm_provider`)
- `input_hash` / `output_hash`: SHA-256 fingerprints of the input and output
- `validation_status`: "verified", "failed", or "unverified"
- `created_at`: generation timestamp

## Consequences

Positive: Full audit trail; provenance is traceable to snapshot, prompt version, and model; stale state is explicitly tracked.

Negative: Additional storage for explanation content; migration required to add columns.
