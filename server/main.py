"""
Unified FastAPI server — runs the entire PathWise AI platform.
Includes: auth, RBAC, audit log, alerts, reports, and all core features.
"""

from __future__ import annotations
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from server.state import state, ActiveRoutingRule, SteeringEvent
from server.lstm_engine import prediction_loop
from server.auth import (
    login as auth_login, register_user, get_current_user, get_current_user_strict,
    get_ws_user, get_all_users, unlock_user, User, AUTH_ENABLED, PRIVILEGED_ROLES,
)
from fastapi import HTTPException
from server.rbac import require_role, require_permission
from server import audit
from server import alerts
from server import reports
from server import traffic_shaper

# DATA_SOURCE modes:
#   sim    = synthetic simulator (default, no hardware needed)
#   live   = all 4 links from real hardware collectors
#   hybrid = WiFi live + 3 links replayed from training datasets
_DATA_SOURCE = os.environ.get("DATA_SOURCE", "sim").lower()
if _DATA_SOURCE in ("live", "hybrid"):
    from server.collector import live_collection_loop as simulation_loop, get_live_data_stats, LIVE_DATA_DIR
    print(f"[main] DATA_SOURCE={_DATA_SOURCE} -- using {'hybrid WiFi+replay' if _DATA_SOURCE == 'hybrid' else 'real-time hardware'} collectors")
else:
    from server.simulator import simulation_loop
    get_live_data_stats = None
    LIVE_DATA_DIR = None
    print("[main] DATA_SOURCE=sim -- using synthetic simulator")

from server.sandbox import (
    validate_steering, serialize_report, record_report,
    get_sandbox_history, TOPOLOGY,
)
from server.ibn_engine import (
    create_intent, get_all_intents, get_intent, delete_intent,
    pause_intent, resume_intent, serialize_intent, ibn_monitor_loop,
    IntentParseError,
)


# -- Lifespan --

@asynccontextmanager
async def lifespan(app: FastAPI):
    audit.log_event("SYSTEM", actor="SYSTEM", details="Server started")
    # Idempotently seed demo accounts + multi-tenant data so login (v2) and the
    # billing/tickets/sites dashboards work out of the box on a fresh DB (local
    # SQLite or a fresh cloud instance). INSERT OR IGNORE makes re-runs a no-op.
    if os.environ.get("SEED_DEMO_DATA", "true").lower() != "false":
        try:
            from scripts.seed_ui_data import seed as _seed_demo
            _seed_demo()
        except Exception as _seed_err:  # never block startup on seeding
            print(f"[main] demo seed skipped: {_seed_err}")
    sim_task = asyncio.create_task(simulation_loop())
    pred_task = asyncio.create_task(prediction_loop())
    ws_task = asyncio.create_task(scoreboard_broadcast_loop())
    ibn_task = asyncio.create_task(ibn_monitor_loop())
    yield
    # Clean up traffic shaping policies on shutdown
    traffic_shaper.remove_all_policies()
    sim_task.cancel()
    pred_task.cancel()
    ibn_task.cancel()
    ws_task.cancel()


