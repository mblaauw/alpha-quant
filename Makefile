.PHONY: check format format-check type type-all test test-unit test-integration test-parallel test-e2e lint qa clean schema coverage check-docs

check:
	uv run ruff check src/

format:
	uv run ruff format src/

format-check:
	uv run ruff format --check src/

type:
	uv run ty check src/

type-all:
	uv run ty check src/ tests/

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/ -q

test-integration:
	uv run pytest tests/integration/ -q

test-parallel:
	uv run pytest tests/ -q -n auto

test-e2e:
	uv run pytest tests/ -v --timeout=30

qa:
	@for script in tests/qa/*.sh; do \
		echo "Running $$script..."; \
		bash "$$script" || echo "  ⚠️  $$script failed (non-zero exit)"; \
	done

golden:
	uv run pytest tests/test_golden_replay.py -q

bless-golden:
	rm -f fixtures/golden/run.hash
	uv run pytest tests/test_golden_replay.py -q 2>&1 || true
	@echo "Golden hash updated in fixtures/golden/run.hash"

lint: check format type
	@echo "All linting passed."

bootstrap:
	PYTHONHASHSEED=0 uv run python scripts/generate_fixtures.py
	@echo "Fixtures generated in fixtures/v1/"

schema:
	uv run python -c "from alpha_quant.application.config import AppConfig; import json; json.dump(AppConfig.model_json_schema(), open('docs/config-schema.json','w'), indent=2)"
	@echo "Generated docs/config-schema.json"

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

coverage:
	uv run pytest --cov=src --cov-report=html --cov-report=term

check-docs:
	@echo "Documentation check skipped (deprecated)."
