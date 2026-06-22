"""
Authentication module — JWT tokens + bcrypt password hashing + account lockout.

Implements:
  - Req-Func-Sw-16: Secure credential login with bcrypt one-way hashing
  - UC-6: Generic error on failed login, account lockout after 5 attempts
"""

from __future__ import annotations
import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import secrets as _secrets

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, WebSocket

# Never ship a hardcoded secret in source. If JWT_SECRET is unset (e.g. local
# sim/demo), generate an ephemeral random one so the app still boots — tokens
# simply won't survive a restart. Set JWT_SECRET in the environment (Render,
# Docker, etc.) for stable tokens across restarts/instances.
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = _secrets.token_urlsafe(48)
    print(
        "[auth] WARNING: JWT_SECRET not set — using an ephemeral random secret. "
        "Set JWT_SECRET for stable tokens across restarts."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.environ.get("JWT_EXPIRY_MINUTES", "60"))
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_S = 30 * 60  # 30-minute auto-unlock, matches /auth/login/v2 DB path

VALID_ROLES = frozenset({
    "SUPER_ADMIN", "NETWORK_ADMIN", "IT_MANAGER", "MSP_TECH",
    "IT_STAFF", "END_USER", "BUSINESS_OWNER",
})
# Roles that confer privileged platform access; only SUPER_ADMIN may grant these.
PRIVILEGED_ROLES = frozenset({"SUPER_ADMIN", "NETWORK_ADMIN"})


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    role: str  # NETWORK_ADMIN, IT_MANAGER, MSP_TECH, IT_STAFF, END_USER
    is_active: bool = True
    failed_attempts: int = 0
    locked_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)


# ── In-Memory User Store ───────────────────────────────────────

_users: dict[str, User] = {}


def _seed_default_users():
    """Create default admin and demo users on startup."""
    defaults = [
        ("admin@pathwise.local", "admin", "NETWORK_ADMIN"),
        ("manager@pathwise.local", "manager", "IT_MANAGER"),
        ("tech@pathwise.local", "tech", "MSP_TECH"),
        ("staff@pathwise.local", "staff", "IT_STAFF"),
        ("user@pathwise.local", "user", "END_USER"),
    ]
    for email, password, role in defaults:
        if not any(u.email == email for u in _users.values()):
            uid = str(uuid.uuid4())[:8]
            _users[uid] = User(
                id=uid,
                email=email,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                role=role,
            )


_seed_default_users()


# ── Password Hashing ──────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT Token Management ──────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": time.time() + JWT_EXPIRY_MINUTES * 60,
        "iat": time.time(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Login ─────────────────────────────────────────────────────

def login(email: str, password: str) -> dict:
    """
    Authenticate a user. Returns JWT on success.
    - Generic error message on failure (UC-6: never reveal which field is wrong)
    - Account lockout after 5 consecutive failures
    """
    user = next((u for u in _users.values() if u.email == email), None)

    if user and user.locked_at:
        if time.time() - user.locked_at >= LOCKOUT_DURATION_S:
            user.locked_at = None
            user.failed_attempts = 0
        else:
            raise HTTPException(
                status_code=423,
                detail="Account locked due to too many failed attempts. Contact system administrator.",
            )

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_at = time.time()
            raise HTTPException(
                status_code=423,
                detail="Account locked due to too many failed attempts. Contact system administrator.",
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success — reset failed attempts
    user.failed_attempts = 0
    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role, "email": user.email}


# ── User Management ───────────────────────────────────────────

def register_user(email: str, password: str, role: str) -> User:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown role '{role}'. Valid: {sorted(VALID_ROLES)}",
        )
    if any(u.email == email for u in _users.values()):
        raise HTTPException(status_code=409, detail="Email already registered")
    uid = str(uuid.uuid4())[:8]
    user = User(
        id=uid, email=email,
        password_hash=hash_password(password),
        role=role,
    )
    _users[uid] = user
    return user


def get_user_by_id(user_id: str) -> Optional[User]:
    return _users.get(user_id)


def get_all_users() -> list[User]:
    return list(_users.values())


def unlock_user(user_id: str) -> bool:
    user = _users.get(user_id)
    if user:
        user.locked_at = None
        user.failed_attempts = 0
        return True
    return False


# ── FastAPI Dependency: Extract Current User ──────────────────

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"


async def get_current_user(request: Request) -> Optional[User]:
    """FastAPI dependency — extracts and validates JWT from Authorization header."""
    if not AUTH_ENABLED:
        # Return a default admin user when auth is disabled
        return next((u for u in _users.values() if u.role == "NETWORK_ADMIN"), None)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header[7:]
    payload = decode_token(token)
    user = get_user_by_id(payload.get("sub", ""))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user


async def get_current_user_strict(request: Request) -> User:
    """Like get_current_user but does NOT honor AUTH_ENABLED=false dev bypass.
    Used for privileged operations (user creation, unlock) that must always
    require a real authenticated token regardless of dev mode."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    token = auth_header[7:]
    payload = decode_token(token)
    user = get_user_by_id(payload.get("sub", ""))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user


async def get_ws_user(websocket: WebSocket) -> Optional[User]:
    """Extract user from WebSocket query param: ?token=xxx"""
    if not AUTH_ENABLED:
        return next((u for u in _users.values() if u.role == "NETWORK_ADMIN"), None)

    token = websocket.query_params.get("token", "")
    if not token:
        return None
    try:
        payload = decode_token(token)
        return get_user_by_id(payload.get("sub", ""))
    except Exception:
        return None
