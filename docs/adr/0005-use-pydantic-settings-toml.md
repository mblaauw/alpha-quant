# ADR-0005: Use pydantic-settings + TOML for Configuration

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant has a complex configuration structure: bootstrap parameters, data source settings, portfolio limits, risk thresholds, LLM provider config, education level, and multiple API keys. Configuration must be type-safe, env-overridable (for CI and deployment), and human-readable.

DESIGN.md §2 specifies a TOML config schema with nested sections.

## Decision Drivers

- Type-safe: config errors must be caught at startup, not silently at runtime
- Overridable via environment variables (for CI, Docker, secrets)
- Nested configuration: 9 top-level sections with subsections
- API keys must be handled as secrets (masked in logs, never in source)
- Multiple config discovery paths (project, home directory, explicit `--config`)

## Considered Options

- **Option A: pydantic-settings + TOML** — Nested pydantic models, env overrides with `__` delimiters, TOML file support, SecretStr for keys
- **Option B: dyanaconf + YAML** — Popular in data projects, but no type validation natively
- **Option C: stdlib configparser + envars** — Simple but no type safety, no nesting, no secrets handling

## Decision Outcome

Chosen option: **Option A — pydantic-settings + TOML**.

Rationale:
1. Type validation at startup means invalid config (e.g., `max_positions = 100`) is caught immediately
2. Env override pattern `ALPHA_QUANT_PAPER__STARTING_EQUITY=50000` is clean and works in CI
3. `SecretStr` handles API keys: they serialize as `'******'` in logs and `status` output
4. The team already has pydantic as a dependency (zone-boundary models in the data layer) — no new dependency
5. TOML is more readable than YAML for configuration (fewer edge cases, no footguns with indentation)

### Positive Consequences

- Config validation is automatic and expressive (`@field_validator` for cross-field constraints)
- Single source of truth: the pydantic model IS the schema (generate docs from it)
- Adding a new config field is a one-line addition to the model

### Negative Consequences

- TOML is less expressive than YAML (no anchors/aliases, no multi-line strings without `\`)
- TOML not as widely used as YAML in the Python data ecosystem (but perfectly adequate for config files)
- Overriding deeply nested config via env vars requires remembering the `__` delimited path

## References

- DESIGN.md §2 (Configuration schema), §3.8 (Library decisions)
- RAD §3 (Technology Stack Summary)
