# ADR-0013: Use structlog with JSON Format for Structured Logging

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant's daily pipeline produces structured events from every stage (ingest, validate, derive, decide, fill, persist). These events serve dual purposes: debug logging during development and operational observability in production. The system also has a formal append-only event log (DESIGN §10) that shares its shape with the debug log stream.

## Decision Drivers

- Structured (JSON) output for machine parsing and log aggregation
- Event shape must be consistent with domain events (the same dict goes to both the event log and the JSON log stream)
- Minimal performance overhead — the pipeline is not latency-sensitive (daily batch), but logging should not dominate runtime
- Support for both human-readable console output (development) and JSON output (production)

## Considered Options

- **Option A: structlog with JSON processor** — Configured pipeline: `[TimeStamper, JSONRenderer]` for production, console rendering for dev
- **Option B: stdlib logging + json formatter** — Works but requires manual dict construction for every log call; structlog provides auto-binding of context vars
- **Option C: loguru** — Popular, simpler API, but no native JSON formatting without a custom sink; adds another dependency

## Decision Outcome

Chosen option: **Option A — structlog with JSON processor**.

Rationale:
1. structlog's processor chain maps naturally to the pattern: enrich → format → output
2. Context variables (run_id, date, source) are automatically bound to every log call in a pipeline run
3. The same `event.model_dump_json()` output goes to both the DuckDB event log and the structlog JSON stream — one write, two consumers
4. CalVer versioning (26.1.0) ensures predictable release cadence
5. Native async log methods (`alog()`, `ainfo()`) for future async paths

### Positive Consequences

- Logs are structured JSON: `{"event": "DATA_INGESTED", "run_id": "...", "source": "tiingo", "symbol_count": 9, "timestamp": "..."}`
- Development console output is human-readable (colors, key-value pairs)
- Context is automatically propagated (no need to pass `run_id` to every log call)
- The event log and debug log share the same data — no duplication

### Negative Consequences

- Learning curve for structlog's processor chain (but it's well-documented and intuitive)
- Slightly more setup than `import logging` (single config at startup, then use throughout)
- structlog adds ~2MB to the dependency tree (negligible for a Python project)

## References

- DESIGN.md §3.8 (Library decisions), §10 (Event log)
- RAD §10 (Cross-Cutting Concerns — Logging & Audit)
- structlog documentation: https://www.structlog.org/
