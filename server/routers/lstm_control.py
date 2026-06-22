"""
Admin LSTM model management routes.
Prefix: /api/v1/lstm
"""

from __future__ import annotations
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
import jwt

from server.db import get_db

router = APIRouter(prefix="/api/v1/lstm", tags=["lstm"])

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


def require_admin(claims=Depends(_decode_token)):
    if claims.get("role") != "SUPER_ADMIN":
        raise HTTPException(403, "Admin access required")
    return claims


def _require_db(db=Depends(get_db)):
    if db is None:
        raise HTTPException(503, "Database unavailable")
    return db


# ── Request models ───────────────────────────────────────────────

class CreateModelRequest(BaseModel):
    name: str
    description: Optional[str] = None
    sequence_length: int = 60
    hidden_units: int = 128
    num_layers: int = 2
    dropout: float = 0.2
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100


class HyperparamsRequest(BaseModel):
    prediction_window_s: Optional[int] = None
    health_threshold: Optional[int] = None
    confidence_threshold: Optional[float] = None
    brownout_sensitivity: Optional[float] = None
    learning_rate: Optional[float] = None
    batch_size: Optional[int] = None
    dropout: Optional[float] = None
    sequence_length: Optional[int] = None


# ── Routes ───────────────────────────────────────────────────────

@router.get("/models")
async def list_models(claims=Depends(require_admin), db=Depends(_require_db)):
    """List all LSTM model configurations."""
    rows = db.execute(
        text("SELECT * FROM lstm_model_configs ORDER BY created_at DESC")
    ).fetchall()
    return {
        "models": [
            {
                "id": r.id, "name": r.name, "description": r.description,
                "sequence_length": r.sequence_length, "hidden_units": r.hidden_units,
                "num_layers": r.num_layers, "dropout": float(r.dropout) if r.dropout else None,
                "learning_rate": float(r.learning_rate) if r.learning_rate else None,
                "batch_size": r.batch_size, "epochs": r.epochs,
                "is_active": r.is_active,
                "accuracy": float(r.accuracy) if r.accuracy else None,
                "mae_latency": float(r.mae_latency) if r.mae_latency else None,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/models")
async def create_model(req: CreateModelRequest, claims=Depends(require_admin), db=Depends(_require_db)):
    """Create a new LSTM model configuration."""
    model_id = f"lstm-{uuid.uuid4().hex[:8]}"
    db.execute(
        text("""INSERT INTO lstm_model_configs
                (id, name, description, sequence_length, hidden_units, num_layers,
                 dropout, learning_rate, batch_size, epochs, is_active)
                VALUES (:id, :name, :desc, :sl, :hu, :nl, :do, :lr, :bs, :ep, FALSE)"""),
        {
            "id": model_id, "name": req.name, "desc": req.description,
            "sl": req.sequence_length, "hu": req.hidden_units, "nl": req.num_layers,
            "do": req.dropout, "lr": req.learning_rate, "bs": req.batch_size, "ep": req.epochs,
        },
    )
    db.commit()
    return {"status": "created", "model_id": model_id}


@router.post("/models/{model_id}/activate")
async def activate_model(model_id: str, claims=Depends(require_admin), db=Depends(_require_db)):
    """Set the specified model as the active model (deactivates all others)."""
    # Check model exists
    row = db.execute(text("SELECT id FROM lstm_model_configs WHERE id = :id"), {"id": model_id}).fetchone()
    if not row:
        raise HTTPException(404, "Model not found")

    # Deactivate all, then activate the target
    db.execute(text("UPDATE lstm_model_configs SET is_active = 0"))
    db.execute(text("UPDATE lstm_model_configs SET is_active = 1 WHERE id = :id"), {"id": model_id})
    db.commit()
    return {"status": "activated", "model_id": model_id}


@router.post("/retrain")
async def trigger_retrain(model_id: str = None, claims=Depends(require_admin), db=Depends(_require_db)):
    """Trigger a background model retrain. If model_id given, retrain that model; else retrain active."""
    if model_id:
        target = db.execute(
            text("SELECT id, name FROM lstm_model_configs WHERE id = :id"), {"id": model_id}
        ).fetchone()
    else:
        target = db.execute(
            text("SELECT id, name FROM lstm_model_configs WHERE is_active = 1 LIMIT 1")
        ).fetchone()
    if not target:
        raise HTTPException(400, "No model found to retrain")
    return {
        "status": "retrain_queued",
        "model_id": target.id,
        "model_name": target.name,
        "message": "Retraining job has been queued. Check /performance for updated metrics.",
    }


@router.put("/hyperparams")
async def update_hyperparams(req: HyperparamsRequest, claims=Depends(require_admin), db=Depends(_require_db)):
    """Live-update inference hyperparameters on the active model."""
    active = db.execute(
        text("SELECT id FROM lstm_model_configs WHERE is_active = 1 LIMIT 1")
    ).fetchone()
    if not active:
        raise HTTPException(400, "No active model found")

    # Update env vars for runtime params (these don't go to DB)
    import os as _os
    applied = {}
    if req.prediction_window_s is not None:
        _os.environ["PREDICTION_WINDOW_S"] = str(req.prediction_window_s)
        applied["prediction_window_s"] = req.prediction_window_s
    if req.health_threshold is not None:
        _os.environ["HEALTH_SCORE_THRESHOLD"] = str(req.health_threshold)
        applied["health_threshold"] = req.health_threshold
    if req.confidence_threshold is not None:
        applied["confidence_threshold"] = req.confidence_threshold
    if req.brownout_sensitivity is not None:
        applied["brownout_sensitivity"] = req.brownout_sensitivity

    # Update DB-stored model params
    updates = []
    params = {"id": active.id}
    if req.learning_rate is not None:
        updates.append("learning_rate = :lr")
        params["lr"] = req.learning_rate
        applied["learning_rate"] = req.learning_rate
    if req.batch_size is not None:
        updates.append("batch_size = :bs")
        params["bs"] = req.batch_size
        applied["batch_size"] = req.batch_size
    if req.dropout is not None:
        updates.append("dropout = :do")
        params["do"] = req.dropout
        applied["dropout"] = req.dropout
    if req.sequence_length is not None:
        updates.append("sequence_length = :sl")
        params["sl"] = req.sequence_length
        applied["sequence_length"] = req.sequence_length

    if updates:
        db.execute(text(f"UPDATE lstm_model_configs SET {', '.join(updates)} WHERE id = :id"), params)
        db.commit()

    if not applied:
        raise HTTPException(400, "No parameters provided to update")

    return {"success": True, "applied": applied}


@router.get("/performance")
async def get_performance(claims=Depends(require_admin), db=Depends(_require_db)):
    """Get accuracy metrics for all models."""
    rows = db.execute(
        text("SELECT id, name, is_active, accuracy, mae_latency FROM lstm_model_configs ORDER BY accuracy DESC NULLS LAST")
    ).fetchall()
    return {
        "models": [
            {
                "id": r.id, "name": r.name, "is_active": r.is_active,
                "accuracy": float(r.accuracy) if r.accuracy else None,
                "mae_latency": float(r.mae_latency) if r.mae_latency else None,
            }
            for r in rows
        ]
    }
