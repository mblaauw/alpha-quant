.PHONY: check format type test test-unit test-integration test-parallel test-dashboard test-e2e test-chaos lint qa bootstrap golden bless-golden clean schema coverage check-docs

check:
	uv run ruff check alpha_quant/

format:
	uv run ruff format alpha_quant/

type:
	uv run ty check alpha_quant/ tests/

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/ -q

test-integration:
	uv run pytest tests/integration/ -q

test-parallel:
	uv run pytest tests/ -q -n auto

test-dashboard:
	uv run pytest tests/unit/test_dashboard.py tests/integration/test_dashboard_e2e.py -v

test-e2e:
	uv run pytest tests/integration/ -v

test-chaos:
	uv run pytest tests/chaos/ -q --timeout=30 -m chaos

qa:
	@for script in tests/qa/*.sh; do \
		echo "Running $$script..."; \
		bash "$$script" || echo "  ⚠️  $$script failed (non-zero exit)"; \
	done

lint: check format type
	@echo "All linting passed."

bootstrap:
	PYTHONHASHSEED=0 uv run alpha-quant bootstrap

golden:
	PYTHONHASHSEED=0 uv run alpha-quant replay \
		--fixture fixtures/v1 \
		--from-date 2024-01-01 \
		--to-date 2024-01-31 \
		--output fixtures/golden/golden_run.json

schema:
	uv run python -c "from alpha_quant.app.config import AppConfig; import json; json.dump(AppConfig.model_json_schema(), open('config-schema.json','w'), indent=2)"
	@echo "Generated config-schema.json"

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

coverage:
	uv run pytest --cov=alpha_quant --cov-report=html --cov-report=term

check-docs:
	@echo "Checking for stale documentation patterns..."
	@failed=0; \
	check() { label=$$1; shift; if grep -rni "$$@" 2>/dev/null | grep -qviE 'remove|removed|removal|changed|chang|SqliteEventSink|ADR-0027|0007-use-sqlite|0008-use-custom|0010-use-custom|0014-use-streamlit|0017-use-golden'; then echo "  ❌ $$label"; grep -rni "$$@" 2>/dev/null | grep -viE 'remove|removed|removal|changed|chang|SqliteEventSink|ADR-0027|0007-use-sqlite|0008-use-custom|0010-use-custom|0014-use-streamlit|0017-use-golden' | sed 's/^/      /'; failed=1; else echo "  ✅ $$label"; fi; }; \
	check 'pytest + hypothesis' 'pytest + hypothesis' docs/ README.md DESIGN.md --include='*.md'; \
	check 'stale SQLite references in docs' 'SQLite scanner\|SQLite state\|SQLite State Store' docs/ README.md --include='*.md'; \
	check 'stale SQLite references in tests/' '"SQLite\|Sqlite' tests/ --include='*.py'; \
	check '50-day tail as active feature' '50-day raw tail\|50-day tail pattern\|50-day tail prune\|raw bars are pruned\|Pruned to 50-day' docs/ DESIGN.md --include='*.md'; \
	check 'stale broker wording' 'designed but unimplemented' docs/ DESIGN.md --include='*.md'; \
	check 'overstrong clock claims' 'fully wired -- every\|fully wired — every' docs/ --include='*.md'; \
	check 'stale CLI count' 'CLI with 9 subcommands' docs/ --include='*.md'; \
	check 'stale CLI count in ADR-0004' '9 subcommands' docs/adr/0004-use-argparse-for-cli.md --include='*.md'; \
	check 'stale golden replay duration' '6 fixture-months' docs/ README.md DESIGN.md --include='*.md'; \
	check 'stale fixture version example' 'fx-2026' docs/ DESIGN.md --include='*.md'; \
	check 'stale replay flags' '--from 20.*--to 20\|--from 20.*--to ' docs/ DESIGN.md --include='*.md'; \
	check 'lxml fallback claim' 'lxml fallback' docs/ DESIGN.md --include='*.md'; \
	check 'stale RSI range claim' 'RSI 45.70' docs/ DESIGN.md --include='*.md'; \
	if [ $$failed -eq 0 ]; then echo "Documentation check passed."; else echo "Documentation check FAILED."; false; fi

bless-golden: bootstrap golden
	@echo "Golden file updated: fixtures/golden/golden_run.json"
	@echo "Commit and push the new golden file."
