# Beta UAT Sign-Off — v0.2.0-beta1

**Release Tag**: v0.2.0-beta1
**Test Date**: 2026-06-15
**Tester(s)**: Automated (opencode)
**Git Commit**: `548db5c`
**Environment**: macOS 15 (arm64) / Python 3.14 / uv

## Results

| # | Title | Status | Evidence | Notes |
|---|-------|--------|----------|-------|
| QA-1 | Clean install and first-run user journey | ✅ | [#348](https://github.com/mblaauw/alpha-quant/issues/348) | `uv sync --frozen --extra dev` succeeds; `make bootstrap` generates fixtures |
| QA-2 | Fixture-mode end-user CLI smoke test | ✅ | [#349](https://github.com/mblaauw/alpha-quant/issues/349) | All 12 CLI commands work; `run --mode fixture` produces decisions |
| QA-3 | Live ingest dry-run and degradation acceptance | ✅ | [#350](https://github.com/mblaauw/alpha-quant/issues/350) | Source degradation fallbacks verified |
| QA-4 | Dashboard user acceptance smoke test | ✅ | [#351](https://github.com/mblaauw/alpha-quant/issues/351) | 6 tabs render; empty data/ handled gracefully; beta warning banner present; no state mutation |
| QA-5 | State continuity across repeated daily runs | ✅ | [#352](https://github.com/mblaauw/alpha-quant/issues/352) | 2 sequential fixture runs; positions persist; I1 invariant holds; equity curve tracked |
| QA-6 | Risk, halt, and safety UAT scenarios | ✅ | [#353](https://github.com/mblaauw/alpha-quant/issues/353) | All 7 risk mechanisms verified; halt/resume works; 4 missing event types emitted now |
| QA-7 | Determinism and release reproducibility | ✅ | [#354](https://github.com/mblaauw/alpha-quant/issues/354) | 3 consecutive bootstrap+golden runs produce identical SHA-256 (`8b85231f5e619754`) |
| QA-8 | Docs and release metadata sanity check | ✅ | [#355](https://github.com/mblaauw/alpha-quant/issues/355) | README test count fixed (429); CLI table updated (12 commands); version bumped to 0.2.0; stale ROADMAP refs fixed |
| QA-9 | Backtest, paper, replay fill-model parity | ✅ | [#356](https://github.com/mblaauw/alpha-quant/issues/356) | 2 I8 violations fixed: pipeline entry now uses `fill_entry_order`; replay partial take now uses `fill_partial_take` |

## Test Output Summary

```
$ make check     → All checks passed
$ make format    → 95 files already formatted
$ make type      → All checks passed
$ make test      → 429 passed in 15.47s
$ make golden    → sha256=8b85231f5e619754 (deterministic across 3 runs)
```

## Issues Fixed During QA

| Issue | Bug | Fix |
|-------|-----|-----|
| [#354](https://github.com/mblaauw/alpha-quant/issues/354) | `created_at` timestamp in fixture manifest broke determinism | Removed `datetime.now(UTC)` from `freeze_bundle()` |
| [#352](https://github.com/mblaauw/alpha-quant/issues/352) | Fixture mode couldn't load bars (store vs market data) | Added `market_data` fallback to `pipeline.run()` |
| [#352](https://github.com/mblaauw/alpha-quant/issues/352) | First pipeline run never saved equity curve | Always save portfolio snapshot, not just when `prev_snap` exists |
| [#352](https://github.com/mblaauw/alpha-quant/issues/352) | Fixture version mismatch (config vs bootstrap) | Changed config default from `fx-2026-06-v1` to `v1` |
| [#353](https://github.com/mblaauw/alpha-quant/issues/353) | 4 risk event types never emitted by pipeline.py | Added `PartialTaken`, `FillBooked`, `TimeStopTriggered`, `DrawdownLadderTripped` |
| [#353](https://github.com/mblaauw/alpha-quant/issues/353) | Raw `RiskAction` objects leaked into events | Replaced with proper domain events |
| [#356](https://github.com/mblaauw/alpha-quant/issues/356) | pipeline.py entries bypassed fill model (I8) | `fill_entry_order` now used for all main book entries |
| [#356](https://github.com/mblaauw/alpha-quant/issues/356) | replay.py partial takes bypassed fill model (I8) | `fill_partial_take` now used instead of inline price calc |

## Go / No-Go

- **Blocking failures**: 0
- **Non-blocking issues**: 0
- **Items remaining**: 0
- **Decision**: ✅ **GO**
- **PO Signature**: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ (auto-generated)
