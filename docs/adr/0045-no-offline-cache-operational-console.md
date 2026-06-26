# ADR-0045: No Offline Cache for the Write-Capable Operational Console

## Status

Accepted

## Date

2026-06-26

## Context

Alpha-Quant's operational console is a write-capable interface for monitoring and controlling the decision pipeline. Unlike read-only data exploration dashboards, stale cached data in an operational console can lead to incorrect operator decisions.

The previous Alpha-Quant UI inherited service-worker patterns from Alpha-Lake (which is a read-only data validation desk). An operational console must not serve stale cached responses for state that can be mutated through the same interface.

## Options Considered

1. **Full service-worker offline cache** — enables offline use but risks stale command state, replayed mutations, and misleading status display
2. **Cache-first with background revalidation** — better for performance but still risks showing stale mutable state
3. **No offline cache** — the console requires network connectivity; static assets may use HTTP cache headers, but no service-worker registration

## Decision

Alpha-Quant does not register a service worker in V1.

Operational read and mutation responses are never cached for offline use. Static assets (HTML, CSS, JS, icons) may use standard HTTP cache headers, but no offline-capable caching layer is installed.

A service worker may be reconsidered in a future version only with:

- a deliberate, tested offline policy
- explicit cache invalidation for mutable state
- no risk of replayed or duplicated mutation requests

## Consequences

**Positive:**

- Operators always see current state — no stale portfolio, halt, or command data
- No risk of replayed mutation requests from a cached service worker
- Simpler deployment — no service-worker registration, update, or scope management

**Negative:**

- The console is unavailable without network connectivity
- Static assets are always fetched from the server (can be mitigated with HTTP caching headers)

## Related

- ADR-0042 (Static SPA and Same-Origin FastAPI BFF)
