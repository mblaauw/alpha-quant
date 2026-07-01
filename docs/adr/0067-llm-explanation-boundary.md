# ADR-67: LLM Explanation Boundary and Non-Authoritative Role

## Status

Accepted

## Date

2026-06-30

## Context

The scoring engine and risk engine are the sole deterministic sources of truth for all calculations, gates, recommendations, position sizing, and policy decisions. As LLM-generated explanations are introduced, a clear boundary must exist between deterministic computation and LLM narration. Without this boundary, the LLM could appear authoritative or could silently contradict deterministic results.

ADR-0051 established that the LLM explains deterministic advice but never computes it. This ADR refines the boundary to include risk explanations and defines the exact scope of LLM authority.

## Decision

The LLM must only:

- Interpret deterministic results in plain language
- Explain why a result exists based on the evidence provided
- Educate the user about the meaning of indicators, scores, risks, constraints, and trade-offs
- Surface caveats, uncertainty, missing data, freshness concerns, and policy limitations
- Help users understand why a decision was allowed, resized, blocked, or deprioritized

The LLM must never:

- Calculate scores, risk values, weights, or position sizes
- Override scoring or risk policy
- Invent facts, indicators, market data, portfolio state, or missing evidence
- Turn unsupported narrative into a trade recommendation
- Silently produce a different decision than the deterministic engines

The `ExplanationInputBundle` typed data packet enforces this boundary by containing only the information required to explain the result: deterministic values, evidence references, data-quality state, and user-safe display labels. No internal objects, raw database access, or unrestricted prompts are passed to the LLM.

## Consequences

Positive: Clear separation of concerns; deterministic engines remain authoritative; LLM content is always subordinate and labeled.

Negative: Additional abstraction layer between engine output and LLM input; bundle construction adds code surface.