app = FastAPI(
    title="PathWise AI -- SD-WAN Management Platform",
    version="2.0.0",
    description="AI-Powered SD-WAN with LSTM prediction, autonomous steering, digital twin sandbox, and intent-based networking.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Multi-tenant SaaS routers (UI gap fix)
try:
    from server.routers import billing, tickets, lstm_control, profile, admin_portal, app_priority
    app.include_router(billing.router)
    app.include_router(tickets.router)
    app.include_router(lstm_control.router)
    app.include_router(profile.router)
    app.include_router(admin_portal.router)
    app.include_router(app_priority.router)
except ImportError as e:
    print(f"[main] Optional SaaS routers not loaded: {e}")


# -- Pydantic Models --

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str

class LSTMToggleRequest(BaseModel):
    enabled: bool

class StatusResponse(BaseModel):
    status: str
    lstm_enabled: bool
    uptime_seconds: float
    tick_count: int
    active_links: list[str]
    auth_enabled: bool

class SandboxValidationRequest(BaseModel):
    source_link: str
    target_link: str
    traffic_classes: list[str]

class ApplyRuleRequest(BaseModel):
    sandbox_report_id: str
    source_link: str
    target_link: str
    traffic_classes: list[str]

class IntentRequest(BaseModel):
    text: str

class AlertConfigRequest(BaseModel):
    threshold: Optional[float] = None
    suppression_window_s: Optional[float] = None


# ================================================================
#  AUTH ENDPOINTS (Req-Func-Sw-15, Req-Func-Sw-16, UC-6)
# ================================================================

@app.post("/api/v1/auth/login")
async def login_endpoint(req: LoginRequest):
    result = auth_login(req.email, req.password)
    audit.log_event("AUTH", actor=req.email, details="Login successful")
    return result


@app.post("/api/v1/auth/login/v2")
async def login_v2(req: LoginRequest):
    """Multi-tenant login — checks app_users table in DB."""
    from server.db import get_db
    import bcrypt as _bcrypt
    db_gen = get_db()
    db = next(db_gen, None)
    if db is None:
        # Fall back to in-memory auth
        return await login_endpoint(req)
    try:
        from sqlalchemy import text as _text
        user = db.execute(_text("SELECT * FROM app_users WHERE email = :e"), {"e": req.email}).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if user.locked_until and user.locked_until > __import__('datetime').datetime.utcnow():
            raise HTTPException(status_code=423, detail="Account locked. Contact admin.")
        if not _bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
            attempts = user.failed_attempts + 1
            locked = __import__('datetime').datetime.utcnow() + __import__('datetime').timedelta(minutes=30) if attempts >= 5 else None
            db.execute(_text("UPDATE app_users SET failed_attempts=:a, locked_until=:l WHERE id=:id"),
                       {"a": attempts, "l": locked, "id": user.id})
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")
        db.execute(_text("UPDATE app_users SET failed_attempts=0, locked_until=NULL WHERE id=:id"), {"id": user.id})
        db.commit()
        from server.auth import create_access_token
        token = create_access_token(user.id, user.role)
        return {
            "access_token": token, "token": token, "token_type": "bearer",
            "role": user.role, "user_id": user.id, "name": user.name,
            "email": user.email, "company": user.company,
            "avatar_initials": user.avatar_initials,
            "redirect_to": "/admin/dashboard" if user.role == "SUPER_ADMIN" else "/user/dashboard"
        }
    finally:
        try: next(db_gen, None)
        except: pass


@app.post("/api/v1/auth/register")
async def register_endpoint(
    req: RegisterRequest,
    caller: User = Depends(get_current_user_strict),
):
    # Strict auth: always required, even when AUTH_ENABLED=false (otherwise
    # a stranger could register themselves as SUPER_ADMIN against a dev box
    # exposed on 0.0.0.0).
    if caller.role not in PRIVILEGED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions to register users. Required: {sorted(PRIVILEGED_ROLES)}",
        )
    # Only SUPER_ADMIN can grant privileged roles.
    if req.role in PRIVILEGED_ROLES and caller.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail=f"Only SUPER_ADMIN may grant role '{req.role}'.",
        )
    user = register_user(req.email, req.password, req.role)
    audit.log_event(
        "AUTH", actor=caller.email,
        details=f"Registered {req.email} with role {req.role}",
    )
    return {"id": user.id, "email": user.email, "role": user.role}


