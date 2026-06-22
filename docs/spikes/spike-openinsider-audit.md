## Status: Historical (Closed)

# OpenInsider HTML Parsing Robustness Audit — Results

## Current CSS Selectors

| Selector | Use | Assumption |
|----------|-----|------------|
| `table.tinytable tbody tr` | Row fetching (primary) | Table has class `tinytable` with `<tbody>` wrapper |
| `table.tinytable tr` | Row fetching (fallback) | Same table, no `<tbody>` wrapper |
| `td` (nth child 0-11) | Cell extraction | At least 12 `<td>` per row |
| `_cell_text(cells, 0)` | Ticker text | First cell has ticker text directly (no `<a>` wrapper needed) |

## Column Mapping

**Actual implementation** in `domain/_normalize_helpers.py:_row_to_transaction()` (lines 90-118):

| Index | Field | Parsing |
|-------|-------|---------|
| 0 | ticker | `_cell_text(cells, 0).upper()` |
| 3 | owner | `_cell_text(cells, 3)` |
| 4 | title | `_cell_text(cells, 4)` |
| 5 | transaction_type | `_cell_text(cells, 5).title()` |
| 6 | transaction_date | `_parse_date(_cell_text(cells, 6))` |
| 7 | filing_date | `_parse_date(_cell_text(cells, 7))` |
| 9 | price | `_parse_number(_cell_text(cells, 9))` |
| 10 | quantity | `_parse_number(_cell_text(cells, 10))` |
| 11 | held | `_parse_number(_cell_text(cells, 11))` |

Note: The actual column indices differ significantly from the HTML structure assumed during spike analysis. The `css_first("a")` lookup was also unnecessary — the ticker text is directly in the cell. Parsing logic lives in `domain/_normalize_helpers.py` (not the connector), imported by `openinsider_connector.py`.

## Improvements Applied

1. **Added expected HTML structure documentation** as comment block in `openinsider_connector.py` (lines 25-42)
2. **Added warning when all rows are skipped** — detects silent parsing failures after HTML structure changes
3. **Added `skip_count` tracking** — distinguishes "no data" from "all rows failed to parse"

## Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Column order change | High | Parsing silently produces wrong values; no mitigation without schema validation |
| Date format change (OpenInsider uses `%Y-%m-%d` currently) | Medium | `_parse_date()` tries multiple formats; if all fail, field is `None` |
| Table class name change (`tinytable` → `screener-table`) | High | Returns empty list; warning logged but caller gets 0 results |
| Selectolax HTML spec compliance | Low | selectolax is lenient; real-world HTML variations handled well |

## Recommendation

For long-term robustness, consider adding a Pydantic model for the expected table row structure and validate parsed output against it. This would catch column-order changes immediately rather than silently producing wrong data.
