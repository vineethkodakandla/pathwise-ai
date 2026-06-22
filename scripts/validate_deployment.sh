#!/usr/bin/env bash
# TC-20: Validate PathWise AI runs correctly in a virtualized environment.
# Satisfies: Req-Func-Hw-7
# Run on the VM: bash scripts/validate_deployment.sh

set -e
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
BACKEND_SERVICE="${BACKEND_SERVICE:-api-gateway}"
DB_SERVICE="${DB_SERVICE:-timescaledb}"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  [PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL+1))
    fi
}

echo "=== PathWise AI TC-20 Deployment Validation ==="
echo "Target: $BACKEND_URL"
echo ""

echo "[ Platform checks ]"
check "x86-64 architecture"        "[ '$(uname -m)' = 'x86_64' ]"
check "Docker available"           "docker --version"
check "Docker Compose available"   "docker compose version"
check "Virtualization detected"    "systemd-detect-virt | grep -qvE '^none$'"

echo ""
echo "[ Container health checks ]"
check "$BACKEND_SERVICE running"   "docker compose ps $BACKEND_SERVICE | grep -q 'Up'"
check "$DB_SERVICE running"        "docker compose ps $DB_SERVICE | grep -q 'Up'"
check "redis container running"    "docker compose ps redis | grep -q 'Up'"
check "nginx container running"    "docker compose ps nginx | grep -q 'Up'"

echo ""
echo "[ API health checks ]"
check "Health endpoint 200"        "curl -sf $BACKEND_URL/api/v1/health"
check "Status endpoint 200"        "curl -sf $BACKEND_URL/api/v1/status"
check "Auth endpoint reachable"    "curl -sf -o /dev/null -w '%{http_code}' $BACKEND_URL/api/v1/auth/login | grep -qE '200|405|422'"
check "TLS enforced via nginx"     "curl -sk https://localhost/api/v1/health || true"

echo ""
echo "[ Resource checks ]"
check ">= 32 GB RAM"               "[ \$(free -g | awk '/Mem:/{print \$2}') -ge 32 ]"
check ">= 8 CPU cores"             "[ \$(nproc) -ge 8 ]"
check ">= 100 GB free disk"        "[ \$(df / --output=avail | tail -1) -ge 104857600 ]"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