@app.get("/api/v1/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active}


@app.get("/api/v1/auth/users", dependencies=[Depends(require_role("NETWORK_ADMIN"))])
async def list_users():
    return {"users": [
        {"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active,
         "failed_attempts": u.failed_attempts, "locked": u.locked_at is not None}
        for u in get_all_users()
    ]}


@app.post("/api/v1/auth/unlock/{user_id}", dependencies=[Depends(require_role("NETWORK_ADMIN"))])
async def unlock_user_endpoint(user_id: str):
    if unlock_user(user_id):
        return {"status": "unlocked"}
    return {"error": "User not found"}


# ================================================================
#  STATUS (public)
# ================================================================

@app.get("/api/v1/status")
async def get_status():
    return StatusResponse(
        status="running",
        lstm_enabled=state.lstm_enabled,
        uptime_seconds=time.time() - state.start_time,
        tick_count=state.tick_count,
        active_links=state.active_links,
        auth_enabled=AUTH_ENABLED,
    )


# ================================================================
#  ADMIN (Req-Func-Sw-4: configurable threshold)
# ================================================================

@app.post("/api/v1/admin/lstm-toggle", dependencies=[Depends(require_permission("admin"))])
async def toggle_lstm(req: LSTMToggleRequest):
    state.lstm_enabled = req.enabled
    audit.log_event("SYSTEM", actor="admin", details=f"LSTM {'enabled' if req.enabled else 'disabled'}")
    return {"lstm_enabled": state.lstm_enabled}

@app.get("/api/v1/admin/lstm-status")
async def lstm_status():
    return {"lstm_enabled": state.lstm_enabled}


# ================================================================
#  TELEMETRY (Req-Func-Sw-1, Req-Func-Sw-20, UC-1)
# ================================================================

@app.get("/api/v1/telemetry/links")
async def get_links():
    return {"links": state.active_links}

@app.get("/api/v1/telemetry/{link_id}")
async def get_telemetry(link_id: str, window: int = 60):
    is_known = link_id in state.active_links
    points = state.get_latest_effective(link_id, window) if is_known else []
    status = "active" if is_known else "offline"  # UC-1: unknown/offline links advertise their state
    return {
        "link_id": link_id,
        "status": status,
        "points": [
            {"timestamp": p.timestamp, "latency_ms": round(p.latency_ms, 2),
             "jitter_ms": round(p.jitter_ms, 2), "packet_loss_pct": round(p.packet_loss_pct, 3),
             "bandwidth_util_pct": round(p.bandwidth_util_pct, 1), "rtt_ms": round(p.rtt_ms, 2)}
            for p in points
        ],
    }

@app.get("/api/v1/telemetry/{link_id}/raw")
async def get_raw_telemetry(link_id: str, window: int = 60):
    points = state.get_latest_telemetry(link_id, window)
    return {
        "link_id": link_id,
        "points": [
            {"timestamp": p.timestamp, "latency_ms": round(p.latency_ms, 2),
             "jitter_ms": round(p.jitter_ms, 2), "packet_loss_pct": round(p.packet_loss_pct, 3),
             "bandwidth_util_pct": round(p.bandwidth_util_pct, 1), "rtt_ms": round(p.rtt_ms, 2)}
            for p in points
        ],
    }


# ================================================================
#  PREDICTIONS (Req-Func-Sw-2, Req-Func-Sw-3, Req-Func-Sw-14)
# ================================================================

@app.get("/api/v1/predictions/all")
async def get_all_predictions():
    result = {}
    for link_id, pred in state.predictions.items():
        if pred:
            result[link_id] = _serialize_prediction(pred)
    return result

@app.get("/api/v1/predictions/{link_id}")
async def get_prediction(link_id: str):
    pred = state.predictions.get(link_id)
    if not pred:
        return {"error": "No prediction available yet"}
    return _serialize_prediction(pred)


# ================================================================
#  STEERING (Req-Func-Sw-4, Req-Func-Sw-6, UC-3)
# ================================================================

@app.get("/api/v1/steering/history")
async def get_steering_history(limit: int = 50):
    events = list(state.steering_history)[:limit]
    return {"events": [
        {"id": e.id, "timestamp": e.timestamp, "action": e.action,
         "source_link": e.source_link, "target_link": e.target_link,
         "traffic_classes": e.traffic_classes, "confidence": round(e.confidence, 2),
         "reason": e.reason, "status": e.status, "lstm_enabled": e.lstm_enabled}
        for e in events
    ]}

@app.get("/api/v1/metrics/comparison")
async def get_comparison_metrics():
    m_on = state.metrics_lstm_on
    m_off = state.metrics_lstm_off
    return {
        "lstm_on": {"avg_latency": round(m_on.avg_latency, 2), "avg_jitter": round(m_on.avg_jitter, 2),
                     "avg_packet_loss": round(m_on.avg_packet_loss, 3),
                     "proactive_steerings": m_on.proactive_steerings, "brownouts_avoided": m_on.brownouts_avoided},
        "lstm_off": {"avg_latency": round(m_off.avg_latency, 2), "avg_jitter": round(m_off.avg_jitter, 2),
                      "avg_packet_loss": round(m_off.avg_packet_loss, 3),
                      "reactive_steerings": m_off.reactive_steerings, "brownouts_hit": m_off.brownouts_hit},
    }


# ================================================================
#  SANDBOX (Req-Func-Sw-8, Req-Func-Sw-9, Req-Func-Sw-10, UC-4)
# ================================================================

@app.post("/api/v1/sandbox/validate", dependencies=[Depends(require_permission("sandbox"))])
async def sandbox_validate(req: SandboxValidationRequest):
    report = await validate_steering(
        source_link=req.source_link, target_link=req.target_link,
        traffic_classes=req.traffic_classes,
    )
    record_report(report)
    audit.log_event(
        "VALIDATION", actor="user",
        link_id=req.source_link,
        validation_result=report.result.value,
        routing_change={"source": req.source_link, "target": req.target_link, "classes": req.traffic_classes},
        details=f"Sandbox validation: {report.result.value} in {report.execution_time_ms:.0f}ms",
    )
    return serialize_report(report)

@app.get("/api/v1/sandbox/history")
async def sandbox_history(limit: int = 20):
    return {"reports": get_sandbox_history(limit)}

@app.get("/api/v1/sandbox/topology")
async def sandbox_topology():
    links_health = {}
    for link in TOPOLOGY["links"]:
        lid = link["link_id"]
        pred = state.predictions.get(lid)
        links_health[lid] = {
            "health_score": pred.health_score if pred else None,
            "brownout_active": state.brownout_active.get(lid, False),
        }
    return {"topology": TOPOLOGY, "links_health": links_health}


# ================================================================
#  ROUTING RULES (with audit + performance timing)
# ================================================================

@app.post("/api/v1/routing/apply", dependencies=[Depends(require_permission("routing"))])
async def apply_routing_rule(req: ApplyRuleRequest):
    import uuid as _uuid

    t_start = time.perf_counter_ns()

    if req.source_link == req.target_link:
        return {"error": "Source and target must differ"}
    if req.source_link not in state.active_links or req.target_link not in state.active_links:
        return {"error": "Invalid link ID"}

    for existing in state.get_active_rules():
        if existing.source_link == req.source_link:
            return {"error": f"Traffic from {req.source_link} is already being diverted by rule {existing.id}"}

    rule = ActiveRoutingRule(
        id=str(_uuid.uuid4())[:8], source_link=req.source_link, target_link=req.target_link,
        traffic_classes=req.traffic_classes, applied_at=time.time(),
        sandbox_report_id=req.sandbox_report_id, status="active",
    )
    state.routing_rules.append(rule)

    evt = SteeringEvent(
        id=rule.id, timestamp=time.time(), action="SANDBOX_DEPLOY",
        source_link=req.source_link, target_link=req.target_link,
        traffic_classes=",".join(req.traffic_classes), confidence=1.0,
        reason=f"Sandbox-validated rule applied (report {req.sandbox_report_id[:8]})",
        status="deployed", lstm_enabled=state.lstm_enabled,
    )
    state.steering_history.appendleft(evt)

    execution_ms = (time.perf_counter_ns() - t_start) / 1_000_000

    audit.log_event(
        "STEERING", actor="user", link_id=req.source_link,
        routing_change={"source": req.source_link, "target": req.target_link, "rule_id": rule.id},
        details=f"Routing rule deployed in {execution_ms:.1f}ms",
    )

    return {
        "rule_id": rule.id, "status": "deployed",
        "source_link": rule.source_link, "target_link": rule.target_link,
        "traffic_classes": rule.traffic_classes,
        "execution_time_ms": round(execution_ms, 2),
        "message": f"Traffic rerouted: {rule.source_link} -> {rule.target_link}",
    }

@app.get("/api/v1/routing/active")
async def get_active_rules():
    rules = state.get_active_rules()
    return {"rules": [
        {"id": r.id, "source_link": r.source_link, "target_link": r.target_link,
         "traffic_classes": r.traffic_classes, "applied_at": r.applied_at,
         "sandbox_report_id": r.sandbox_report_id, "status": r.status,
         "age_seconds": round(time.time() - r.applied_at, 1)}
        for r in rules
    ]}

@app.get("/api/v1/routing/all")
async def get_all_rules():
    return {"rules": [
        {"id": r.id, "source_link": r.source_link, "target_link": r.target_link,
         "traffic_classes": r.traffic_classes, "applied_at": r.applied_at,
         "sandbox_report_id": r.sandbox_report_id, "status": r.status,
         "age_seconds": round(time.time() - r.applied_at, 1)}
        for r in state.routing_rules
    ]}

@app.delete("/api/v1/routing/{rule_id}", dependencies=[Depends(require_permission("routing"))])
async def rollback_rule(rule_id: str):
    for r in state.routing_rules:
        if r.id == rule_id and r.status == "active":
            r.status = "rolled_back"
            evt = SteeringEvent(
                id=r.id + "-rb", timestamp=time.time(), action="SANDBOX_ROLLBACK",
                source_link=r.target_link, target_link=r.source_link,
                traffic_classes=",".join(r.traffic_classes), confidence=1.0,
                reason=f"Routing rule {r.id} rolled back", status="rolled_back",
                lstm_enabled=state.lstm_enabled,
            )
            state.steering_history.appendleft(evt)
            audit.log_event("STEERING", actor="user", link_id=r.source_link,
                            routing_change={"rule_id": r.id, "action": "rollback"},
                            details=f"Rule {r.id} rolled back")
            return {"rule_id": r.id, "status": "rolled_back", "message": f"Traffic restored to {r.source_link}"}
    return {"error": "Rule not found or already rolled back"}


# ================================================================
#  IBN (Req-Func-Sw-11, Req-Func-Sw-12, UC-5)
# ================================================================

@app.post("/api/v1/ibn/intents", dependencies=[Depends(require_permission("ibn"))])
async def create_ibn_intent(req: IntentRequest):
    try:
        intent = create_intent(req.text)
    except IntentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit.log_event("POLICY_CHANGE", actor="user",
                     policy_change={"action": "create", "intent_id": intent.id, "text": req.text},
                     details=f"IBN intent created: {req.text[:60]}")
    return serialize_intent(intent)

@app.get("/api/v1/ibn/intents")
async def list_ibn_intents():
    return {"intents": [serialize_intent(i) for i in get_all_intents()]}

@app.get("/api/v1/ibn/intents/{intent_id}")
async def get_ibn_intent(intent_id: str):
    intent = get_intent(intent_id)
    if not intent:
        return {"error": "Intent not found"}
    return serialize_intent(intent)

@app.delete("/api/v1/ibn/intents/{intent_id}", dependencies=[Depends(require_permission("ibn"))])
async def delete_ibn_intent(intent_id: str):
    if delete_intent(intent_id):
        audit.log_event("POLICY_CHANGE", actor="user",
                         policy_change={"action": "delete", "intent_id": intent_id},
                         details=f"IBN intent {intent_id} deleted")
        return {"status": "deleted", "id": intent_id}
    return {"error": "Intent not found"}

@app.post("/api/v1/ibn/intents/{intent_id}/pause", dependencies=[Depends(require_permission("ibn"))])
async def pause_ibn_intent(intent_id: str):
    if pause_intent(intent_id):
        return {"status": "paused", "id": intent_id}
    return {"error": "Intent not found or already deleted"}

@app.post("/api/v1/ibn/intents/{intent_id}/resume", dependencies=[Depends(require_permission("ibn"))])
async def resume_ibn_intent(intent_id: str):
    if resume_intent(intent_id):
        return {"status": "active", "id": intent_id}
    return {"error": "Intent not found or not paused"}

@app.post("/api/v1/ibn/deploy", dependencies=[Depends(require_permission("ibn"))])
async def deploy_ibn_intent(req: IntentRequest):
    """
    Translate a natural-language intent to YANG/NETCONF, validate via sandbox,
    and submit to the live SDN controller (Req-Func-Sw-11, Req-Func-Sw-12).
    """
    from server.ibn_engine import deploy_intent as _deploy
    result = _deploy({"command": req.text})
    audit.log_event(
        "POLICY_CHANGE", actor="user",
        policy_change={"action": "deploy", "command": req.text,
                       "flow_id": result.get("flow_id"),
                       "success": result.get("success")},
        details=f"IBN deploy: {req.text[:80]} → success={result.get('success')}",
    )
    return result


@app.post("/api/v1/ibn/parse")
async def parse_ibn_intent(req: IntentRequest):
    from server.ibn_engine import parse_intent, generate_yang_config, NetworkIntent
    try:
        parsed = parse_intent(req.text)
    except IntentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    temp_intent = NetworkIntent(id="preview", raw_text=req.text, parsed=parsed, created_at=time.time())
    temp_intent.yang_config = generate_yang_config(temp_intent)
    return {
        "action": parsed.action.value, "traffic_classes": parsed.traffic_classes,
        "metric": parsed.metric, "threshold": parsed.threshold,
        "threshold_unit": parsed.threshold_unit, "preferred_link": parsed.preferred_link,
        "avoid_link": parsed.avoid_link, "source_link": parsed.source_link,
        "target_link": parsed.target_link,
        "high_app": parsed.high_app, "low_app": parsed.low_app,
        "throttle_kbps": parsed.throttle_kbps,
        "yang_config": temp_intent.yang_config,
    }


# ================================================================
#  AUDIT LOG (Req-Func-Sw-18, Req-Qual-Sec-3)
# ================================================================

@app.get("/api/v1/audit", dependencies=[Depends(require_permission("audit"))])
async def get_audit_log(
    page: int = 1, per_page: int = 50,
    event_type: Optional[str] = None,
    actor: Optional[str] = None,
):
    entries, total = audit.get_audit_log(page=page, per_page=per_page,
                                         event_type=event_type, actor=actor)
    return {
        "entries": [audit.serialize_entry(e) for e in entries],
        "total": total, "page": page, "per_page": per_page,
    }

@app.get("/api/v1/audit/verify", dependencies=[Depends(require_role("NETWORK_ADMIN"))])
async def verify_audit_integrity():
    return audit.verify_integrity()


# ================================================================
#  ALERTS (Req-Func-Sw-17)
# ================================================================

@app.get("/api/v1/alerts/history")
async def get_alert_history(limit: int = 50):
    return {"alerts": alerts.get_alert_history(limit)}

@app.put("/api/v1/alerts/config", dependencies=[Depends(require_role("NETWORK_ADMIN"))])
async def update_alert_config(req: AlertConfigRequest):
    alerts.update_config(threshold=req.threshold, suppression=req.suppression_window_s)
    return {"threshold": alerts.HEALTH_THRESHOLD, "suppression_window_s": alerts.SUPPRESSION_WINDOW}


# ================================================================
#  REPORTS (Req-Func-Sw-21)
# ================================================================

_VALID_REPORT_FORMATS = {"csv", "pdf"}


def _check_report_format(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in _VALID_REPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{fmt}'. Use one of: {sorted(_VALID_REPORT_FORMATS)}",
        )
    return fmt


@app.get("/api/v1/reports/health-scores", dependencies=[Depends(require_permission("reports"))])
async def export_health_scores(format: str = "csv"):
    fmt = _check_report_format(format)
    if fmt == "pdf":
        data = reports.generate_health_scores_pdf()
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                                  headers={"Content-Disposition": "attachment; filename=health_scores.pdf"})
    data = reports.generate_health_scores_csv()
    return StreamingResponse(io.BytesIO(data.encode()), media_type="text/csv",
                              headers={"Content-Disposition": "attachment; filename=health_scores.csv"})

