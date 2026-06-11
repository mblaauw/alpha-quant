# OpenInsider HTML Parsing Robustness Audit — Results

## Current CSS Selectors

| Selector | Use | Assumption |
|----------|-----|------------|
| `table.tinytable tbody tr` | Row fetching (primary) | Table has class `tinytable` with `<tbody>` wrapper |
| `table.tinytable tr` | Row fetching (fallback) | Same table, no `<tbody>` wrapper |
| `td` (nth child 0-9) | Cell extraction | At least 10 `<td>` per row |
| `td:nth-child(1) a` | Ticker hyperlink | First cell has an `<a>` tag with ticker text |

## Column Mapping

| Index | Field | Parsing |
|-------|-------|---------|
| 0 | ticker | `cells[0].css_first("a").text(strip=True).upper()` |
| 1 | owner | `cells[1].text(strip=True)` |
| 2 | title | `cells[2].text(strip=True)` |
| 3 | relationship | `cells[3].text(strip=True).lower()` |
| 4 | transaction_type | `cells[4].text(strip=True).lower()` |
| 5 | price | `_parse_number(cells[5].text(strip=True))` |
| 6 | quantity | `_parse_number(cells[6].text(strip=True))` |
| 7 | held | Not used directly |
| 8 | date | `_parse_date(cells[8].text(strip=True))` |

## Improvements Applied

1. **Added expected HTML structure documentation** as comment block in `openinsider_connector.py` (lines 21-36)
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
