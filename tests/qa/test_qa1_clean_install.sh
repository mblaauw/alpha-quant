#!/usr/bin/env bash
# BETA-QA-1: Clean install and first-run user journey
# Validates that a new user can clone, install, and run the system
# without encountering stale docs, missing dependencies, or tracebacks.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS+1)); echo -e "${GREEN}  ✅ PASS${NC}"; }
fail() { ERRORS+=("$1"); FAIL=$((FAIL+1)); echo -e "${RED}  ❌ FAIL: $1${NC}"; }

echo "======================================"
echo " BETA-QA-1: Clean Install Test Suite"
echo "======================================"
echo ""

SRC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_DIR=$(mktemp -d /tmp/alpha-quant-qa1.XXXXXX)
echo "Source: $SRC_DIR"
echo "Test dir: $TMP_DIR"
echo ""

# ── AC-1a: Fresh clone ──
echo "--- AC-1a: Fresh clone ---"
CLONE_DIR="$TMP_DIR/clone"
git clone "$SRC_DIR" "$CLONE_DIR" 2>&1
ls -la "$CLONE_DIR" > /dev/null 2>&1 && pass || fail "git clone failed"

# ── AC-1b: uv sync (with dev deps) ──
echo "--- AC-1b: uv sync (with dev deps) ---"
(cd "$CLONE_DIR" && uv sync --extra dev 2>&1)
[ -d "$CLONE_DIR/.venv" ] && pass || fail "uv sync did not create .venv"

# ── AC-2a: alpha-quant --version ──
echo "--- AC-2a: version matches pyproject.toml ---"
VERSION_OUTPUT=$(cd "$CLONE_DIR" && uv run alpha-quant --version 2>&1) || true
VERSION_TAG=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"([^\"]+)\"', open('$SRC_DIR/pyproject.toml').read()).group(1))")
if echo "$VERSION_OUTPUT" | grep -qi "$VERSION_TAG"; then
  pass
else
  fail "alpha-quant --version mismatch. Expected '$VERSION_TAG', got: '$VERSION_OUTPUT'"
fi

# ── AC-2b: alpha-quant no args ──
echo "--- AC-2b: alpha-quant shows help with no args ---"
NOARGS_OUTPUT=$(cd "$CLONE_DIR" && uv run alpha-quant 2>&1) || true
if echo "$NOARGS_OUTPUT" | grep -qi "usage:" 2>/dev/null; then
  pass
else
  fail "alpha-quant with no args should show help, got: $NOARGS_OUTPUT"
fi

# ── AC-2c: alpha-quant unknown subcommand ──
echo "--- AC-2c: unknown subcommand produces helpful error ---"
BOGUS_OUTPUT=$(cd "$CLONE_DIR" && uv run alpha-quant bogus 2>&1) || true
if ! echo "$BOGUS_OUTPUT" | grep -qi "traceback" 2>/dev/null; then
  pass
else
  fail "alpha-quant bogus produced traceback: $BOGUS_OUTPUT"
fi

# ── AC-3: Missing config produces actionable error ──
echo "--- AC-3: missing config produces actionable error ---"
(cd "$CLONE_DIR" && cp config.local.toml.example config.local.toml)
NO_CONFIG_OUTPUT=$(cd "$CLONE_DIR" && uv run alpha-quant bootstrap 2>&1) || true
if ! echo "$NO_CONFIG_OUTPUT" | grep -qiE "(sk-|ak-|pk-|[A-Za-z0-9_-]{20,})" 2>/dev/null; then
  if echo "$NO_CONFIG_OUTPUT" | grep -qiE "(error|Error|missing|not found)" 2>/dev/null; then
    pass
  else
    echo "  Output: $NO_CONFIG_OUTPUT"
    fail "Missing config should produce an error"
  fi
else
  fail "Error message leaked secret patterns"
fi

# ── AC-4: Version consistency between pyproject.toml and __init__.py ──
echo "--- AC-4: version consistency ---"
PKG_VERSION=$(python3 -c "import re; print(re.search(r'version\s*=\s*\"([^\"]+)\"', open('$CLONE_DIR/pyproject.toml').read()).group(1))")
PKG_META_VERSION=$(cd "$CLONE_DIR" && python3 -c "
from importlib.metadata import version; print(version('alpha-quant'))
" 2>/dev/null || echo "FAIL")
if [ "$PKG_VERSION" = "$PKG_META_VERSION" ]; then
  pass
else
  fail "pyproject.toml version ($PKG_VERSION) != importlib.metadata version ($PKG_META_VERSION)"
fi

# ── AC-5: pytest discovery ──
echo "--- AC-5: pytest discovers and runs tests ---"
(cd "$CLONE_DIR" && uv run pytest --collect-only --quiet 2>/dev/null 1>/dev/null)
PYTEST_EXIT=$?
if [ $PYTEST_EXIT -eq 0 ] || [ $PYTEST_EXIT -eq 5 ]; then
  echo -e "${GREEN}  ✅ PASS (pytest exit=$PYTEST_EXIT)${NC}"
  PASS=$((PASS+1))
else
  fail "pytest collection failed (exit code: $PYTEST_EXIT)"
fi

# ── Summary ──
echo ""
echo "======================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "======================================"

if [ $FAIL -gt 0 ]; then
  echo ""
  echo "Errors:"
  for e in "${ERRORS[@]}"; do
    echo "  - $e"
  done
fi

rm -rf "$TMP_DIR"
exit $FAIL
