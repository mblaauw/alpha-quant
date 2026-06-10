# ADR-0011: Use Direct httpx (No SDK) for LLM Integration

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant's narration layer sends structured data (NarrationContext) to an LLM and receives prose. The system must support both OpenAI and OpenRouter via a single code path. The LLM is an explainer/educator only — never in the decision path (I3).

DESIGN.md §3.8 specifies: "httpx against OpenAI-compatible API — one adapter: OpenAI + OpenRouter."

## Decision Drivers

- Single code path for OpenAI and OpenRouter (both expose the same API format)
- No SDK dependency lock-in
- The LLM interface is simple: one POST request with a system prompt + user message
- The narration layer is not a core differentiator — simplicity over features
- Timeout and retry control must be explicit (LLM API can be slow or unavailable)

## Considered Options

- **Option A: Direct httpx against OpenAI-compatible API** — POST to `/v1/chat/completions` with JSON body, parse JSON response
- **Option B: OpenAI Python SDK** — Official SDK, handles retries and streaming, but ties to OpenAI's library; OpenRouter requires a different base URL config
- **Option C: LangChain** — Full LLM framework, overkill for a single API call pattern; heavy dependency tree

## Decision Outcome

Chosen option: **Option A — Direct httpx against OpenAI-compatible API**.

Rationale:
1. Both OpenAI and OpenRouter expose the same API format (`/v1/chat/completions`, same request/response schema) — one httpx POST call works for both
2. The LLM interaction is trivial: build JSON body → POST → parse JSON → return `choices[0].message.content`
3. No SDK update surprises — breaking changes in the OpenAI SDK do not affect the system
4. httpx is already a core dependency (used by all data connectors)
5. tenacity (already a dependency) handles retry — no need for the SDK's built-in retry

### Positive Consequences

- LLM adapter is ~50 lines of code, no framework dependencies
- Provider switching is a config change (`provider = "openrouter"`, `base_url = "https://openrouter.ai/api/v1"`)
- Full control over timeout, retry, error handling
- No transitive dependencies from LLM SDKs

### Negative Consequences

- Must manually construct the API request (trivial for a single chat completion call)
- No streaming support (not needed — narration is ~1000 tokens, generated once per day)
- No built-in token counting (can be approximated or ignored for daily journals)

## References

- DESIGN.md §3.8 (Library decisions), §11 (Narration & education layer), §16 (Invariant I3)
- RAD §6.2 (Decision Engine Components — LLM Narrator)
- C4 Container diagram: `docs/architecture/views/container.png`
