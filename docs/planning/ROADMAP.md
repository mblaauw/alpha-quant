# Alpha-Quant — Development Roadmap

> **Status:** 🏁 Beta Release — Phases P0–P6 complete.
> See [Beta Release milestone](https://github.com/mblaauw/alpha-quant/milestone/8)
> for current work items.

---

## Phase Summary (Completed)

| Phase | Title | Duration | Deliverable |
|-------|-------|----------|-------------|
| **P0** | Skeleton + Fixtures | Week 1 | Runnable DAG on fixtures, CI golden replay |
| **P1** | Data Layer | Weeks 1–3 | All connectors, vault, canonical stores, derive, validate |
| **P2** | Domain + Backtest + Paper | Weeks 3–5 | Decision engine, sizing, risk, fills, backtester, paper book |
| **P3** | Alt-Data Signals | Weeks 5–6 | M5, M6, ablation books NO_INSIDER, NO_CROWDING_VETO |
| **P4** | Narration + Education | Weeks 6–7 | LLM narrator, concept cards, reports, dashboard |
| **P5** | Live Data Operations | Weeks 7–8 | Scheduler, alerting, ops commands, backup |
| **P6** | Evaluation | ≥3 months | Mechanism keep/kill decisions, broker go/no-go |

## Current Status: Beta Release

The system is in **Beta Release** with the following capabilities:

### What Works
- Full data pipeline: EODHD, Alpaca, SEC, OpenInsider, Reddit connectors
- Decision engine: 8 mechanisms (universe, regime, technical, quality, insider, crowding, blackout, composite)
- Backtest and paper trading engines with conservative fill model
- Position sizing (ATR-based, Kelly fraction), risk management (stops, trailing, partial takes, drawdown ladder)
- Deterministic golden replay for regression testing
- LLM-powered daily journal narration
- Streamlit dashboard (6 tabs): Home, Portfolio, Reports, Concepts, Daily Journal, Decision Explorer
- CLI with 12 subcommands: bootstrap, replay, ingest, run, backtest, journal, ask, report, status, halt, schedule, backup
- Data quality monitoring (quarantine, staleness halts)

### Known Limitations
- M1 universe uses a configured symbol list (domain `universe.select()` is wired in pipeline)
- M2 regime SPY path is live; VIX/breadth use defaults unless overridden
- Live broker integration is out of scope — paper trading only
- Broker decision documented in `docs/evaluation/BROKER_DECISION.md`; final go/no-go deferred until paper trading results

### Next Steps
- Release hardening — documentation, CI invariant, and config cleanup
- Begin evaluation phase (≥3 months of paper trading data)
- Broker go/no-go decision based on evaluation results (see `docs/evaluation/BROKER_DECISION.md`)
