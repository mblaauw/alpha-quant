FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.6.10 /uv /bin/uv
ENV UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY alembic.ini .
COPY config.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-slim AS runtime
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app && \
    chown -R app:app /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/config.toml /app/config.toml
COPY fixtures/ fixtures/
RUN chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
ENTRYPOINT ["alpha-quant"]
