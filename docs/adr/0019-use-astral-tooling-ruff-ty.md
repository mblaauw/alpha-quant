# ADR-0019: Use Astral Development Tooling (ruff + ty)

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant uses uv (ADR-0002) as its package manager, part of the Astral ecosystem. The project needs linting, formatting, and type checking for code quality. Multiple options exist for each concern, and using tools from a shared ecosystem reduces configuration surface and cognitive overhead.

Key considerations:
- Linting: historically Flake8, now ruff (Astral) is the de facto standard
- Formatting: historically Black, now ruff format (Astral) is the direct replacement
- Type checking: historically mypy, now ty (Astral) offers a Rust-based alternative
- All three Astral tools share configuration conventions and versioning philosophy

## Decision Drivers

- Single ecosystem reduces tool configuration complexity
- Ruff and ty are 10-100x faster than legacy alternatives (Flake8, Black, mypy)
- All three tools are maintained by the same team (Astral) with aligned release cadences
- Growing community adoption lowers bus-factor risk

## Considered Options

### Linting + Formatting

- **Option A: ruff** — Astral's unified linter and formatter, single binary, configured in pyproject.toml
- **Option B: Flake8 + Black + isort** — Traditional stack, multiple configs, slower

### Type Checking

- **Option A: ty** — Astral's Rust type checker, single binary, intersection types, fast
- **Option B: mypy** — Mature, widest adoption, but slower on large codebases
- **Option C: pyright** — Microsoft's TypeScript-adjacent tool, good but separate ecosystem

## Decision Outcome

Chosen option: **Option A for both (ruff + ty)**.

Rationale:
1. Unified pyproject.toml configuration — no separate config files for each tool
2. Ruff replaces Flake8, isort, Black, pyupgrade, and autoflake in a single binary
3. Ty is 10x faster than mypy on equivalent codebases and supports intersection types
4. Both tools are under active development by the same team behind uv (ADR-0002)
5. Agent skills (`astral-sh/claude-code-plugins@ruff`, `jiatastic/open-python-skills@ty-skills`) provide AI-assisted guidance for both tools
6. Consistent CLI patterns: `uv run ruff check .`, `uv run ty check .`

### Positive Consequences

- Zero additional config files beyond pyproject.toml
- Near-instant linting and type checking (both < 1s for the current codebase)
- Agent skills provide contextual guidance for both tools
- Intersection types (ty exclusive) enable cleaner domain model patterns

### Negative Consequences

- ty is newer than mypy — some edge cases may have less mature error messages
- Team must learn ty-specific rule names (different from mypy's error codes)
- Future migration if Astral abandons either tool (low risk given community adoption)

## References

- ADR-0002: uv Package Manager
- DESIGN.md §3.8 (Library decisions)
- RAD §3 (Technology Stack Summary)
- Ruff: https://github.com/astral-sh/ruff
- Ty: https://docs.astral.sh/ty/
