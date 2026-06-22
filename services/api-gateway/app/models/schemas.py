# services/api-gateway/app/models/schemas.py

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TelemetryPoint(BaseModel):
    """Schema for a single telemetry data point."""
    timestamp: float
    link_id: str
    latency_ms: float = Field(ge=0, description="One-way latency in milliseconds")
    jitter_ms: float = Field(ge=0, description="Jitter in milliseconds")
    packet_loss_pct: float = Field(ge=0, le=100, description="Packet loss percentage")
    bandwidth_util_pct: float = Field(ge=0, le=100, description="Bandwidth utilization %")
    rtt_ms: float = Field(ge=0, description="Round-trip time in milliseconds")


class PredictionResponse(BaseModel):
    """Schema for LSTM prediction output."""
    link_id: str
    health_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    latency_forecast: list[float] = Field(description="30-step latency forecast")
    jitter_forecast: list[float] = Field(description="30-step jitter forecast")
    packet_loss_forecast: list[float] = Field(description="30-step packet loss forecast")
    timestamp: str


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


class LinkHealth(BaseModel):
    """Schema for real-time link health data pushed via WebSocket."""
    health_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    latency_current: float
    jitter_current: float
    packet_loss_current: float
    latency_forecast: list[float]
    trend: TrendDirection


class SteeringAction(str, Enum):
    HOLD = "hold"
    PREEMPTIVE_SHIFT = "shift"
    EMERGENCY_FAILOVER = "failover"
    REBALANCE = "rebalance"


class SteeringDecisionSchema(BaseModel):
    """Schema for a steering decision."""
    action: SteeringAction
    source_link: str
    target_link: str
    traffic_classes: list[str]
    confidence: float = Field(ge=0, le=1)
    reason: str
    requires_sandbox_validation: bool


class ValidationResult(str, Enum):
    PASS = "pass"
    FAIL_LOOP_DETECTED = "fail_loop"
    FAIL_POLICY_VIOLATION = "fail_policy"
    FAIL_UNREACHABLE = "fail_unreachable"
    FAIL_TIMEOUT = "fail_timeout"


class SandboxReportSchema(BaseModel):
    """Schema for a sandbox validation report."""
    result: ValidationResult
    details: str
    loop_free: bool
    policy_compliant: bool
    reachability_verified: bool
    execution_time_ms: float
    topology_snapshot: Optional[dict] = None


class PolicyRuleSchema(BaseModel):
    """Schema for a network policy rule."""
    name: str
    traffic_class: str
    priority: int = Field(ge=0, le=65535)
    bandwidth_guarantee_mbps: Optional[float] = None
    latency_max_ms: Optional[float] = None
    action: str
    target_links: list[str]
