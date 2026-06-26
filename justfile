# ── Lifecycle ────────────────────────────────────────────────────────────────

# Start the full stack (PostgreSQL, artifacts, migrate, API, worker)
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

# Build the application image
build:
    docker compose build api

# ── Database ─────────────────────────────────────────────────────────────────

# Run pending Alembic migrations
migrate:
    docker compose run --rm migrate

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

# ── Artifacts ────────────────────────────────────────────────────────────────

# List artifacts in the bucket
artifacts-list:
    docker compose run --rm --entrypoint mc rustfs/rustfs:latest \
        --config-dir /tmp/mc alias set aq http://artifacts:9000 rustfsadmin rustfsadmin && \
        docker compose run --rm --entrypoint mc rustfs/rustfs:latest \
        --config-dir /tmp/mc ls aq/alpha-quant-artifacts

# ── Testing ──────────────────────────────────────────────────────────────────

# Run tests
test:
    docker compose run --rm --entrypoint pytest api

# Run dashboard API tests
test-api:
    docker compose run --rm --entrypoint pytest api tests/unit/test_dashboard_api.py

# Run end-to-end tests
test-e2e:
    docker compose run --rm --entrypoint pytest api tests/integration/

# Run all checks (lint, type, test)
check:
    docker compose run --rm --entrypoint /bin/sh api -c "ruff check && ty check"

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

# Remove artifact data volume
reset-artifacts confirm="":
    @if [ "{{ confirm }}" != "DROP_ALPHA_QUANT_ARTIFACTS" ]; then \
        echo "ERROR: Provide confirm=DROP_ALPHA_QUANT_ARTIFACTS to proceed."; \
        echo "This will IRREVERSIBLY DELETE all artifact data."; \
        exit 1; \
    fi
    echo "WARNING: Removing artifacts volume — all data will be lost!"
    docker compose stop api worker
    docker volume rm alpha_quant_artifacts
    echo "Artifacts volume removed. Run 'just up' to recreate."

# Remove ALL data (PostgreSQL + artifacts)
reset-all confirm="":
    @if [ "{{ confirm }}" != "DROP_ALPHA_QUANT_ALL_STATE" ]; then \
        echo "ERROR: Provide confirm=DROP_ALPHA_QUANT_ALL_STATE to proceed."; \
        echo "This will IRREVERSIBLY DELETE all data."; \
        exit 1; \
    fi
    echo "WARNING: Removing ALL data volumes — every record will be lost!"
    docker compose down
    docker volume rm alpha_quant_pgdata alpha_quant_artifacts
    echo "All volumes removed. Run 'just up' to recreate."
