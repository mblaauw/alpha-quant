# ADR-0050: Scorecards Are the Primary Decision Artifact

## Status

Accepted

## Date

2026-06-27

## Context

The original pipeline (pipeline_v2/DuckDB) stored decisions as flat CandidateEvaluation
and PolicyEvaluation rows. These lacked per-component scoring, evidence links, and
structured recommendations. The advice workflow requires richer artifacts:
deterministic component scores, gates, evidence provenance, and a consolidated
recommendation.

## Decision

Replace CandidateEvaluation with Scorecard as the primary decision artifact.

- **Scorecard**: One per symbol per decision run. Contains total_score, confidence,
  recommendation, data_quality, and a list of ScorecardComponent objects.
- **ScorecardComponent**: Individual scored dimension (technical_trend, momentum,
  fundamentals, etc.) with state (pass/warn/fail), weight, and reason.
- **Scorecard run.scorecard** and **run.scorecard_component** tables replace
  run.candidate_evaluation and run.policy_evaluation for all new advice workflows.
- Old rows remain in candidate_evaluation/policy_evaluation for historical queries
  but new runs write only to scorecard tables.

## Consequences

Positive:
- Richer artifact supports both deterministic scoring and LLM explanation.
- Component-level evidence is persisted and queryable.
- Reproducibility via facts_hash, config_hash, and as_of.

Negative:
- Two parallel schemas during migration (candidate_evaluation + scorecard).
- Query code must handle both paths or filter by date.
