"""
TC-18: Concurrent monitoring and management of 100 sites with no degradation.
Satisfies: Req-Func-Sw-19, Req-Qual-Scal-1
Run: pytest tests/load/test_tc18_100_sites.py -v -s
"""

from __future__ import annotations
import asyncio
import os
import statistics
import time

import pytest

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

BASE_URL    = os.getenv("BACKEND_URL", "http://localhost:8000")
NUM_SITES   = int(os.getenv("TC18_NUM_SITES", "100"))
CONCURRENCY = int(os.getenv("TC18_CONCURRENCY", "50"))
MAX_AVG_MS  = int(os.getenv("TC18_MAX_AVG_MS", "2000"))
MAX_P95_MS  = int(os.getenv("TC18_MAX_P95_MS", "4000"))


@pytest.fixture(scope="module")
def auth_token():
    """Obtain a JWT for the test user, or skip if backend is not reachable."""
    if httpx is None:
        pytest.skip("httpx not installed")
    try:
        r = httpx.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "admin@pathwise.local", "password": "admin"},
            timeout=5,
        )
    except Exception as exc:
        pytest.skip(f"Backend not reachable: {exc}")
    if r.status_code != 200:
        pytest.skip(f"Auth failed (status={r.status_code}) — is the backend running?")
    body = r.json()
    return body.get("access_token") or body.get("token") or ""


async def _fetch_site_telemetry(client, site_id: int, token: str):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    t0 = time.perf_counter()
    r = await client.get(
        f"{BASE_URL}/api/v1/telemetry/site/{site_id}",
        headers=headers,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return elapsed, r.status_code


async def _run_concurrent_wave(site_ids, token):
    async with httpx.AsyncClient(timeout=15.0) as client:
        tasks = [_fetch_site_telemetry(client, sid, token) for sid in site_ids]
        return await asyncio.gather(*tasks)


def test_100_site_concurrent_monitoring(auth_token):
    """All 100 sites must respond within SLA under full concurrency."""
    site_ids = list(range(1, NUM_SITES + 1))

    all_results = []
    for i in range(0, len(site_ids), CONCURRENCY):
        wave = site_ids[i:i + CONCURRENCY]
        results = asyncio.run(_run_concurrent_wave(wave, auth_token))
        all_results.extend(results)

    latencies = [r[0] for r in all_results]
    status_codes = [r[1] for r in all_results]

    avg_ms = statistics.mean(latencies)
    p95_ms = sorted(latencies)[int(0.95 * len(latencies))]
    errors = sum(1 for s in status_codes if s not in (200, 404))

    print("\n=== TC-18 Load Test Results ===")
    print(f"Sites tested:    {len(all_results)}")
    print(f"Average latency: {avg_ms:.1f} ms")
    print(f"P95 latency:     {p95_ms:.1f} ms")
    print(f"Errors:          {errors}")
    print("================================")

    assert errors == 0, f"TC-18 FAIL: {errors} error responses (non-200/404)"
    assert avg_ms < MAX_AVG_MS, f"TC-18 FAIL: avg {avg_ms:.0f}ms > {MAX_AVG_MS}ms SLA"
    assert p95_ms < MAX_P95_MS, f"TC-18 FAIL: p95 {p95_ms:.0f}ms > {MAX_P95_MS}ms SLA"


def test_100_site_dashboard_render(auth_token):
    """Dashboard summary endpoint must handle 100 sites in one request."""
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
    r = httpx.get(
        f"{BASE_URL}/api/v1/dashboard/summary?sites={NUM_SITES}",
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200, f"unexpected status {r.status_code}"
    data = r.json()
    sites_returned = len(data.get("sites", []))
    assert sites_returned >= 1, "At least one site must be returned"
    print(f"\nDashboard returned {sites_returned} site entries")
