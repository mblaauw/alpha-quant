# ADR-0042: Static SPA and Same-Origin FastAPI BFF

## Status

Accepted

## Date

2026-06-26

## Context

Alpha-Quant requires an operational console for monitoring and controlling the decision pipeline. The previous approach used Streamlit (ADR-0014), then a Jinja2/HTMX hybrid. Both approaches had drawbacks: Streamlit required a separate runtime and process, while Jinja2 templates coupled presentation to server-side rendering.

The desired frontend must be:

- easy to inspect, deploy, and version from the same Python container
- fast and responsive without server round-trips for every interaction
- maintainable without a JavaScript build toolchain or Node.js dependency
- safe for a write-capable operational console (no service worker, no offline cache)

## Options Considered

1. **React/Next.js SPA** — full-featured but adds Node.js build step, npm dependencies, and complexity
2. **Streamlit** — previously adopted (ADR-0014), but requires its own server and process model, and is read-only by design
3. **Jinja2 server-rendered pages** — couples UI to server, every interaction requires full page or fragment reloads
4. **Vanilla JavaScript SPA served by FastAPI** — no build step, same-origin, same container, no Node/npm

## Decision

Adopt a static, same-origin, vanilla JavaScript SPA served by FastAPI.

The frontend uses:

- HTML for structure
- CSS custom properties for theming (`--aq-*` tokens)
- Vanilla ES modules (no bundler)
- Fetch API for all data access
- Native `dialog` elements for modals
- LocalStorage only for visual preferences (theme, sidebar state, last route)

No frontend frameworks, build tools, or package managers are used. The browser communicates only with Alpha-Quant's same-origin read and command APIs.

## Consequences

**Positive:**

- Zero build step — static files are served directly from the FastAPI process
- Same container serves both API and frontend — no separate deployment
- Easy to inspect, debug, and version alongside the Python codebase
- No npm vulnerabilities, no lockfile conflicts, no dependency drift
- CSS custom properties enable light/dark theme without JavaScript framework

**Negative:**

- No component hot-reloading during development (require full refresh)
- No TypeScript — type safety must be ensured through the API contract
- No SSR or SEO — the SPA is an authenticated operational console, not a public site

## Related

- Supersedes ADR-0014 (Streamlit Dashboard)
