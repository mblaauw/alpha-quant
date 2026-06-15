.PHONY: check format type test test-dashboard test-e2e bootstrap golden bless-golden lint

check:
	uv run ruff check alpha_quant/

format:
	uv run ruff format alpha_quant/

type:
	uv run ty check alpha_quant/

test:
	uv run pytest

test-dashboard:
	uv run pytest tests/unit/test_dashboard.py tests/integration/test_dashboard_e2e.py -v

test-e2e:
	uv run pytest tests/integration/ -v

lint: check format type
	@echo "All linting passed."

bootstrap:
	export PYTHONHASHSEED=0
	uv run alpha-quant bootstrap

golden:
	export PYTHONHASHSEED=0
	uv run alpha-quant replay \
		--fixture fixtures/v1 \
		--from-date 2024-01-01 \
		--to-date 2024-01-31 \
		--output fixtures/golden/golden_run.json

bless-golden: bootstrap golden
	@echo "Golden file updated: fixtures/golden/golden_run.json"
	@echo "Commit and push the new golden file."
