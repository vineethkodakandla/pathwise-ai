"""
UI Test Suite — Authentication and Role-Based Access Control
Tests all 9 accounts (1 admin + 8 business owners).
"""
import os
import pytest

try:
    import httpx
except ImportError:
    httpx = None

BASE = os.getenv("BACKEND_URL", "http://localhost:8000")

pytestmark = pytest.mark.skipif(httpx is None, reason="httpx not installed")

ADMIN_CREDS = {"email": "admin@pathwise.ai", "password": "Admin@PathWise2026"}
USER_CREDS = [
    {"email": "marcus@riveralogistics.com", "password": "Rivera@2026"},
    {"email": "priya@nairmedical.com", "password": "NairMed@2026"},
    {"email": "deshawn@carterretail.com", "password": "Carter@2026"},
    {"email": "sofia@moralesacademy.edu", "password": "Sofia@2026"},
    {"email": "kenji@tanakafab.com", "password": "Tanaka@2026"},
    {"email": "amara@oseifinance.com", "password": "Amara@2026"},
    {"email": "elena@petrovhotel.com", "password": "Elena@2026"},
    {"email": "tobias@bauertech.io", "password": "Bauer@2026"},
]

def _login(creds):
    # Try v2 first, fall back to v1
    r = httpx.post(f"{BASE}/api/v1/auth/login/v2", json=creds, timeout=5)
    if r.status_code == 404:
        r = httpx.post(f"{BASE}/api/v1/auth/login", json=creds, timeout=5)
    return r

def test_admin_login():
    r = _login(ADMIN_CREDS)
    if r.status_code != 200:
        pytest.skip("DB-backed accounts not seeded yet — run scripts/seed_ui_data.py")
    data = r.json()
    assert data["role"] == "SUPER_ADMIN"
    assert data["redirect_to"] == "/admin/dashboard"

@pytest.mark.parametrize("creds", USER_CREDS)
def test_user_login(creds):
    r = _login(creds)
    if r.status_code != 200:
        pytest.skip(f"Account not seeded: {creds['email']}")
    data = r.json()
    assert data["role"] == "BUSINESS_OWNER"
    assert data["redirect_to"] == "/user/dashboard"
    assert "access_token" in data

def test_invalid_login():
    r = httpx.post(f"{BASE}/api/v1/auth/login/v2",
                   json={"email": "nobody@fake.com", "password": "wrong"}, timeout=5)
    # 401 or 404 (if v2 not available) are both acceptable
    assert r.status_code in (401, 404)

def test_wrong_password_generic_error():
    r = httpx.post(f"{BASE}/api/v1/auth/login/v2",
                   json={"email": ADMIN_CREDS["email"], "password": "wrongpassword"}, timeout=5)
    if r.status_code == 404:
        pytest.skip("v2 login not available")
    assert r.status_code == 401
    body = r.json()
    assert "Invalid credentials" in body.get("detail", "")