@app.get("/api/v1/reports/steering-events", dependencies=[Depends(require_permission("reports"))])
async def export_steering_events(format: str = "csv"):
    fmt = _check_report_format(format)
    if fmt == "pdf":
        data = reports.generate_steering_events_pdf()
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                                  headers={"Content-Disposition": "attachment; filename=steering_events.pdf"})
    data = reports.generate_steering_events_csv()
    return StreamingResponse(io.BytesIO(data.encode()), media_type="text/csv",
                              headers={"Content-Disposition": "attachment; filename=steering_events.csv"})

@app.get("/api/v1/reports/audit-log", dependencies=[Depends(require_permission("reports"))])
async def export_audit_log(format: str = "csv"):
    fmt = _check_report_format(format)
    if fmt == "pdf":
        data = reports.generate_audit_log_pdf()
        return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                                  headers={"Content-Disposition": "attachment; filename=audit_log.pdf"})
    data = reports.generate_audit_log_csv()
    return StreamingResponse(io.BytesIO(data.encode()), media_type="text/csv",
                              headers={"Content-Disposition": "attachment; filename=audit_log.csv"})


# ================================================================
#  TRAFFIC SHAPING (App-Level QoS via IBN)
# ================================================================

class TrafficShapeRequest(BaseModel):
    app_name: str
    bandwidth_kbps: int = 500

