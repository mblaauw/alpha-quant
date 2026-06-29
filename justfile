# ── Lifecycle ────────────────────────────────────────────────────────────────

# Start the full stack (PostgreSQL, migrate, API, worker)
up *flags:
    docker compose up -d {{ flags }}

# Stop all services, preserve data
down:
    docker compose down

# Show logs for all services
logs *service:
    docker compose logs -f {{ service }}

# Show service status
status:
    docker compose ps

# Rebuild the application image (no cache)
rebuild:
    docker compose build --no-cache api

# Build the application image
build:
    docker compose build api

# ── Database ─────────────────────────────────────────────────────────────────

# Run pending Alembic migrations
migrate:
    docker compose run --rm migrate

# Check pending migrations without applying (dry-run)
migrate-check:
    docker compose run --rm --entrypoint alpha-quant api db-migrate-check

# Open psql shell to the database
db-shell:
    docker compose exec postgres psql -U alpha_quant -d alpha_quant

# Check database health
db-status:
    docker compose exec postgres pg_isready -U alpha_quant -d alpha_quant

# Backup PostgreSQL to a file
db-backup file="backup.sql":
    docker compose exec -T postgres pg_dump -U alpha_quant -d alpha_quant > {{ file }}

# Restore PostgreSQL from a file
db-restore file:
    docker compose exec -T postgres psql -U alpha_quant -d alpha_quant < {{ file }}

# ── Testing / QA ─────────────────────────────────────────────────────────────

# Run tests
test *args:
    docker compose run --rm --entrypoint pytest api {{ args }}

# Run all checks (lint, type) using host tooling
check:
    uv run ruff check src/ && uv run ty check src/

# ── Destructive Reset (requires explicit confirmation) ───────────────────────

# Remove PostgreSQL data volume
reset-db confirm="":
    @if [ "{{ confirm }}" != "DROP_ALPHA_QUANT_DB" ]; then \
        echo "ERROR: Provide confirm=DROP_ALPHA_QUANT_DB to proceed."; \
        echo "This will IRREVERSIBLY DELETE all PostgreSQL data."; \
        exit 1; \
    fi
    echo "WARNING: Removing PostgreSQL volume — all data will be lost!"
    docker compose stop api worker migrate
    docker volume rm alpha_quant_pgdata
    echo "PostgreSQL volume removed. Run 'just up' to recreate."

# Remove ALL data (PostgreSQL)
reset-all confirm="":
    @if [ "{{ confirm }}" != "DROP_ALPHA_QUANT_ALL_STATE" ]; then \
        echo "ERROR: Provide confirm=DROP_ALPHA_QUANT_ALL_STATE to proceed."; \
        echo "This will IRREVERSIBLY DELETE all data."; \
        exit 1; \
    fi
    echo "WARNING: Removing ALL data volumes — every record will be lost!"
    docker compose down
    docker volume rm alpha_quant_pgdata
    echo "All volumes removed. Run 'just up' to recreate."
