# ADR-0004: Use argparse (stdlib) for the CLI

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant has 9 CLI subcommands: `run`, `replay`, `backtest`, `bootstrap`, `journal`, `ask`, `report`, `status`, `halt`. Each needs argument parsing, help text, and subcommand dispatch. The CLI is the primary interface for users and for cron-based scheduling.

## Decision Drivers

- Zero additional dependencies for the CLI path
- Subcommand support with argument delegation
- Help text generation for each subcommand
- Minimal learning curve for the team

## Considered Options

- **Option A: argparse (stdlib)** — Built into Python, sufficient for 9 subcommands, `add_subparsers()` for hierarchy
- **Option B: Click** — Decorator-based, more ergonomic for complex CLI trees, requires external dependency
- **Option C: Typer** — Modern, type-hint-driven, generates help from type annotations, requires `click` + `typer` dependencies

## Decision Outcome

Chosen option: **Option A — argparse (stdlib)**.

Rationale:
1. 9 subcommands with simple arguments (mostly flags and paths) do not justify an additional dependency
2. argparse is universally understood by Python developers — zero learning curve
3. The CLI is thin: each subcommand dispatches to an `app/` module — the complexity is in the modules, not the CLI
4. No need for Click's plugin system or Typer's auto-conversion features
5. One fewer dependency to keep version-compatible across the project's lifetime

### Positive Consequences

- Zero additional runtime dependencies
- CLI works even if the package installation is partially broken (`argparse` is always available)
- Simple, explicit dispatch — no magic

### Negative Consequences

- More boilerplate than Click's decorators (but trivial for 9 subcommands)
- Help text formatting is less polished than Click/Typer
- No auto-completion (can be added separately with `argcomplete` if needed)

## References

- DESIGN.md §1 (CLI entrypoint)
- RAD §5 (Container Architecture — CLI container)
- C4 Container diagram: `docs/architecture/views/container.png`