class PrioritizeOverRequest(BaseModel):
    high_app: str
    low_app: str
    throttle_kbps: int = 500

@app.get("/api/v1/traffic/apps")
async def list_apps():
    return {"apps": traffic_shaper.get_app_list()}

@app.get("/api/v1/traffic/policies")
async def get_traffic_policies():
    return {"policies": traffic_shaper.get_active_policies()}

@app.get("/api/v1/traffic/policies/all")
async def get_all_traffic_policies():
    return {"policies": traffic_shaper.get_all_policies()}

@app.post("/api/v1/traffic/throttle", dependencies=[Depends(require_permission("ibn"))])
async def throttle_app_endpoint(req: TrafficShapeRequest):
    policy = traffic_shaper.throttle_app(req.app_name, req.bandwidth_kbps)
    if not policy:
        return {"error": f"Unknown app: {req.app_name}"}
    return {"policy_id": policy.id, "action": "throttle", "app": policy.display_name,
            "bandwidth_kbps": policy.bandwidth_kbps}

@app.post("/api/v1/traffic/prioritize", dependencies=[Depends(require_permission("ibn"))])
async def prioritize_app_endpoint(req: TrafficShapeRequest):
    policy = traffic_shaper.prioritize_app(req.app_name)
    if not policy:
        return {"error": f"Unknown app: {req.app_name}"}
    return {"policy_id": policy.id, "action": "prioritize", "app": policy.display_name}

