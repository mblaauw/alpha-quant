# ADR-0018: Use Bootstrap + Fixture Bundle Developer Workflow

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant requires a reproducible starting state for development. New developers need to set up the project without API keys and run tests without network access. The design specifies a bootstrap command that fetches real data and freezes a fixture bundle.

DESIGN.md §3.7 specifies: "alpha-quant bootstrap reads [...] config, fetches history_years of daily bars, fundamentals snapshots, earnings dates, OpenInsider history; writes vault → canonical → seeds indicator_state; then freezes a fixture bundle."

## Decision Drivers

- Zero network needed for unit tests and CI (golden replay)
- Reproducible starting state: every developer has the same fixture data
- One command to set up the project: `alpha-quant bootstrap`
- Fixture bundle is versioned (`fixture_version` in config) — changes are tracked in git
- Fast development cycle: domain unit tests (ms) → full-DAG replay (seconds) → real daily runs (only when testing connectors)

## Considered Options

- **Option A: Bootstrap command + frozen fixture bundle** — One-time fetch, freeze fixture, develop against fixtures forever
- **Option B: Live data only** — Always fetch from APIs; requires API keys, network, slower, non-deterministic
- **Option C: Downloadable fixture bundle from releases** — Pre-built fixture bundles published to GitHub Releases — Option A + this for CI

## Decision Outcome

Chosen option: **Option A — Bootstrap command + frozen fixture bundle** (with CI download from releases for faster setup).

Rationale:
1. Determinism: all developers and CI use the same fixture data → golden hash is reproducible
2. Speed: fixture replay is faster than real API calls (no network, no rate limiting)
3. Offline development: work on a plane, in a cafe, or anywhere without internet
4. Versioning: fixture_version in config.toml pinning means the fixture bundle change is deliberate
5. CI integration: the fixture bundle can be pre-built and downloaded from GitHub Releases in CI (faster than re-bootstrapping every run)

### Positive Consequences

- New developer setup: `git clone → uv sync → alpha-quant bootstrap (or download fixtures) → alpha-quant replay`
- CI setup: download pre-built fixture bundle from GitHub Releases → run golden replay
- No API keys needed for development (only for `alpha-quant run --live`)
- The fixture bundle includes synthetic overlays (missing bar, stale feed, mention spike) for edge case testing

### Negative Consequences

- Bootstrapping requires API keys (but only the developer who creates the fixture bundle needs them)
- Fixture bundle is a binary artifact (parquet files) — it goes in the repo's `fixtures/` directory or GitHub Releases
- Re-bootstrapping is required when the symbol list changes (config change → re-bootstrap)
- Fixture bundle size: ~9 symbols × 200 days × daily bars + fundamentals + insider data ≈ 2-5 MB (acceptable in repo or Releases)

## Amendment (2026-06-21)

Fixture workflow now generates lake-shaped bundles consumed by FixtureLakeGateway.

## References

- DESIGN.md §3.7 (Bootstrap), §4 (Clock virtualization and replay)
- RAD §6.1 (Data Layer Components — Bootstrap/Catalog)
- STORY-0.7 (Bootstrap command + fixture bundle), BACKLOG.md
- ADR-0017 (Golden replay CI)
