# ADR-0031: Use File-Based Halt Mechanism for System Safety

## Status

Superseded (by ADR-0040 — Database-Backed Halts)

## Date

2026-06-15

## Context

Alpha-Quant runs unattended via APScheduler. When a critical condition occurs (data staleness exceeds threshold, consistency violation, daily loss limit hit), the system must stop processing until a human reviews the situation. The halt must survive process restarts — an in-memory flag is insufficient.

The halt mechanism serves two purposes:
1. **Prevent pipeline runs** while halted — `run`, `backtest`, and `replay` commands check before executing
2. **Provide diagnostic information** — the halt record includes reason, timestamp, and affected symbols

The halt is cleared manually by an operator (via `alpha-quant halt --reason resume`) after reviewing and resolving the issue.

## Decision Drivers

- **Crash-safe** — Halt state must survive process termination and machine restart
- **Minimal dependencies** — No database connection needed to check halt status (the database itself may be the source of the halt)
- **Anyone can check** — CLI, dashboard, and scheduler all need to read halt status without importing heavy modules
- **Atomic write** — Setting and clearing the halt must be atomic to prevent race conditions

## Considered Options

- **Option A: File-based protocol (current choice)** — `data/.HALT` JSON file with `{reason, timestamp, halted_by}`. `is_halted()` checks file existence. `write_halt()` atomically writes via tempfile+rename
- **Option B: Database flag** — Store halt status in `state.db` `admin` table. Check via DuckDB query
- **Option C: Environment variable** — Set `ALPHA_QUANT_HALTED=1` env var
- **Option D: Process-level flag** — In-memory `threading.Event` in the scheduler process

## Decision Outcome

Chosen option: **Option A — File-based protocol**.

Rationale:
1. Crash-safe — a `.HALT` file persists across reboots. No database dependency
2. Zero-dependency check — `is_halted()` reads a file, imports nothing beyond `pathlib`. The dashboard can check halt status before connecting to the database
3. Atomic writes — `write_halt()` writes to a temp file, then `os.rename()` (atomic on POSIX). Partial writes never produce a valid `.HALT`
4. Human-readable — halt file is valid JSON. An operator can inspect it with any text editor
5. Database flag (Option B) fails if the database itself caused the halt (e.g., corruption, staleness)
6. Env var (Option C) is process-scoped — a scheduler restart would lose the halt state
7. Process-level flag (Option D) is lost on crash — worst-case scenario

### Positive Consequences

- `is_halted()` is a 5-line pure file check — usable everywhere
- The halt file format is extensible: `{"reason": "...", "timestamp": "...", "source": "..."}`
- Dashboard shows halt status before attempting database connection
- Pipeline checks halt status as its first I/O operation — fails fast

### Negative Consequences

- A stray `.HALT` file from a previous session prevents runs — operator must manually delete or run `halt --resume`
- File-based protocol does not support distributed systems — but Alpha-Quant is single-machine
- No expiration — a halt from last week still blocks today's run. Manual clearance required

## References

- `src/app/halt.py` — write_halt, read_halt, is_halted, clear_halt
- DESIGN.md §9.2 (Halt mechanics)
- ADR-0016 (Degrade-don't-block failure model)
- ADR-0024 (Self-consistency invariants — I12 triggers halt)
