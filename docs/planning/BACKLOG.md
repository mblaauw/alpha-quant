# Alpha-Quant — Historical Backlog (Retired)

> **Status:** 🏁 Retired — GitHub is the authoritative issue tracker.
> All phase-level stories are resolved. New issues and milestones are tracked at:
> [github.com/mblaauw/alpha-quant/issues](https://github.com/mblaauw/alpha-quant/issues)
>
> **Milestone reference:**
> - [P0–P6 (Completed)](https://github.com/mblaauw/alpha-quant/milestones?state=closed)
> - [Beta Release (Current)](https://github.com/mblaauw/alpha-quant/milestone/8)

---

This file previously tracked implementation stories across phases P0–P6. All phases
are now complete and the system has entered **Beta Release**. The definitions and
conventions below are preserved for historical reference.

---

## Preservation: Definitions (Historical)

### Definition of Done (DoD)

- [ ] Code compiles (ruff, ty)
- [ ] Tests pass (`pytest`)
- [ ] New code has tests (unit + integration if applicable)
- [ ] Event logged for all state mutations
- [ ] ADR updated if architecture changed
- [ ] Regression golden replay still passes (or updated)

### Estimation

Story points (Fibonacci: 1, 2, 3, 5, 8).

### Labels

| Label | Meaning |
|-------|---------|
| `priority/p0` | Blocking — must do before beta |
| `priority/p1` | Important — should do before beta |
| `priority/p2` | Nice to have — can defer |
| `size/s` | ≤1 day |
| `size/m` | 2–3 days |
| `size/l` | 1 week |
| `domain/backend` | Core infrastructure |
| `domain/frontend` | Dashboard, CLI, reporting |
| `domain/data` | Connectors, stores, pipeline |

### Workflow Statuses (Historical)

📝 Backlog → 🔍 Refining → 🏗 In Progress → ✅ Done → ❌ Blocked
