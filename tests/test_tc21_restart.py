"""
TC-21: Auto-reconnect after service restart.
Run: pytest tests/test_tc21_restart.py -v -s
Requires Docker and docker-compose on PATH.
"""

import os
import subprocess
import time

import pytest

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_SERVICE = os.getenv("BACKEND_SERVICE", "api-gateway")
DB_SERVICE = os.getenv("DB_SERVICE", "timescaledb")


def _docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "version"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _wait_healthy(timeout: int = 60) -> bool:
    if httpx is None:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/api/v1/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


@pytest.mark.skipif(not _docker_available(),
                    reason="Docker is not available — TC-21 requires docker compose")
def test_backend_recovers_after_restart():
    """Backend must come back healthy within 60s after docker restart."""
    if not _wait_healthy(30):
        pytest.skip("Backend not healthy before test — start docker compose first")

    result = subprocess.run(
        ["docker", "compose", "restart", BACKEND_SERVICE],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"docker restart failed: {result.stderr}"
    print("\nBackend restarted — waiting for recovery...")

    recovered = _wait_healthy(60)
    assert recovered, "TC-21 FAIL: backend did not recover within 60s"
    print("TC-21 PASS: backend recovered after restart")


@pytest.mark.skipif(not _docker_available(),
                    reason="Docker is not available — TC-21 requires docker compose")
def test_timescaledb_reconnects_after_restart():
    """TimescaleDB must reconnect automatically after restart."""
    if not _wait_healthy(30):
        pytest.skip("Backend not healthy before test — start docker compose first")

    result = subprocess.run(
        ["docker", "compose", "restart", DB_SERVICE],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"docker restart failed: {result.stderr}"

    time.sleep(10)  # allow DB to come back
    recovered = _wait_healthy(60)
    assert recovered, "TC-21 FAIL: backend did not reconnect to DB within 60s"
    print("TC-21 PASS: DB reconnect confirmed")
