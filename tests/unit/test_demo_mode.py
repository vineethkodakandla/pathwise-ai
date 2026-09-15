"""Read-only guard for the public demo (server/demo.py)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from server.demo import (
    DEMO_WRITE_ALLOWLIST,
    READ_ONLY_DETAIL,
    install_read_only_guard,
    is_write_allowed,
)


def _client(enabled: bool) -> TestClient:
    """A small app wired the same way as server/main.py: guard, then CORS."""
    app = FastAPI()
    install_read_only_guard(app, enabled=enabled)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/v1/status")
    def status():
        return {"ok": True}

    @app.put("/api/v1/admin/users/{user_id}/suspend")
    def suspend(user_id: str):
        return {"suspended": user_id}

    @app.post("/api/v1/tickets/")
    def create_ticket():
        return {"id": "t-1"}

    @app.post("/api/v1/sandbox/validate")
    def validate():
        return {"result": "PASS"}

    return TestClient(app)


def test_reads_pass_and_writes_are_rejected():
    client = _client(enabled=True)
    assert client.get("/api/v1/status").status_code == 200
    r = client.put("/api/v1/admin/users/admin-001/suspend")
    assert r.status_code == 403
    assert r.json() == {"detail": READ_ONLY_DETAIL}


def test_trailing_slash_route_is_still_rejected():
    assert _client(enabled=True).post("/api/v1/tickets/").status_code == 403


def test_allowlisted_compute_endpoint_passes():
    assert _client(enabled=True).post("/api/v1/sandbox/validate").status_code == 200


def test_rejection_keeps_cors_headers_for_the_browser():
    r = _client(enabled=True).put(
        "/api/v1/admin/users/admin-001/suspend", headers={"Origin": "https://example.com"},
    )
    assert r.status_code == 403
    assert r.headers.get("access-control-allow-origin") == "*"


def test_guard_is_a_no_op_outside_demo_mode():
    assert _client(enabled=False).put("/api/v1/admin/users/admin-001/suspend").status_code == 200


def test_allowlist_matches_exact_paths_only():
    assert is_write_allowed("post", "/api/v1/ibn/parse/")
    assert is_write_allowed("HEAD", "/api/v1/anything")
    assert not is_write_allowed("POST", "/api/v1/auth/register")
    assert not is_write_allowed("DELETE", "/api/v1/ibn/intents/abc")
    assert not is_write_allowed("POST", "/api/v1/sandbox/validate/extra")
    assert all(path == path.rstrip("/") for path in DEMO_WRITE_ALLOWLIST)
