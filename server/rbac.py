"""
Role-Based Access Control (RBAC) — enforces per-route authorization.

Implements Req-Func-Sw-15: Five roles with tiered permissions.
"""

from __future__ import annotations
from enum import Enum
from functools import wraps

from fastapi import Depends, HTTPException

from server.auth import get_current_user, User


class Role(str, Enum):
    NETWORK_ADMIN = "NETWORK_ADMIN"
    IT_MANAGER = "IT_MANAGER"
    MSP_TECH = "MSP_TECH"
    IT_STAFF = "IT_STAFF"
    END_USER = "END_USER"


# Permission matrix: each role maps to a set of allowed categories
PERMISSIONS: dict[str, set[str]] = {
    "NETWORK_ADMIN": {"telemetry", "predictions", "steering", "routing", "sandbox", "policies", "ibn", "admin", "audit", "reports", "alerts", "users"},
    "IT_MANAGER":    {"telemetry", "predictions", "steering", "routing", "sandbox", "policies", "ibn", "audit", "reports", "alerts"},
    "MSP_TECH":      {"telemetry", "predictions", "steering", "routing", "sandbox", "policies", "ibn", "reports"},
    "IT_STAFF":      {"telemetry", "predictions", "sandbox", "reports"},
    "END_USER":      {"telemetry", "predictions"},
}


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory. Returns a dependency that checks the
    current user's role is in the allowed set.

    Usage:
        @app.get("/admin/...", dependencies=[Depends(require_role("NETWORK_ADMIN"))])
    """
    async def _check(user: User = Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {', '.join(allowed_roles)}",
            )
        return user
    return _check


def require_permission(category: str):
    """
    FastAPI dependency factory. Checks the current user's role has
    access to the given permission category.

    Usage:
        @app.post("/steering/...", dependencies=[Depends(require_permission("steering"))])
    """
    async def _check(user: User = Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        allowed = PERMISSIONS.get(user.role, set())
        if category not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' does not have '{category}' permission",
            )
        return user
    return _check
