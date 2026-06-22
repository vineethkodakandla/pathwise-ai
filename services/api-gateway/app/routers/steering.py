# services/api-gateway/app/routers/steering.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import redis.asyncio as redis
import json

from app.config import get_settings

router = APIRouter(prefix="/api/v1/steering", tags=["Traffic Steering"])

settings = get_settings()
redis_client = redis.from_url(settings.redis_url)


class SteeringRequest(BaseModel):
    source_link: str
    target_link: str
    traffic_classes: list[str]
    reason: Optional[str] = "Manual steering request"


class SteeringResponse(BaseModel):
    status: str
    action: str
    source_link: str
    target_link: str
    traffic_classes: list[str]
    sandbox_validated: bool


@router.post("/execute", response_model=SteeringResponse)
async def execute_steering(request: SteeringRequest):
    """
    Manually trigger a traffic steering action.

    The request is validated in the Digital Twin sandbox before execution.
    """
    # Publish steering request to Redis for the steering engine
    await redis_client.xadd("steering:requests", {
        "source_link": request.source_link,
        "target_link": request.target_link,
        "traffic_classes": json.dumps(request.traffic_classes),
        "reason": request.reason,
        "type": "manual",
    })

    return SteeringResponse(
        status="submitted",
        action="manual_shift",
        source_link=request.source_link,
        target_link=request.target_link,
        traffic_classes=request.traffic_classes,
        sandbox_validated=False,
    )


@router.get("/history")
async def get_steering_history(limit: int = 50):
    """Get the audit log of past steering decisions."""
    entries = await redis_client.xrevrange("steering:audit", count=limit)

    history = []
    for entry_id, fields in entries:
        history.append({
            "id": entry_id.decode(),
            "action": fields.get(b"action", b"").decode(),
            "source_link": fields.get(b"source", b"").decode(),
            "target_link": fields.get(b"target", b"").decode(),
            "traffic_classes": fields.get(b"traffic_classes", b"").decode(),
            "confidence": float(fields.get(b"confidence", 0)),
            "reason": fields.get(b"reason", b"").decode(),
            "status": fields.get(b"status", b"").decode(),
            "sandbox_validated": fields.get(b"sandbox_validated", b"").decode(),
        })

    return {"history": history, "count": len(history)}
