# Python 3.14 Feature Opportunity Audit — Results

## Summary

| Category | Changes Applied | Files Affected |
|----------|----------------|----------------|
| `@override` decorator | 48 methods decorated | 16 files |
| `match`/`case` string dispatch | 1 function rewritten | `app/store.py:80` |
| `Self` return type | 1 annotation updated | `domain/models.py:148` |
| Generic[T] → `[T]` syntax | 0 (no generics exist) | — |

## Detail

### 1. @override Decorator (+48 sites)

Every method that overrides a port interface ABC method now has `@override` from `typing`. This provides compile-time safety: if the parent port signature changes, `ty` will flag any override that doesn't match.

Files updated:
- `adapters/fake/` — virtual_clock, fake_event_sink, canned_llm, fixture_market_data, fixture_fundamentals, fixture_insider_feed, fixture_sentiment_feed, fixture_store
- `adapters/real/` — clock, event_sink, eodhd_connector, alpaca_connector, openinsider_connector, reddit_sentiment_connector, sec_connector
- `app/` — store.py (CanonicalStore)

### 2. match/case String Dispatch (+1)

`_model_to_pylist()` in `app/store.py:80` — the 4-way `if` chain on `model_name` was replaced with `match/case`. This improves readability and makes exhaustiveness checking possible if the match becomes a function in the future.

### 3. Self Return Type (+1)

`Order._validate_fill_quantity()` in `domain/models.py:148` — changed return annotation from `-> Order` to `-> Self`. This is technically correct: the method returns `self`, not necessarily an `Order` instance.

### 4. Generic[T] → PEP 695 Syntax

No generics exist in the codebase. If introduced later, prefer `class Foo[T]:` (Python 3.12+) over `class Foo(Generic[T]):`.

## Verification

- `ruff check` — All checks passed
- `ruff format` — All files formatted
- `ty check` — All checks passed
