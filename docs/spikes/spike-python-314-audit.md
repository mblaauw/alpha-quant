# Python 3.14 Feature Opportunity Audit — Results

## Summary

| Category | Changes Applied | Files Affected |
|----------|----------------|----------------|
| `@override` decorator | 132 methods decorated | 28 files |
| `match`/`case` string dispatch | 0 (not applied — no suitable dispatch chains exist) | — |
| `Self` return type | 4 annotations updated | `domain/models.py` (4 methods) |
| Generic[T] → `[T]` syntax | 0 (no generics exist) | — |

## Detail

### 1. @override Decorator (+132 sites)

Every method that overrides a port interface ABC method now has `@override` from `typing`. This provides compile-time safety: if the parent port signature changes, `ty` will flag any override that doesn't match.

Files updated:
- `adapters/fake/` — virtual_clock, fake_event_sink, canned_llm, fixture_market_data, fixture_fundamentals, fixture_insider_feed, fixture_sentiment_feed, fixture_store
- `adapters/real/` — clock, event_sink, tiingo_connector, eodhd_connector, sec_fundamentals_connector, alpaca_connector, openinsider_connector, reddit_sentiment_connector, sec_connector
- `app/` — store modules (CanonicalStore mixins)

### 2. match/case String Dispatch

Not applied. The codebase was audited for dispatch chains suitable for `match/case` conversion, but the existing `if` chains in `app/store/` modules and elsewhere lacked the clear pattern structure where `match/case` provides a readability advantage.

### 3. Self Return Type (+4)

Four methods in `domain/models.py` use `Self` return type:
- `DailyBar._validate_bar_relationships()` (line 26)
- `Quote._validate_spread()` (line 54)
- `Decision._validate_gate_consistency()` (line 170)
- `Order._validate_fill_quantity()` (line 192)

These change return annotations from `-> ModelName` to `-> Self`, which is technically correct since they return `self`.

### 4. Generic[T] → PEP 695 Syntax

No generics exist in the codebase. If introduced later, prefer `class Foo[T]:` (Python 3.12+) over `class Foo(Generic[T]):`.

## Verification

- `ruff check` — All checks passed
- `ruff format` — All files formatted
- `ty check` — All checks passed
