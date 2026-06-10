# ADR-0002: Use uv as the Package Manager

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant has ~20+ core dependencies and ~8 dev dependencies. Fast, reproducible dependency resolution is critical for CI (golden replay must be deterministic) and for onboarding new developers. The choice of package manager affects lockfile format, workflow speed, and CI pipeline complexity.

## Decision Drivers

- CI must install dependencies in < 30 seconds (golden replay CI runs on every PR)
- Deterministic, reproducible builds across macOS and Linux
- Support for editable installs (`pip install -e .`)
- Workspace support for potential future library splits (e.g., `alpha-quant-core`, `alpha-quant-data`)

## Considered Options

- **Option A: uv** — Rust-based, 10-100x faster than pip, `uv.lock` lockfile, workspace support, growing ecosystem adoption
- **Option B: pip + virtualenv** — Standard, widely understood, but slow resolution for 20+ deps
- **Option C: Poetry** — Mature, lockfile, but slower than uv for dependency resolution; transitive dependency conflicts more frequent

## Decision Outcome

Chosen option: **Option A — uv**.

Rationale:
1. CI speed: uv resolves and installs all dependencies in ~10 seconds vs ~60+ seconds for pip
2. Lockfile determinism: `uv.lock` captures exact versions, ensuring CI matches local development
3. Workspace support: future-proof for extracting shared libraries
4. No runtime dependency — uv is a build/dev tool only; the package itself installs via `pyproject.toml` metadata
5. Community trajectory: uv is increasingly the default for new Python projects (FastAPI, ruff, etc.)

### Positive Consequences

- CI pipeline completes in < 10 minutes (dependency install is not the bottleneck)
- Developers can reproduce the exact same environment with `uv sync`
- Simple commands: `uv add httpx`, `uv sync`, `uv run alpha-quant status`

### Negative Consequences

- Additional tool to install (though `brew install uv` and `curl -LsSf https://astral.sh/uv/install.sh` are trivial)
- Team must learn uv CLI (similar to pip, but not identical)
- Not yet the universal default (pip-users need a brief orientation)

## References

- DESIGN.md §3.8 (Library decisions)
- uv documentation: https://docs.astral.sh/uv/
- RAD §3 (Technology Stack Summary)
