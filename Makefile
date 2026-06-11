.PHONY: check format type bootstrap golden bless-golden

check:
	uv run ruff check alpha_quant/

format:
	uv run ruff format alpha_quant/

type:
	uv run ty check alpha_quant/

bootstrap:
	uv run alpha-quant bootstrap

golden:
	uv run alpha-quant replay \
		--from-date 2024-01-01 \
		--to-date 2024-01-31 \
		--output fixtures/golden/golden_run.json

bless-golden: bootstrap golden
	@echo "Golden file updated: fixtures/golden/golden_run.json"
	@echo "Commit and push the new golden file."
