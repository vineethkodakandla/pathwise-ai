"""
Support ticket system routes.
Prefix: /api/v1/tickets
"""

from __future__ import annotations
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text
import jwt

from server.db import get_db

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])

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


def require_admin(claims=Depends(_decode_token)):
    if claims.get("role") != "SUPER_ADMIN":
        raise HTTPException(403, "Admin access required")
    return claims


def _require_db(db=Depends(get_db)):
    if db is None:
        raise HTTPException(503, "Database unavailable")
    return db


# ── Request models ───────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    subject: str
    description: str
    priority: str = "medium"
    category: str = "general"


class RespondTicketRequest(BaseModel):
    admin_response: str   # frontend sends admin_response
    status: str = "resolved"


# ── Routes ───────────────────────────────────────────────────────

@router.post("/")
async def create_ticket(req: CreateTicketRequest, claims=Depends(require_user), db=Depends(_require_db)):
    """Create a new support ticket."""
    user_id = claims.get("sub")
    ticket_id = f"ticket-{uuid.uuid4().hex[:8]}"
    db.execute(
        text("""INSERT INTO support_tickets (id, user_id, subject, description, priority, category)
                VALUES (:id, :uid, :sub, :desc, :pri, :cat)"""),
        {
            "id": ticket_id, "uid": user_id, "sub": req.subject,
            "desc": req.description, "pri": req.priority, "cat": req.category,
        },
    )
    db.commit()
    return {"status": "created", "ticket_id": ticket_id}


@router.get("/my")
async def get_my_tickets(claims=Depends(require_user), db=Depends(_require_db)):
    """Get tickets belonging to the current user."""
    user_id = claims.get("sub")
    rows = db.execute(
        text("SELECT * FROM support_tickets WHERE user_id = :uid ORDER BY created_at DESC"),
        {"uid": user_id},
    ).fetchall()
    return {
        "tickets": [
            {
                "id": r.id, "subject": r.subject, "description": r.description,
                "priority": r.priority, "status": r.status, "category": r.category,
                "admin_response": r.admin_response, "resolved_by": r.resolved_by,
                "created_at": str(r.created_at) if r.created_at else None,
                "updated_at": str(r.updated_at) if r.updated_at else None,
            }
            for r in rows
        ]
    }


@router.get("/admin/all")
async def admin_get_all_tickets(claims=Depends(require_admin), db=Depends(_require_db)):
    """Admin — get all tickets with user info, sorted by priority."""
    priority_order = "CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END"
    rows = db.execute(
        text(f"""SELECT t.*, u.name AS user_name, u.email AS user_email, u.company AS user_company
                 FROM support_tickets t
                 LEFT JOIN app_users u ON t.user_id = u.id
                 ORDER BY {priority_order}, t.created_at DESC""")
    ).fetchall()
    return {
        "tickets": [
            {
                "id": r.id, "user_id": r.user_id, "user_name": r.user_name,
                "user_email": r.user_email, "user_company": r.user_company,
                "subject": r.subject, "description": r.description,
                "priority": r.priority, "status": r.status, "category": r.category,
                "admin_response": r.admin_response, "resolved_by": r.resolved_by,
                "created_at": str(r.created_at) if r.created_at else None,
                "updated_at": str(r.updated_at) if r.updated_at else None,
            }
            for r in rows
        ]
    }


@router.put("/admin/{ticket_id}/respond")
async def admin_respond_ticket(ticket_id: str, req: RespondTicketRequest, claims=Depends(require_admin), db=Depends(_require_db)):
    """Admin — respond to and optionally resolve a ticket."""
    admin_id = claims.get("sub")
    result = db.execute(
        text("""UPDATE support_tickets
                SET admin_response = :resp, status = :status, resolved_by = :admin, updated_at = CURRENT_TIMESTAMP
                WHERE id = :tid"""),
        {"resp": req.admin_response, "status": req.status, "admin": admin_id, "tid": ticket_id},
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Ticket not found")
    return {"status": "updated", "ticket_id": ticket_id}
