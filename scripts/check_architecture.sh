#!/usr/bin/env bash
set -euo pipefail

# CI architecture checks for Alpha-Quant
# Verifies no stale patterns, legacy code, or security violations.

echo "=== Architecture Checks ==="
fail=0

# 1. No Streamlit files
if [ -d ".streamlit" ] || [ -f "src/app/dashboard.py" ]; then
    echo "FAIL: Streamlit artifacts found"
    fail=1
fi

# 2. No file-based halts
if rg -q "data/\.HALT|os\.path\.exists.*HALT" src/ tests/ 2>/dev/null; then
    echo "FAIL: File-based halt references found"
    fail=1
fi

# 3. No automatic database destruction
if rg -q "create_all\(|DROP SCHEMA|TRUNCATE|DROP DATABASE" src/alpha_quant/application/ src/scripts/ 2>/dev/null; then
    echo "FAIL: Automatic schema destruction found"
    fail=1
fi

# 4. No browser-side Alpha-Lake secrets
if rg -q "fetch\(.*alpha-lake|ALPHA_LAKE_API_KEY" src/alpha_quant/transport/static/ 2>/dev/null; then
    echo "FAIL: Browser-side Alpha-Lake reference found"
    fail=1
fi

# 5. No direct PostgreSQL browser calls
if rg -q "postgres|psycopg|sqlalchemy" src/alpha_quant/transport/static/ 2>/dev/null; then
    echo "FAIL: Browser-side database reference found"
    fail=1
fi

# 6. No Jinja templates in transport
if [ -d "src/alpha_quant/transport/templates" ]; then
    echo "FAIL: Jinja templates found in transport"
    fail=1
fi

if [ "$fail" -eq 0 ]; then
    echo "PASS: All architecture checks passed"
else
    echo "FAIL: Architecture violations detected"
fi
exit $fail
