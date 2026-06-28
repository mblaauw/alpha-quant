# ADR-0055: Risk Desk Uses a Stable Placeholder Contract Before the Real Risk Engine

## Status

Superseded by ADR-0056

## Date

2026-06-28

## Context

The redesigned Risk Desk needs a rich `/v1/console/risk` response containing
headline KPIs, VaR/Expected Shortfall, component VaR, stress scenarios,
concentration, factor exposure, liquidity horizon, limits, and events.

The real risk engine for those calculations is larger than the GUI replacement
work. It is tracked as GitHub epic
[#612](https://github.com/mblaauw/alpha-quant/issues/612). Blocking the GUI on
that engine would prevent incremental delivery and force the frontend to be built
against mock data outside the application.

## Decision

`GET /v1/console/risk` returns the final GUI response shape now, backed by a
deterministic placeholder implementation where real risk math is not yet
available.

The placeholder response must:
- Preserve the final field names and value types expected by the GUI.
- Derive equity, gross exposure, concentration, component rows, and liquidity
  rows from current portfolio positions where possible.
- Mark placeholder model parameters explicitly with
  `var.method_params.placeholder = true`.
- Suppress stale cleared-halt details; `halt` is only populated when
  `halted = true`.
- Keep read routes mutation-free and book-scoped through `book_id`.

The real engine will replace the placeholder internals without changing the GUI
contract.

## Consequences

Positive:
- The Risk Desk GUI can be implemented and validated against the production API
  shape immediately.
- Backend and frontend can evolve independently as long as the contract is
  stable.
- Operators can see which fields are placeholder-backed via the explicit marker.

Negative:
- Dashboard risk numbers are not yet production risk analytics.
- Documentation and UI copy must avoid implying that placeholder VaR/ES values
  are real methodology outputs.
- The real risk engine epic remains a required follow-up before risk analytics
  should be used for investment decisions.
