# ADR-0054: Desk Redesigned with Advice-First Tab

## Status

Accepted

## Date

2026-06-27

## Context

The Alpha-Quant Desk was originally designed as an operational console showing
tables of data (positions, orders, decisions, runs). The advice workflow
introduced a new interaction model: daily advice cards with follow/modify/reject
actions. Rather than replacing the Desk tab entirely, a separate Advice tab was
added alongside the existing operational views.

## Decision

Add a dedicated Advice tab showing daily advice cards. Keep the existing Desk
tab as the operational summary view.

The Advice tab shows three sections:
1. **Portfolio actions** — Symbols needing attention (add, reduce, exit recs).
2. **Portfolio overview** — Symbols on hold/watch.
3. **No action needed** — Collapsible list of do-nothing recs.

Each advice card has: recommendation badge, confidence, total score, data quality,
Follow/Reject/Details buttons. Evidence drawer shows component scores.

## Consequences

Positive:
- Clear separation between advice (forward-looking) and operations (current state).
- Advice tab is the default daily landing for users.
- Existing Desk tab unchanged — no disruption for users who want operational data.

Negative:
- Users have one more tab to navigate.
- Advice data depends on a completed decision run — empty state until first run.
