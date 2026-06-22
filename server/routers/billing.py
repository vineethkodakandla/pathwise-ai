"""
Billing and subscription management routes.
Prefix: /api/v1/billing
"""

from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text
import jwt

from server.db import get_db, is_postgres

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Use the canonical secret from server.auth so tokens verify consistently whether
# JWT_SECRET is provided via env or an ephemeral one was generated at startup.
from server.auth import JWT_SECRET

PLANS = {
    "starter":      {"name": "Starter",      "price": 49.00,  "sites": 2,  "links": 2},
    "professional": {"name": "Professional", "price": 149.00, "sites": 5,  "links": 4},
    "enterprise":   {"name": "Enterprise",   "price": 299.00, "sites": 20, "links": 6},
}


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

def require_admin(claims=Depends(_decode_token)):
    if claims.get("role") != "SUPER_ADMIN":
        raise HTTPException(403, "Admin access required")
    return claims

def _require_db(db=Depends(get_db)):
    if db is None:
        raise HTTPException(503, "Database unavailable")
    return db


class UpgradeRequest(BaseModel):
    plan_id: str


# ── Routes ───────────────────────────────────────────────────────

@router.get("/plans")
async def get_plans():
    """Public — list available subscription plans as array."""
    return {"plans": [{"id": k, **v} for k, v in PLANS.items()]}


@router.get("/subscription")
async def get_subscription(claims=Depends(require_user), db=Depends(_require_db)):
    """Get current user's active subscription — flat response."""
    user_id = claims.get("sub")
    row = db.execute(
        text("SELECT * FROM subscriptions WHERE user_id = :uid AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
        {"uid": user_id},
    ).fetchone()
    if not row:
        return {"plan_id": None, "plan_name": "None", "status": "none", "monthly_price": 0,
                "next_billing_date": None, "card_last4": "0000"}
    return {
        "id": row.id, "plan_id": row.plan_id, "plan_name": row.plan_name,
        "status": row.status, "monthly_price": float(row.monthly_price) if row.monthly_price else 0,
        "billing_cycle": row.billing_cycle,
        "start_date": str(row.start_date) if row.start_date else None,
        "next_billing_date": str(row.next_billing_date) if row.next_billing_date else None,
        "payment_method": row.payment_method,
        "card_last4": row.card_last4 or "4242",
    }


@router.post("/subscription/upgrade")
async def upgrade_subscription(req: UpgradeRequest, claims=Depends(require_user), db=Depends(_require_db)):
    if req.plan_id not in PLANS:
        raise HTTPException(400, f"Invalid plan: {req.plan_id}")
    user_id = claims.get("sub")
    plan = PLANS[req.plan_id]
    db.execute(
        text("UPDATE subscriptions SET status = 'cancelled' WHERE user_id = :uid AND status = 'active'"),
        {"uid": user_id},
    )
    sub_id = f"sub-{uuid.uuid4().hex[:8]}"
    db.execute(
        text("""INSERT INTO subscriptions (id, user_id, plan_id, plan_name, monthly_price, status, next_billing_date)
                VALUES (:id, :uid, :pid, :pname, :price, 'active', :nbd)"""),
        {"id": sub_id, "uid": user_id, "pid": req.plan_id,
         "pname": plan["name"], "price": plan["price"],
         "nbd": (datetime.utcnow() + timedelta(days=30)).date()},
    )
    db.commit()
    return {"success": True, "plan": plan, "plan_id": req.plan_id}


@router.post("/subscription/cancel")
async def cancel_subscription(claims=Depends(require_user), db=Depends(_require_db)):
    user_id = claims.get("sub")
    db.execute(
        text("UPDATE subscriptions SET status = 'cancelled' WHERE user_id = :uid AND status = 'active'"),
        {"uid": user_id},
    )
    db.commit()
    return {"success": True, "status": "cancelled"}


@router.get("/invoices")
async def get_invoices(claims=Depends(require_user), db=Depends(_require_db)):
    user_id = claims.get("sub")
    rows = db.execute(
        text("SELECT * FROM invoices WHERE user_id = :uid ORDER BY issued_at DESC"),
        {"uid": user_id},
    ).fetchall()
    return {
        "invoices": [
            {"id": r.id, "amount": float(r.amount) if r.amount else 0, "status": r.status,
             "period_start": str(r.period_start) if r.period_start else None,
             "period_end": str(r.period_end) if r.period_end else None,
             "issued_at": str(r.issued_at) if r.issued_at else None}
            for r in rows
        ]
    }


@router.get("/admin/revenue")
async def admin_revenue(claims=Depends(require_admin), db=Depends(_require_db)):
    """Admin — MRR/ARR dashboard with by_plan array and monthly_trend."""
    mrr_row = db.execute(
        text("SELECT COALESCE(SUM(monthly_price), 0) AS mrr FROM subscriptions WHERE status = 'active'")
    ).fetchone()
    mrr = float(mrr_row.mrr) if mrr_row else 0

    # by_plan as array (frontend expects [{plan_name, count, revenue}, ...])
    plan_rows = db.execute(
        text("""SELECT plan_name, plan_id, COUNT(*) AS count, COALESCE(SUM(monthly_price),0) AS revenue
                FROM subscriptions WHERE status = 'active' GROUP BY plan_name, plan_id""")
    ).fetchall()
    by_plan = [{"plan_name": r.plan_name, "plan_id": r.plan_id,
                "count": r.count, "revenue": float(r.revenue)} for r in plan_rows]

    # monthly_trend from invoices
    try:
        if is_postgres():
            trend_rows = db.execute(text("""
                SELECT DATE_TRUNC('month', issued_at) AS month, SUM(amount) AS revenue, COUNT(*) AS invoices
                FROM invoices WHERE status = 'paid' GROUP BY month ORDER BY month DESC LIMIT 12
            """)).fetchall()
        else:
            trend_rows = db.execute(text("""
                SELECT strftime('%Y-%m', issued_at) AS month, SUM(amount) AS revenue, COUNT(*) AS invoices
                FROM invoices WHERE status = 'paid' GROUP BY month ORDER BY month DESC LIMIT 12
            """)).fetchall()
        monthly_trend = [{"month": str(r.month), "revenue": float(r.revenue), "invoices": r.invoices}
                         for r in trend_rows]
    except Exception:
        monthly_trend = []

    total_mrr = mrr
    return {
        "total_mrr": total_mrr,
        "arr": total_mrr * 12,
        "by_plan": by_plan,
        "monthly_trend": monthly_trend,
    }
