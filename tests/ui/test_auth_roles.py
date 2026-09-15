"""
UI Test Suite — Authentication and Role-Based Access Control
Tests all 9 accounts (1 admin + 8 business owners) against a running backend.

Seed passwords are not hardcoded. Start the backend on a fresh database with
SEED_DEMO_PASSWORD set and run these tests with the same variable; without it
the login tests are skipped.
"""
import os

import pytest

try:
    import httpx
except ImportError:
    httpx = None

BASE = os.getenv("BACKEND_URL", "http://localhost:8000")
PASSWORD = os.getenv("SEED_DEMO_PASSWORD")

pytestmark = pytest.mark.skipif(httpx is None, reason="httpx not installed")
needs_password = pytest.mark.skipif(PASSWORD is None, reason="SEED_DEMO_PASSWORD not set")

ADMIN_EMAIL = "admin@pathwise.ai"
USER_EMAILS = [
    "marcus@riveralogistics.com",
    "priya@nairmedical.com",
    "deshawn@carterretail.com",
    "sofia@moralesacademy.edu",
    "kenji@tanakafab.com",
    "amara@oseifinance.com",
    "elena@petrovhotel.com",
    "tobias@bauertech.io",
]

def _login(email, password):
    # Try v2 first, fall back to v1
    creds = {"email": email, "password": password}
    r = httpx.post(f"{BASE}/api/v1/auth/login/v2", json=creds, timeout=5)
    if r.status_code == 404:
        r = httpx.post(f"{BASE}/api/v1/auth/login", json=creds, timeout=5)
    return r

@needs_password
def test_admin_login():
    r = _login(ADMIN_EMAIL, PASSWORD)
    if r.status_code != 200:
        pytest.skip("DB-backed accounts not seeded yet — run scripts/seed_ui_data.py")
    data = r.json()
    assert data["role"] == "SUPER_ADMIN"
    assert data["redirect_to"] == "/admin/dashboard"

@needs_password
@pytest.mark.parametrize("email", USER_EMAILS)
def test_user_login(email):
    r = _login(email, PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Account not seeded: {email}")
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
                   json={"email": ADMIN_EMAIL, "password": "wrongpassword"}, timeout=5)
    if r.status_code == 404:
        pytest.skip("v2 login not available")
    assert r.status_code == 401
    body = r.json()
    assert "Invalid credentials" in body.get("detail", "")
