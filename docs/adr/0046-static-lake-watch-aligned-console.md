# ADR-0046: Static Lake Watch–Aligned Operational Console

## Status

Accepted

## Date

2026-06-27

## Context

Alpha-Quant's original operational GUI was a Streamlit dashboard (ADR-0014), later migrated to a FastAPI + Jinja/HTMX dashboard, and then to a static vanilla JavaScript SPA. Each iteration moved closer to the visual and interaction language of Alpha-Lake Lake Watch.

The product distinction is absolute:
- Alpha-Lake Lake Watch = inspect facts, freshness, provenance, PIT state
- Alpha-Quant Desk = operate decisions, portfolio books, risk controls, orders, fills, runs, and journals

A shared visual family reduces operator cognitive load when switching between fact inspection and operational control. However, the implementations must remain separate because the product concerns are different.

## Decision Drivers

- **Operator experience** — operators work with both Lake Watch and Alpha-Quant Desk daily; visual consistency reduces errors
- **No build toolchain** — the frontend must remain a no-build static SPA served by FastAPI, matching the existing deployment model
- **Modularity** — command behaviour and write safety are materially more complex than Lake Watch's read-only fact exploration; a monolithic single-file frontend is unacceptable
- **Same-origin security** — the browser must never talk directly to PostgreSQL, Alpha-Lake, or object storage; all communication goes through the FastAPI BFF

## Decision Outcome

Alpha-Quant uses a static vanilla JavaScript SPA, served by FastAPI, with the visual and interaction language of Alpha-Lake Lake Watch.

Key architectural choices:

1. **CSS token system** — shared visual tokens (--aq-paper, --aq-ink, --aq-rule, etc.) rather than copied CSS files
2. **Horizontal tab navigation** — Desk / Portfolio / Decisions / Orders / Risk / Runs / Journal / System
3. **Top context bar** — active book, mode, operational status, latest run, snapshot, Alpha-Lake health
4. **ES modules** — small focused files per screen, not a monolithic SPA
5. **Right-side drawers** — detail views without page navigation
6. **Modals for mutations only** — no modal dialogs for read-only evidence

## Consequences

### Positive

- Operators see a consistent visual family across Lake Watch and Alpha-Quant
- No build toolchain, Node dependencies, or frontend build stage
- ES module structure is navigable and maintainable
- Same-origin BFF architecture prevents browser-side data access

### Negative

- Visual consistency requires manual effort — no shared component library
- Vanilla JS lacks type safety and component re-rendering optimisation
- CSS token system must be maintained in two places (Lake Watch + Alpha-Quant)

## References

- Supersedes ADR-0014 (Streamlit Dashboard)
- Supersedes previous Jinja/HTMX dashboard approach
- Alpha-Lake Lake Watch visual language
