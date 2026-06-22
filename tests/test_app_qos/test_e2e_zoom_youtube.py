"""
End-to-end test: Zoom HIGH + YouTube LOW priority switch.

Requires a running backend at http://localhost:8000.
Skipped automatically if the server is not reachable.
"""

import os
import pytest

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

BASE = os.environ.get("PATHWISE_API_URL", "http://localhost:8000")

pytestmark = pytest.mark.skipif(not _HAS_HTTPX, reason="httpx not installed")


def _server_reachable() -> bool:
    try:
        r = httpx.get(f"{BASE}/api/v1/status", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def auth_headers():
    if not _server_reachable():
        pytest.skip("Backend not reachable")
    # Use existing in-memory admin account
    r = httpx.post(f"{BASE}/api/v1/auth/login",
                   json={"email": "admin@pathwise.local", "password": "admin"}, timeout=5)
    if r.status_code != 200:
        pytest.skip(f"Cannot authenticate: {r.status_code}")
    token = r.json().get("access_token") or r.json().get("token")
    if not token:
        pytest.skip("No token in login response")
    return {"Authorization": f"Bearer {token}"}


class TestE2EZoomYouTube:
    def test_apply_zoom_high_youtube_low(self, auth_headers):
        """Core demo: Zoom HIGH → 60 Mbps Excellent, YouTube LOW → 300 Kbps 240p."""
        r = httpx.post(
            f"{BASE}/api/v1/apps/priorities",
            json={"priorities": [
                {"app_id": "zoom", "priority": "HIGH"},
                {"app_id": "youtube", "priority": "LOW"},
            ]},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        apps = {a["app_id"]: a for a in data.get("apps", [])}

        # Zoom gets high bandwidth
        assert apps["zoom"]["ceil_kbps"] >= 50000, \
            f"Zoom only got {apps['zoom']['ceil_kbps']} kbps"
        assert apps["zoom"]["estimated_quality"] in ("Excellent", "Good")

        # YouTube is throttled hard
        assert apps["youtube"]["ceil_kbps"] <= 5000, \
            f"YouTube got {apps['youtube']['ceil_kbps']} kbps (expected <= 5000)"
        assert apps["youtube"]["estimated_quality"] in ("144p", "240p", "360p", "480p")

        # Enforcement info present
        assert "enforcement" in data
        assert data["enforcement"]["rules_applied"] == 2

        print(f"\n{'='*50}")
        print(f"DEMO: Zoom={apps['zoom']['ceil_kbps']/1000:.0f}Mbps ({apps['zoom']['estimated_quality']})")
        print(f"      YouTube={apps['youtube']['ceil_kbps']}Kbps ({apps['youtube']['estimated_quality']})")
        print(f"{'='*50}")

    def test_quality_endpoint(self, auth_headers):
        # Apply first so there's data
        httpx.post(f"{BASE}/api/v1/apps/priorities",
                   json={"priorities": [
                       {"app_id": "zoom", "priority": "HIGH"},
                       {"app_id": "youtube", "priority": "LOW"},
                   ]}, headers=auth_headers, timeout=10)

        r = httpx.get(f"{BASE}/api/v1/apps/quality", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        preds = r.json()["predictions"]
        assert len(preds) >= 2

    def test_reset_clears_rules(self, auth_headers):
        r = httpx.post(f"{BASE}/api/v1/apps/reset", headers=auth_headers, json={}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_signatures_returns_apps_array(self, auth_headers):
        """Signatures endpoint returns {apps: [...]}."""
        r = httpx.get(f"{BASE}/api/v1/apps/signatures", timeout=10)
        assert r.status_code == 200
        apps = r.json()["apps"]
        assert isinstance(apps, list)
        app_ids = [a["app_id"] for a in apps]
        assert "zoom" in app_ids
        assert "youtube" in app_ids

    def test_enforcement_status_endpoint(self, auth_headers):
        r = httpx.get(f"{BASE}/api/v1/apps/enforcement-status", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "mode" in data
        assert data["total_link_mbps"] == 100.0
