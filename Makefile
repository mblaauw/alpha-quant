.PHONY: check format type test test-dashboard test-e2e bootstrap golden bless-golden lint check-docs

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

check-docs:
	@echo "Checking for stale documentation patterns..."
	@! grep -rn 'pytest + hypothesis' docs/ --include='*.md' && echo "  ✅ No 'pytest + hypothesis' in docs" || (echo "  ❌ Found 'pytest + hypothesis' in docs (should be just 'pytest')" && false)
	@! grep -rn 'SQLite scanner\|SQLite state\|SqliteEventSink' docs/ --include='*.md' && echo "  ✅ No stale SQLite references in docs" || (echo "  ❌ Found stale SQLite references in docs" && false)
	@! grep -rn '"SQLite\|Sqlite' tests/ --include='*.py' | grep -v '# noqa\|# fmt: skip\|\.sqlite\|sqlite3' && echo "  ✅ No stale SQLite references in tests/" || (echo "  ❌ Found stale SQLite references in tests/" && false)
	@echo "Documentation check passed."

bless-golden: bootstrap golden
	@echo "Golden file updated: fixtures/golden/golden_run.json"
	@echo "Commit and push the new golden file."