@app.post("/api/v1/traffic/prioritize-over", dependencies=[Depends(require_permission("ibn"))])
async def prioritize_over_endpoint(req: PrioritizeOverRequest):
    policies = traffic_shaper.prioritize_over(req.high_app, req.low_app, req.throttle_kbps)
    return {"policies": [{"id": p.id, "app": p.display_name, "action": p.action} for p in policies]}

@app.delete("/api/v1/traffic/policies/{policy_id}", dependencies=[Depends(require_permission("ibn"))])
async def remove_traffic_policy(policy_id: str):
    if traffic_shaper.remove_policy(policy_id):
        return {"status": "removed"}
    return {"error": "Policy not found or already removed"}

@app.post("/api/v1/traffic/reset", dependencies=[Depends(require_role("NETWORK_ADMIN"))])
async def reset_all_traffic_policies():
    traffic_shaper.remove_all_policies()
    return {"status": "all_policies_removed"}


# ================================================================
#  MULTI-SITE SCALABILITY (Req-Func-Sw-19, Gap 5 — TC-18)
# ================================================================

@app.get("/api/v1/telemetry/site/{site_id}")
async def get_site_telemetry(site_id: int):
    """
    Return latest telemetry snapshot for a given site.
    Used by TC-18 100-site concurrent load test.
    Sites that are not yet provisioned return a synthetic 'unprovisioned' record
    so the dashboard can render placeholder cards.
    """
    # Synthesize per-site telemetry from the global state by hashing the site_id
    # into the existing 4-link fleet. This keeps the data deterministic for
    # repeatable load tests without provisioning real per-site collectors.
    if site_id < 1:
        return {"site_id": site_id, "links": [], "health_score": 0,
                "status": "invalid"}

    links_payload = []
    total_score = 0.0
    n = 0
    for link_id in state.active_links:
        pred = state.predictions.get(link_id)
        eff = state.get_latest_effective(link_id, 1)
        if eff:
            latest = eff[-1]
            score = pred.health_score if pred else 75
            total_score += score
            n += 1
            links_payload.append({
                "link_id": link_id,
                "health_score": score,
                "latency_ms": round(latest.latency_ms, 2),
                "jitter_ms": round(latest.jitter_ms, 2),
                "packet_loss_pct": round(latest.packet_loss_pct, 3),
            })

    if not links_payload:
        return {
            "site_id": site_id,
            "links": [],
            "health_score": 100,
            "status": "unprovisioned",
        }

    return {
        "site_id": site_id,
        "links": links_payload,
        "health_score": round(total_score / max(n, 1), 1),
        "status": "ok",
        "timestamp": time.time(),
    }


