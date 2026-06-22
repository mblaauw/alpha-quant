## Status: Historical (Closed)

# Secret Handling and Leakage Audit — Results

## Findings

### ✅ EODHDConfig.api_key — SecretStr
Type: `pydantic.SecretStr` — correctly redacted by `model_dump(mode="json")` to `'**********'`. No change needed.

### ✅ AlpacaConfig.api_key / .secret_key — SecretStr
Both typed as `pydantic.SecretStr` — correctly redacted. No change needed.

### ✅ redact_config() — model_dump
Uses `config.model_dump(mode="json")` which automatically redacts all `SecretStr` fields. No change needed.

### ❌ BaseConnector.fetch() URL logging — LEAK (FIXED)
**Critical**: `EODHDConnector._params()` adds `api_token` as a URL query parameter. The full URL (including `api_token=SECRET`) was logged at debug level by `fetch()`. 

**Fix applied**: `fetch()` now strips sensitive query parameter keys (`api_token`, `apikey`, `api_key`, `secret`, `token`, `key`) before logging, replacing their values with `"***"`. The URL is also truncated to its path portion.

### ✅ alpaca-py SDK
Alpaca keys are passed via HTTP Basic Auth (httpx `auth` parameter) — not in the URL or query params. The SDK's `StockHistoricalDataClient` accepts plain strings (standard practice). No leak path.

### ✅ Vault storage
Raw API response bytes are stored — API keys are in the request URL, not the response. No leak.

### ✅ Vault manifest
The vault manifest records `source`, `endpoint`, `params` — these are metadata, not credentials.

## Summary

| Item | Status | Action |
|------|--------|--------|
| SecretStr config fields | ✅ Redacted | None |
| redact_config() output | ✅ Clean | None |
| fetch() URL logging | ✅ FIXED | Sanitized sensitive params |
| EODHD api_token exposure | ✅ FIXED | Sanitized in log output |
| Alpaca auth logging | ✅ Safe | Via httpx auth header, not URL |
| Vault content | ✅ Safe | Response data only |
| Exception tracebacks | 👁️ Not verified | Requires manual review |

## Recommendation

Add a pytest unit test that verifies `EODHDConfig.api_key.get_secret_value()` is not present in any logged output when calling `EODHDConnector.fetch()` — but since connectors make real HTTP calls, this requires fixture-based testing.
