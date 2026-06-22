"""
In-memory state management — replaces Redis + TimescaleDB for offline operation.
All state is held in Python data structures and accessed via simple functions.
"""

from __future__ import annotations
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TelemetryPoint:
    timestamp: float
    link_id: str
    latency_ms: float
    jitter_ms: float
    packet_loss_pct: float
    bandwidth_util_pct: float
    rtt_ms: float


@dataclass
class LinkPrediction:
    link_id: str
    health_score: float
    confidence: float
    latency_forecast: list[float]
    jitter_forecast: list[float]
    packet_loss_forecast: list[float]
    timestamp: float
    reasoning: str = ""  # Human-readable explanation (Req-Func-Sw-14)


@dataclass
class SteeringEvent:
    id: str
    timestamp: float
    action: str
    source_link: str
    target_link: str
    traffic_classes: str
    confidence: float
    reason: str
    status: str
    lstm_enabled: bool


@dataclass
class ComparisonMetrics:
    avg_latency: float = 0.0
    avg_jitter: float = 0.0
    avg_packet_loss: float = 0.0
    total_steerings: int = 0
    proactive_steerings: int = 0
    reactive_steerings: int = 0
    brownouts_avoided: int = 0
    brownouts_hit: int = 0


@dataclass
class ActiveRoutingRule:
    id: str
    source_link: str
    target_link: str
    traffic_classes: list[str]
    applied_at: float
    sandbox_report_id: str
    status: str = "active"  # "active" | "rolled_back"


class AppState:
    """Central in-memory state for the entire application."""

    def __init__(self):
        self.lstm_enabled: bool = False

        # DATA_SOURCE=hybrid adds "wifi" as a live link alongside 3 replayed links
        import os
        data_source = os.environ.get("DATA_SOURCE", "sim").lower()
        if data_source == "hybrid":
            self.active_links: list[str] = [
                "fiber-primary",
                "5g-mobile",
                "satellite-backup",
                "wifi",
            ]
        else:
            self.active_links: list[str] = [
                "fiber-primary",
                "broadband-secondary",
                "satellite-backup",
                "5g-mobile",
            ]

        self.telemetry: dict[str, deque[TelemetryPoint]] = {
            link: deque(maxlen=300) for link in self.active_links
        }

        self.effective_telemetry: dict[str, deque[TelemetryPoint]] = {
            link: deque(maxlen=300) for link in self.active_links
        }

        self.predictions: dict[str, Optional[LinkPrediction]] = {
            link: None for link in self.active_links
        }

        self.steering_history: deque[SteeringEvent] = deque(maxlen=200)

        self.metrics_lstm_on = ComparisonMetrics()
        self.metrics_lstm_off = ComparisonMetrics()

        self._lock = asyncio.Lock()

        self.start_time = time.time()
        self.tick_count = 0

        self.active_traffic_route: dict[str, str] = {}
        self.brownout_active: dict[str, bool] = {
            link: False for link in self.active_links
        }

        self.routing_rules: list[ActiveRoutingRule] = []

    def get_active_rules(self) -> list[ActiveRoutingRule]:
        return [r for r in self.routing_rules if r.status == "active"]

    def get_rules_affecting_link(self, link_id: str) -> list[ActiveRoutingRule]:
        return [
            r for r in self.routing_rules
            if r.status == "active" and (r.source_link == link_id or r.target_link == link_id)
        ]

    def is_traffic_diverted_from(self, link_id: str) -> bool:
        return any(
            r.source_link == link_id and r.status == "active"
            for r in self.routing_rules
        )

    def is_traffic_diverted_to(self, link_id: str) -> bool:
        return any(
            r.target_link == link_id and r.status == "active"
            for r in self.routing_rules
        )

    def get_latest_telemetry(self, link_id: str, count: int = 60) -> list[TelemetryPoint]:
        buf = self.telemetry.get(link_id, deque())
        items = list(buf)
        return items[-count:]

    def get_latest_effective(self, link_id: str, count: int = 60) -> list[TelemetryPoint]:
        buf = self.effective_telemetry.get(link_id, deque())
        items = list(buf)
        return items[-count:]


state = AppState()