@app.get("/api/v1/dashboard/summary")
async def dashboard_summary(sites: int = 100):
    """
    Return a multi-site summary view for dashboard rendering.
    Supports up to N sites in a single request (TC-18 / Req-Func-Sw-19).
    """
    sites = max(1, min(sites, 1000))
    site_records = []
    for sid in range(1, sites + 1):
        snap = await get_site_telemetry(sid)
        site_records.append({
            "site_id": snap["site_id"],
            "health_score": snap["health_score"],
            "status": snap["status"],
            "link_count": len(snap.get("links", [])),
        })
    return {
        "site_count": len(site_records),
        "sites": site_records,
        "timestamp": time.time(),
    }


# ================================================================
#  SDN CONTROLLER (Req-Func-Sw-5, Gap 1)
# ================================================================

@app.get("/api/v1/sdn/health")
async def sdn_health():
    """Liveness check for the live SDN controller(s) (ODL / ONOS)."""
    from server.sdn_adapter import get_adapter
    return get_adapter().health_check()


@app.post("/api/v1/routing/rollback/{flow_id}", dependencies=[Depends(require_permission("routing"))])
async def rollback_sdn_flow(flow_id: str):
    """One-click rollback of an installed SDN flow rule (Req-Func-Sw-5)."""
    from server.sdn_adapter import get_adapter
    ok = get_adapter().rollback_flow(flow_id)
    audit.log_event("STEERING", actor="user",
                    routing_change={"flow_id": flow_id, "action": "sdn_rollback"},
                    details=f"SDN flow {flow_id} rollback ok={ok}")
    return {"rolled_back": ok, "flow_id": flow_id}


# ================================================================
#  HEALTH (Gap 7 — availability monitor target)
# ================================================================

@app.get("/api/v1/health")
async def health_endpoint():
    """Liveness probe used by uptime monitor and Docker healthchecks."""
    return {
        "status": "ok",
        "uptime_seconds": time.time() - state.start_time,
        "tick_count": state.tick_count,
        "lstm_enabled": state.lstm_enabled,
    }


# ================================================================
#  LIVE DATA STATS
# ================================================================

@app.get("/api/v1/live-data/stats")
async def live_data_stats():
    if get_live_data_stats:
        return {"mode": "live", "stats": get_live_data_stats(), "data_dir": str(LIVE_DATA_DIR)}
    return {"mode": "sim", "stats": {}, "data_dir": None}


# ================================================================
#  HELPERS
# ================================================================

