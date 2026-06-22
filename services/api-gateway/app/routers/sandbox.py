# services/api-gateway/app/routers/sandbox.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import redis.asyncio as redis
import json
import uuid

from app.config import get_settings

router = APIRouter(prefix="/api/v1/sandbox", tags=["Digital Twin Sandbox"])

settings = get_settings()
redis_client = redis.from_url(settings.redis_url)


class SandboxValidationRequest(BaseModel):
    source_link: str
    target_link: str
    traffic_classes: list[str]
    topology_override: Optional[dict] = None


class SandboxReportResponse(BaseModel):
    id: str
    result: str
    details: str
    loop_free: bool
    policy_compliant: bool
    reachability_verified: bool
    execution_time_ms: float


@router.post("/validate", response_model=SandboxReportResponse)
async def validate_in_sandbox(request: SandboxValidationRequest):
    """
    Run a proposed steering change through the Digital Twin sandbox.

    Performs:
    1. Batfish static analysis (loop detection, policy compliance)
    2. Mininet live traffic test (reachability verification)

    Target: Complete validation in <5 seconds.
    """
    report_id = str(uuid.uuid4())

    # Publish validation request for the Digital Twin service
    await redis_client.xadd("sandbox:requests", {
        "report_id": report_id,
        "source_link": request.source_link,
        "target_link": request.target_link,
        "traffic_classes": json.dumps(request.traffic_classes),
        "topology_override": json.dumps(request.topology_override or {}),
    })

    # In a real implementation, we'd await the result from the twin service.
    # For the API contract, return a pending report.
    return SandboxReportResponse(
        id=report_id,
        result="pending",
        details="Validation submitted to Digital Twin sandbox",
        loop_free=False,
        policy_compliant=False,
        reachability_verified=False,
        execution_time_ms=0.0,
    )


@router.get("/reports/{report_id}", response_model=SandboxReportResponse)
async def get_sandbox_report(report_id: str):
    """Retrieve a sandbox validation report by ID."""
    report = await redis_client.hgetall(f"sandbox:report:{report_id}")

    if not report:
        return SandboxReportResponse(
            id=report_id,
            result="not_found",
            details="Report not found or still pending",
            loop_free=False,
            policy_compliant=False,
            reachability_verified=False,
            execution_time_ms=0.0,
        )

    return SandboxReportResponse(
        id=report_id,
        result=report.get(b"result", b"unknown").decode(),
        details=report.get(b"details", b"").decode(),
        loop_free=report.get(b"loop_free", b"false").decode() == "true",
        policy_compliant=report.get(b"policy_compliant", b"false").decode() == "true",
        reachability_verified=report.get(b"reachability_verified", b"false").decode() == "true",
        execution_time_ms=float(report.get(b"execution_time_ms", 0)),
    )
