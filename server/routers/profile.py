"""
User profile routes.
Prefix: /api/v1/profile
"""

from __future__ import annotations
import os

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
import jwt

from server.db import get_db

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

# Use the canonical secret from server.auth so tokens verify consistently whether
# JWT_SECRET is provided via env or an ephemeral one was generated at startup.
from server.auth import JWT_SECRET


# ── Auth helpers ─────────────────────────────────────────────────

def _decode_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


def require_user(claims=Depends(_decode_token)):
    if claims.get("role") not in ("BUSINESS_OWNER", "SUPER_ADMIN", "NETWORK_ADMIN"):
        raise HTTPException(403, "User access required")
    return claims


def _require_db(db=Depends(get_db)):
    if db is None:
        raise HTTPException(503, "Database unavailable")
    return db


# ── Request models ───────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────

@router.get("/")
async def get_profile(claims=Depends(require_user), db=Depends(_require_db)):
    """Get full user profile with subscription and sites."""
    user_id = claims.get("sub")

    user = db.execute(
        text("SELECT * FROM app_users WHERE id = :id"), {"id": user_id}
    ).fetchone()
    if not user:
        raise HTTPException(404, "User not found")

    # Subscription
    sub = db.execute(
        text("SELECT * FROM subscriptions WHERE user_id = :uid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"uid": user_id},
    ).fetchone()

    # Sites
    sites = db.execute(
        text("SELECT * FROM sites WHERE user_id = :uid ORDER BY name"), {"uid": user_id}
    ).fetchall()

    # Return flat response — frontend expects profile.name, profile.sites, etc.
    return {
        "id": user.id, "name": user.name, "email": user.email,
        "role": user.role, "company": user.company,
        "industry": user.industry, "avatar_initials": user.avatar_initials,
        "is_active": bool(user.is_active),
        "created_at": str(user.created_at) if user.created_at else None,
        "subscription": {
            "id": sub.id, "plan_id": sub.plan_id, "plan_name": sub.plan_name,
            "status": sub.status, "monthly_price": float(sub.monthly_price) if sub.monthly_price else 0,
            "next_billing_date": str(sub.next_billing_date) if sub.next_billing_date else None,
        } if sub else None,
        "sites": [
            {"id": s.id, "name": s.name, "location": s.location, "status": s.status}
            for s in sites
        ],
    }


@router.put("/")
async def update_profile(req: UpdateProfileRequest, claims=Depends(require_user), db=Depends(_require_db)):
    """Update user profile fields (name, company, industry)."""
    user_id = claims.get("sub")

    updates = []
    params = {"id": user_id}
    if req.name is not None:
        updates.append("name = :name")
        params["name"] = req.name
    if req.company is not None:
        updates.append("company = :company")
        params["company"] = req.company
    if req.industry is not None:
        updates.append("industry = :industry")
        params["industry"] = req.industry

    if not updates:
        raise HTTPException(400, "No fields provided to update")

    updates.append("updated_at = CURRENT_TIMESTAMP")
    db.execute(text(f"UPDATE app_users SET {', '.join(updates)} WHERE id = :id"), params)
    db.commit()
    return {"status": "updated"}
