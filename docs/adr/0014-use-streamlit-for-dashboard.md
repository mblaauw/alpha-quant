# ADR-0014: Use Streamlit for the Read-Only Dashboard

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant requires a read-only dashboard for monitoring: equity curve, position table, risk map, daily journal, and concept card browser. The dashboard reads from the DuckDB state store (via direct DuckDB connection or through the Store port) — zero coupling to pipeline internals. No user interaction that affects the running system.

DESIGN.md §3.8 specifies Streamlit, but this ADR formally documents the rationale.

## Decision Drivers

- Read-only: the dashboard must never affect pipeline state
- Zero coupling: consumes only persisted data (DuckDB state store: events, positions, equity curve)
- Fast to build: the dashboard is a monitoring tool, not the product
- Local deployment: runs on the same machine as the pipeline (or developer workstation for replay data)
- Live data: auto-refresh every 60 seconds during market hours

## Considered Options

- **Option A: Streamlit** — Python-native, fast prototyping, `@st.cache_data` for data caching, Starlette-based in 1.57+
- **Option B: Panel (HoloViz)** — More flexible layouts, better for complex dashboards, but steeper learning curve
- **Option C: Grafana** — Industry standard for monitoring dashboards, but requires Prometheus/InfluxDB metrics pipeline; overkill for reading DuckDB directly
- **Option D: Custom React app** — Full control, but significant frontend investment for a monitoring tool

## Decision Outcome

Chosen option: **Option A — Streamlit**.

Rationale:
1. Fastest path to a functional dashboard: one Python file, ~200 lines of code, immediate results
2. Zero coupling: reads DuckDB state store via Store port or direct DuckDB connection (the same dependency used by the pipeline)
3. Caching with `@st.cache_data` means the dashboard does not re-read the DuckDB state file on every 60-second auto-refresh unless data changed
4. Streamlit 1.57+ uses Starlette (ASGI) internally, which is a better foundation than the old Tornado-based architecture
5. The team already knows Python — no frontend skills required

### Positive Consequences

- Dashboard is built in hours, not days
- Shares the same data access patterns as the pipeline (DuckDB State Store port or direct DuckDB connection)
- Auto-refresh is a one-line config (`st_autorefresh`)
- Low maintenance: read-only means no state management in the dashboard

### Negative Consequences

- Streamlit's rerun model means the entire script re-executes on interaction (mitigated by `@st.cache_data`)
- Limited customization for complex layouts (not an issue for 5 tabs with tables and charts)
- Not suitable for external user-facing dashboards (but this is an internal monitoring tool)

## References

- DESIGN.md §3.8 (Library decisions), §12 (Reporting)
- RAD §5 (Container Architecture — Dashboard), §8 (Deployment)
- C4 Container diagram: `docs/architecture/views/container.png`
- C4 Deployment diagram: `docs/architecture/views/deployment.png`
