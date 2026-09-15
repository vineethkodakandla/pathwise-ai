"""
Public demo hardening.

The hosted portfolio demo is one shared instance that anyone on the internet
can reach. With DEMO_MODE=true (set in render.yaml):

  * seeded accounts get random per-boot passwords, so no password is ever
    published, bundled into the frontend, or guessable;
  * visitors sign in with POST /api/v1/auth/demo, which issues a short-lived
    token for a demo persona without any password;
  * every state-changing request is rejected except sign-in and a short
    allowlist of compute-only endpoints, so one visitor cannot suspend
    accounts, cancel billing or rewrite policy for everyone else.

Outside DEMO_MODE (local development) none of this applies.
"""

from __future__ import annotations

import os
import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse

DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
DEMO_TOKEN_MINUTES = int(os.environ.get("DEMO_TOKEN_MINUTES", "30"))

# Persona key -> seeded app_users.id (see scripts/seed_ui_data.py).
DEMO_PERSONAS: dict[str, str] = {
    "admin": "admin-001",
    "owner": "user-001",
}

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Writes that stay open in demo mode: sign-in, plus compute-only endpoints whose
# side effects are bounded in memory (sandbox history keeps 50 reports, the
# audit log 10,000 entries) and never touch another visitor's data.
DEMO_WRITE_ALLOWLIST = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/login/v2",
    "/api/v1/auth/demo",
    "/api/v1/sandbox/validate",
    "/api/v1/ibn/parse",
})

READ_ONLY_DETAIL = (
    "Read-only public demo: changes are disabled on this shared instance. "
    "Run PathWise AI locally to try write actions."
)


def seed_password() -> tuple[str, bool]:
    """Password for a seeded account, and whether it was randomly generated.

    Demo mode always generates one. Locally, SEED_DEMO_PASSWORD sets a known
    password for every seeded persona; without it a random one is generated.
    """
    if not DEMO_MODE:
        configured = os.environ.get("SEED_DEMO_PASSWORD")
        if configured:
            return configured, False
    return secrets.token_urlsafe(18), True


def is_write_allowed(method: str, path: str) -> bool:
    if method.upper() in SAFE_METHODS:
        return True
    return (path.rstrip("/") or "/") in DEMO_WRITE_ALLOWLIST


def install_read_only_guard(app, enabled: bool = DEMO_MODE) -> None:
    """Reject state-changing HTTP requests outside DEMO_WRITE_ALLOWLIST.

    Install this before CORSMiddleware: Starlette runs the middleware added
    last as the outermost layer, so CORS headers still reach the browser on
    the 403 and the frontend can show the real reason.
    """
    if not enabled:
        return

    @app.middleware("http")
    async def demo_read_only_guard(request: Request, call_next):
        if not is_write_allowed(request.method, request.url.path):
            return JSONResponse(status_code=403, content={"detail": READ_ONLY_DETAIL})
        return await call_next(request)
