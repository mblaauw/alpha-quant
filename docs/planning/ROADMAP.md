# Alpha-Quant — Development Roadmap

> **Status:** v1.2 Design Complete · Development phase 0 starting
> **Target:** 8-week build → 3-month evaluation → broker decision point

---

## Timeline Overview

```
Week  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20
      │░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│░░│
      │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
P0    │██▓▓░│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
P1    │░░░░░│████▓▓▓▓░│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
P2    │░░░░░│░░░▓▓▓▓▓▓▓▓▓▓▓▓░│  │  │  │  │  │  │  │  │  │  │  │  │  │  │
P3    │░░░░░│░░░░░░░░░░░▓▓▓▓▓▓▓▓░│  │  │  │  │  │  │  │  │  │  │  │  │  │
P4    │░░░░░│░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓░│  │  │  │  │  │  │  │  │  │  │  │  │
P5    │░░░░░│░░░░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓░│  │  │  │  │  │  │  │  │  │  │  │
P6    │░░░░░│░░░░░░░░░░░░░░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓░░░│  │  │  │  │  │
      │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
      │ W1│ W2│ W3│ W4│ W5│ W6│ W7│ W8│  Evaluation period (≥12 weeks)  │
      │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
Key:  ██ build   ▓▓ active   ░░ not started
```

---

## Phase Summary

| Phase | Title | Duration | Dependencies | Deliverable |
|-------|-------|----------|-------------|-------------|
| **P0** | Skeleton + Fixtures | Week 1 | None | Runnable DAG on fixtures, CI golden replay |
| **P1** | Data Layer | Weeks 1–3 | P0 (ports) | All connectors, vault, canonical stores, derive, validate |
| **P2** | Domain + Backtest + Paper | Weeks 3–5 | P1 (data pipeline) | Decision engine, sizing, risk, fills, backtester, paper book |
| **P3** | Alt-Data Signals | Weeks 5–6 | P2 (domain core), P1 (connectors) | M5, M6, ablation books NO_INSIDER, NO_CROWDING_VETO |
| **P4** | Narration + Education | Weeks 6–7 | P2 (event log), P3 (shadow results) | LLM narrator, concept cards, reports, dashboard |
| **P5** | Live Data Operations | Weeks 7–8 | P1 (real connectors), P4 (monitoring) | Scheduler, alerting, ops commands, backup |
| **P6** | Evaluation | ≥3 months | All prior | Mechanism keep/kill decisions, broker go/no-go |

---

## Milestones

| Milestone | Target | Criteria |
|-----------|--------|----------|
| **M0: First Green Replay** | End of week 1 | `alpha-quant replay --fixture` completes with golden hash match |
| **M1: Data Pipeline Live** | End of week 3 | All 5 connectors running; vault → canonical → derive cycle verified |
| **M2: Paper Trading** | End of week 5 | Full decision cycle on fixtures produces fills, P&L, event log |
| **M3: Alternative Data Live** | End of week 6 | M5 & M6 active; all 3 ablation books updating daily |
| **M4: User-Facing System** | End of week 7 | Narrated daily journal, weekly report, `ask` command working |
| **M5: Unattended Operation** | End of week 8 | 2-week unattended run clean; alerting verified |
| **M6: Evaluation Complete** | 3 months after M5 | Mechanism ablation analysis complete; broker decision made |

---

## Dependency Graph

```
P0 (skeleton)
 ├── P1 (data layer) ──┐
 │                     ├── P2 (domain + backtest + paper)
 │                     │    ├── P3 (alt-data signals)
 │                     │    └── P4 (narration + education)
 │                     │         └── P5 (live operations)
 │                     │              └── P6 (evaluation)
 │                     │
 │  P0 provides:       │  P1 provides:          P2 provides:
 │  • Port interfaces   │  • Real/fake connectors  • Decision engine
 │  • Event log         │  • Vault + canonical     • Fill model
 │  • Clock             │  • Derived indicators    • Backtester
 │  • Config            │  • Validation gates      • Paper portfolio
 │  • Fixture harness   │  • Bootstrap             • Shadow ablation books
 │  • CI golden replay  │                          • Self-consistency
```

---

## Key Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **API rate limits / data gaps** (EODHD, Reddit) | Medium | High — pipeline halts | Degrade-don't-block per §3.2; fixture fallbacks in CI |
| **Indicator engine drift** (numpy vs full-history) | Low | Medium — silent P&L error | CI assert recompute to 1e-6 per symbol |
| **Fill model optimism** | Medium | High — paper results misleading | Gap-through-stop fills at open, not stop; explicit caveat in reports |
| **LLM API outage / cost** | Low | Low — narration degrades, decisions unaffected | Template fallback; stale-while-revalidate concept cards |
| **Walk-forward overfitting** | Medium | Medium — mechanisms fail live | Ablation books detect divergence; max 3 tunable params |
| **Team ramp-up on domain** | Medium | Medium — wrong signal implementation | Fixture-driven TDD; golden replay catches regressions |
| **SEC fair access policy changes** | Low | Medium — ticker map stale | Last-good-cache; weekly refetch; degrade gracefully |

---

## Team & Workflow

### Recommended Team

| Role | Headcount | Involved In |
|------|-----------|-------------|
| **Backend / Data Engineer** | 1–2 | P0, P1, P5 — data layer, connectors, ops |
| **Quant / Domain Developer** | 1–2 | P2, P3 — decision engine, signals, risk |
| **Full-Stack / Frontend** | 1 | P4 — narrator, reports, dashboard |
| **QA / Test Engineer** | 1 (shared) | All phases — golden replay CI, validation |

### Ceremonies & Cadence

- **Daily standup** (15 min): What was done, blockers, what's next
- **Weekly sprint review** (30 min): Demo working system increment
- **Sprint retrospective** (30 min): What worked, what didn't
- **Bi-weekly backlog refinement** (45 min): Re-estimate, re-prioritize, split stories

### Definition of Done (DoD)

For every story:
- [ ] All acceptance criteria pass
- [ ] Unit tests written (pytest, ≥80% coverage on new code)
- [ ] Integration tests pass (fixture replay for affected path)
- [ ] Type annotations complete (mypy strict, no `Any` in domain/)
- [ ] Invariant assertions exist where applicable (I1–I13)
- [ ] Events emitted at all stage boundaries
- [ ] Golden replay passes (or golden file intentionally updated with review)
- [ ] Documentation updated (README, concept cards if user-facing)
- [ ] Code review completed
- [ ] No lint warnings (ruff)

### Estimation (Story Points)

| Size | Points | Meaning |
|------|--------|---------|
| XS | 1 | Trivial: config change, 1-file test, small bugfix |
| S | 2 | Small: well-understood, 1-2 files, <1 day |
| M | 3 | Medium: clear spec, 2-4 files, 1-2 days |
| L | 5 | Large: complex, >4 files, 3-5 days, spike needed |
| XL | 8 | Very large: needs decomposition (break into stories) |

---

## How to Use This Roadmap

1. **Start with Phase 0** — the skeleton is prerequisite for everything
2. **Phase 1 and Phase 0 can overlap** once ports are defined (Week 1)
3. **Phases 2–3 are the critical path** — the decision engine is the product
4. **Phase 4 builds on working internals** — don't rush narration before substance
5. **Phase 5 is de-risking** — test failure modes before leaving unattended
6. **Phase 6 is the real test** — don't shortcut the 3-month evaluation

For story-level breakdown → see [BACKLOG.md](./BACKLOG.md)
