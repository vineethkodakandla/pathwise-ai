# services/api-gateway/app/routers/predictions.py

from fastapi import APIRouter
import json
import redis.asyncio as redis

from app.config import get_settings

router = APIRouter(prefix="/api/v1/predictions", tags=["Predictions"])

settings = get_settings()
redis_client = redis.from_url(settings.redis_url)


@router.get("/all")
async def get_all_predictions():
    """Get latest predictions and health scores for all active links."""
    link_ids = await redis_client.smembers("active_links")
    predictions = {}

    for link_id_bytes in link_ids:
        link_id = link_id_bytes.decode()
        pred = await redis_client.hgetall(f"prediction:{link_id}")
        if pred:
            predictions[link_id] = {
                "health_score": float(pred.get(b"health_score", 0)),
                "confidence": float(pred.get(b"confidence", 0)),
                "latency_forecast": json.loads(
                    pred.get(b"latency_forecast", b"[]").decode()
                ),
                "jitter_forecast": json.loads(
                    pred.get(b"jitter_forecast", b"[]").decode()
                ),
                "packet_loss_forecast": json.loads(
                    pred.get(b"packet_loss_forecast", b"[]").decode()
                ),
                "timestamp": pred.get(b"timestamp", b"0").decode(),
            }

    return {"predictions": predictions, "count": len(predictions)}


@router.get("/{link_id}")
async def get_prediction(link_id: str):
    """Get the latest prediction and health score for a specific link."""
    pred = await redis_client.hgetall(f"prediction:{link_id}")

    if not pred:
        return {"error": f"No prediction available for link {link_id}"}

    return {
        "link_id": link_id,
        "health_score": float(pred.get(b"health_score", 0)),
        "confidence": float(pred.get(b"confidence", 0)),
        "latency_forecast": json.loads(
            pred.get(b"latency_forecast", b"[]").decode()
        ),
        "jitter_forecast": json.loads(
            pred.get(b"jitter_forecast", b"[]").decode()
        ),
        "packet_loss_forecast": json.loads(
            pred.get(b"packet_loss_forecast", b"[]").decode()
        ),
        "timestamp": pred.get(b"timestamp", b"0").decode(),
    }
