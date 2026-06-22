# services/api-gateway/app/websocket/scoreboard.py

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis

class ScoreboardManager:
    """
    Pushes real-time health scores to connected dashboard clients
    via WebSocket at 1Hz update rate.
    
    Data per link:
    - Current health score (0-100)
    - Predicted score in 30s / 60s
    - Confidence level
    - Raw metrics (latency, jitter, loss)
    - Active steering decisions
    - Trend direction (improving/stable/degrading)
    """

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)

    async def broadcast_loop(self):
        """Continuously fetch predictions and broadcast to all clients."""
        while True:
            try:
                link_ids = await self.redis.smembers("active_links")
                scoreboard_data = {}
                
                for link_id_bytes in link_ids:
                    link_id = link_id_bytes.decode()
                    pred = await self.redis.hgetall(f"prediction:{link_id}")
                    raw = await self.redis.xrevrange("telemetry:raw", count=1)
                    
                    if pred:
                        scoreboard_data[link_id] = {
                            "health_score": float(pred.get(b"health_score", 0)),
                            "confidence": float(pred.get(b"confidence", 0)),
                            "latency_current": self._get_latest_metric(raw, "latency_ms"),
                            "jitter_current": self._get_latest_metric(raw, "jitter_ms"),
                            "packet_loss_current": self._get_latest_metric(raw, "packet_loss_pct"),
                            "latency_forecast": json.loads(pred.get(b"latency_forecast", b"[]")),
                            "trend": self._compute_trend(pred),
                        }
                
                message = json.dumps({
                    "type": "scoreboard_update",
                    "data": scoreboard_data,
                    "timestamp": asyncio.get_event_loop().time(),
                })
                
                # Broadcast to all connected clients
                disconnected = []
                for ws in self.active_connections:
                    try:
                        await ws.send_text(message)
                    except WebSocketDisconnect:
                        disconnected.append(ws)
                
                for ws in disconnected:
                    self.active_connections.remove(ws)
            
            except Exception as e:
                print(f"Broadcast error: {e}")
            
            await asyncio.sleep(1.0)

    def _get_latest_metric(self, raw_entries: list, metric_key: str) -> float:
        """Extract the latest value of a metric from Redis Stream entries."""
        if raw_entries:
            entry_id, fields = raw_entries[0]
            return float(fields.get(metric_key.encode(), 0))
        return 0.0

    def _compute_trend(self, pred: dict) -> str:
        """Determine trend direction from forecast data."""
        try:
            forecast = json.loads(pred.get(b"latency_forecast", b"[]"))
            if len(forecast) >= 2:
                first_half = sum(forecast[:len(forecast)//2]) / (len(forecast)//2)
                second_half = sum(forecast[len(forecast)//2:]) / (len(forecast) - len(forecast)//2)
                diff = second_half - first_half
                if diff > 2.0:
                    return "degrading"
                elif diff < -2.0:
                    return "improving"
            return "stable"
        except (json.JSONDecodeError, ZeroDivisionError):
            return "stable"