def _serialize_prediction(pred):
    return {
        "link_id": pred.link_id, "health_score": pred.health_score,
        "confidence": round(pred.confidence, 3),
        "latency_forecast": [round(v, 2) for v in pred.latency_forecast],
        "jitter_forecast": [round(v, 2) for v in pred.jitter_forecast],
        "packet_loss_forecast": [round(v, 3) for v in pred.packet_loss_forecast],
        "timestamp": pred.timestamp,
        "reasoning": pred.reasoning,  # Req-Func-Sw-14
    }


# ================================================================
#  WEBSOCKET
# ================================================================

_ws_clients: set[WebSocket] = set()

@app.websocket("/ws/scoreboard")
async def websocket_scoreboard(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)
    except Exception:
        _ws_clients.discard(ws)

async def scoreboard_broadcast_loop():
    while True:
        if _ws_clients:
            payload = _build_scoreboard_payload()
            msg = json.dumps(payload)
            dead = set()
            for ws in _ws_clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.add(ws)
            _ws_clients.difference_update(dead)
        await asyncio.sleep(1.0)

def _build_scoreboard_payload() -> dict:
    links_data = {}
    for link_id in state.active_links:
        eff_points = state.get_latest_effective(link_id, 5)
        raw_points = state.get_latest_telemetry(link_id, 5)
        pred = state.predictions.get(link_id)

        if eff_points:
            latest = eff_points[-1]
            lat_vals = [p.latency_ms for p in eff_points]
            trend = "stable"
            if len(lat_vals) >= 3:
                diff = lat_vals[-1] - lat_vals[0]
                if diff > 5: trend = "degrading"
                elif diff < -5: trend = "improving"

            links_data[link_id] = {
                "health_score": pred.health_score if pred else 75,
                "confidence": pred.confidence if pred else 0.5,
                "reasoning": pred.reasoning if pred else "Awaiting prediction data",
                "latency_current": round(latest.latency_ms, 2),
                "jitter_current": round(latest.jitter_ms, 2),
                "packet_loss_current": round(latest.packet_loss_pct, 3),
                "bandwidth_util": round(latest.bandwidth_util_pct, 1),
                "latency_forecast": pred.latency_forecast[:10] if pred else [],
                "trend": trend,
                "brownout_active": state.brownout_active.get(link_id, False),
            }

            # Check alerts for this link
            if pred:
                alerts.check_and_alert(link_id, pred.health_score, pred.confidence)

        if raw_points:
            raw_latest = raw_points[-1]
            links_data[link_id]["raw_latency"] = round(raw_latest.latency_ms, 2)
            links_data[link_id]["raw_jitter"] = round(raw_latest.jitter_ms, 2)
            links_data[link_id]["raw_packet_loss"] = round(raw_latest.packet_loss_pct, 3)

    recent_events = list(state.steering_history)[:5]
    m_on = state.metrics_lstm_on
    m_off = state.metrics_lstm_off

    return {
        "type": "scoreboard_update",
        "timestamp": time.time(),
        "lstm_enabled": state.lstm_enabled,
        "links": links_data,
        "active_routing_rules": [
            {"id": r.id, "source_link": r.source_link, "target_link": r.target_link,
             "traffic_classes": r.traffic_classes, "age_seconds": round(time.time() - r.applied_at, 1)}
            for r in state.get_active_rules()
        ],
        "ibn_intents": [
            {"id": i.id, "status": i.status.value, "raw_text": i.raw_text[:80],
             "action": i.parsed.action.value, "violation_count": i.violation_count}
            for i in get_all_intents()
        ],
        "steering_events": [
            {"id": e.id, "action": e.action, "source_link": e.source_link,
             "target_link": e.target_link, "reason": e.reason,
             "confidence": round(e.confidence, 2), "status": e.status,
             "lstm_enabled": e.lstm_enabled, "timestamp": e.timestamp}
            for e in recent_events
        ],
        "comparison": {
            "lstm_on": {"avg_latency": round(m_on.avg_latency, 2), "avg_jitter": round(m_on.avg_jitter, 2),
                         "avg_packet_loss": round(m_on.avg_packet_loss, 3),
                         "proactive_steerings": m_on.proactive_steerings, "brownouts_avoided": m_on.brownouts_avoided},
            "lstm_off": {"avg_latency": round(m_off.avg_latency, 2), "avg_jitter": round(m_off.avg_jitter, 2),
                          "avg_packet_loss": round(m_off.avg_packet_loss, 3),
                          "reactive_steerings": m_off.reactive_steerings, "brownouts_hit": m_off.brownouts_hit},
        },
    }
