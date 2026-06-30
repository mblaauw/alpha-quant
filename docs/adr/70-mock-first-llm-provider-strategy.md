# ADR-70: Mock-First LLM Provider Strategy for Explanations

## Status

Accepted

## Date

2026-06-30

## Context

The advice system must work deterministically in tests and local development without a live LLM, external API key, Docker container, or network connection. The existing `CannedLLM` adapter provides this for the initial advice system; it must be extended for the multi-scope explanation system.

## Decision

The `CannedLLM` adapter (in `adapters/fake/canned_llm.py`) provides 12 deterministic fixture scenarios:

1. Positive M-stage explanation
2. Cautionary M-stage explanation
3. Blocking M-stage explanation (earnings blackout)
4. Missing-data explanation
5. Stale-data explanation
6. Risk warning (concentration approaching limit)
7. Risk resizing (per-trade risk cap)
8. Risk hard block (buying power exceeded)
9. Overall scorecard explanation
10. Overall risk explanation
11. Malformed LLM output (non-JSON template — triggers fallback)
12. Timeout/provider failure (non-JSON template)

Fixtures are keyed by `fixture_key` string passed to the constructor (`CannedLLM(fixture_key="positive_stage")`). The default fixture provides a balanced explanation with all new schema fields populated.

All unit tests, e2e mock tests, and CI pipelines use `CannedLLM` exclusively. The `OpenAILikeLLM` adapter is only used in production with a configured API key.

## Consequences

Positive: Zero external dependencies for tests; deterministic assertions; fast test suite (<10s containerless).

Negative: Fixtures must be kept in sync with the actual LLM output schema; the canned output is not representative of real LLM prose quality.
