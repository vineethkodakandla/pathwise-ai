"""
REST API router for App Priority Switch.
Prefix: /api/v1/apps
"""

from __future__ import annotations

import asyncio
import os
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import jwt

from server.app_qos.signatures import APP_SIGNATURES, PRIORITY_CLASSES, get_all_app_ids
from server.app_qos.priority_manager import (
    get_active_apps,
    set_priorities,
    get_priorities,
    remove_app_priority,
    reset_all,
    get_quality_predictions,
    get_all_user_priorities,
)
from server.app_qos import selective_degrader

router = APIRouter(prefix="/api/v1/apps", tags=["app-priority"])

# Use the canonical secret from server.auth so tokens verify consistently whether
# JWT_SECRET is provided via env or an ephemeral one was generated at startup.
from server.auth import JWT_SECRET


# ── Auth helpers ──────────────────────────────────────────────────

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


# ── Request / response models ────────────────────────────────────

class PriorityItem(BaseModel):
    app_id: str
    priority: str

class PriorityRequest(BaseModel):
    priorities: List[PriorityItem]      # [{app_id, priority}] from frontend
    total_mbps: Optional[float] = None


class SelectiveRequest(BaseModel):
    app_id: Optional[str] = None
    ips: List[str]
    mode: str                           # "block" | "throttle"
    duration_s: int
    throttle_kbps: Optional[int] = None
    reason: Optional[str] = ""


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/active")
def list_active_apps(claims=Depends(require_user)):
    """Detect running applications on this host."""
    return {"apps": get_active_apps()}


@router.get("/signatures")
def list_signatures():
    """Return the full app signature catalog as array (for frontend)."""
    # Per-app icon/color overrides (since signatures store single-char fallbacks)
    ICONS = {
        "zoom": "🎥", "teams": "💼", "google_meet": "📹", "youtube": "▶️",
        "netflix": "🎬", "twitch": "🟣", "disney_plus": "🏰", "discord": "🎮",
        "spotify": "🎵", "google_chrome": "🌐", "onedrive": "☁️", "steam": "🎮",
    }
    COLORS = {
        "zoom": "#2D8CFF", "teams": "#6264A7", "google_meet": "#00897B",
        "youtube": "#FF0000", "netflix": "#E50914", "twitch": "#9146FF",
        "disney_plus": "#113CCF", "discord": "#5865F2", "spotify": "#1DB954",
        "google_chrome": "#4285F4", "onedrive": "#0078D4", "steam": "#1B2838",
    }
    apps = []
    for app_id, sig in APP_SIGNATURES.items():
        apps.append({
            "app_id": sig.app_id,
            "name": sig.display_name,
            "icon": ICONS.get(app_id, sig.icon),
            "color": COLORS.get(app_id, "#3b82f6"),
            "category": sig.category,
            "default_priority": sig.default_priority,
            "min_kbps": int(sig.base_bandwidth_mbps * 100),
            "recommended_kbps": int(sig.base_bandwidth_mbps * 1000),
            "quality_tiers": [
                {
                    "label": t.label,
                    "min_kbps": int(t.min_mbps * 1000),
                    "max_kbps": int(t.max_mbps * 1000),
                    "description": t.label,
                }
                for t in sig.quality_tiers
            ],
        })
    return {"apps": apps}


@router.get("/priorities")
def get_user_priorities(claims=Depends(require_user)):
    """Return the current user's app priority settings."""
    user_id = claims.get("sub", claims.get("user_id", "anonymous"))
    return {"user_id": user_id, "priorities": get_priorities(user_id)}


@router.post("/priorities")
def apply_priorities(req: PriorityRequest, claims=Depends(require_user)):
    """Apply new app priority settings for the current user."""
    user_id = claims.get("sub", claims.get("user_id", "anonymous"))
    # Convert list of PriorityItem to dict for the manager
    prio_dict = {p.app_id: p.priority for p in req.priorities}
    try:
        result = set_priorities(user_id, prio_dict, req.total_mbps)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    # Transform to frontend-expected shape: {apps: [{app_id, name, priority, ceil_kbps, estimated_quality}]}
    apps = []
    for app_id, alloc in result.items():
        sig = APP_SIGNATURES.get(app_id)
        quality_raw = alloc.get("quality")
        quality_label = quality_raw.get("label") if isinstance(quality_raw, dict) else (quality_raw or "Unknown")
        apps.append({
            "app_id": app_id,
            "name": sig.display_name if sig else app_id,
            "priority": alloc.get("priority", "NORMAL"),
            "guaranteed_kbps": int(alloc.get("allocated_mbps", 0) * 1000 * 0.5),
            "ceil_kbps": int(alloc.get("allocated_mbps", 0) * 1000),
            "estimated_quality": quality_label,
        })
    from server.app_qos.bandwidth_enforcer import ENFORCER_MODE, WAN_INTERFACE, TOTAL_LINK_MBPS
    import datetime
    return {
        "user_id": user_id,
        "apps": apps,
        "enforcement": {
            "mode": ENFORCER_MODE,
            "interface": WAN_INTERFACE,
            "total_link_mbps": TOTAL_LINK_MBPS,
            "rules_applied": len(apps),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "active": ENFORCER_MODE != "simulate",
        },
        "message": f"Applied priorities for {len(req.priorities)} app(s).",
    }


@router.get("/enforcement-status")
def enforcement_status(claims=Depends(require_user)):
    """Return current enforcement mode, active tc rules, and system info."""
    from server.app_qos.bandwidth_enforcer import ENFORCER_MODE, WAN_INTERFACE, TOTAL_LINK_MBPS
    from server.app_qos.priority_manager import _enforcer
    import subprocess, datetime

    tc_output = ""
    if ENFORCER_MODE == "tc":
        try:
            r = subprocess.run(["tc", "qdisc", "show", "dev", WAN_INTERFACE],
                               capture_output=True, text=True, timeout=5)
            tc_output = r.stdout.strip()
        except Exception:
            tc_output = "tc not available"

    active = _enforcer.get_active_allocations()
    # Get command log from enforcer
    commands = _enforcer.get_commands_log() if hasattr(_enforcer, 'get_commands_log') else []

    # Check if Windows QoS policies exist
    ps_policies = ""
    if ENFORCER_MODE == "powershell":
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 "Get-NetQosPolicy | Where-Object {$_.Name -like 'PW_*'} | Select-Object Name, ThrottleRateAction | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10)
            ps_policies = r.stdout.strip()
        except Exception:
            ps_policies = "PowerShell not available or not admin"

    return {
        "mode": ENFORCER_MODE,
        "interface": WAN_INTERFACE,
        "total_link_mbps": TOTAL_LINK_MBPS,
        "active_rules": len(active),
        "tc_qdisc_output": tc_output,
        "windows_qos_policies": ps_policies,
        "commands_executed": len(commands),
        "last_commands": commands[-5:] if commands else [],
        "requires_admin": ENFORCER_MODE == "powershell",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


@router.delete("/priorities/{app_id}")
def delete_app_priority(app_id: str, claims=Depends(require_user)):
    """Remove a single app from the user's priority set."""
    user_id = claims.get("sub", claims.get("user_id", "anonymous"))
    result = remove_app_priority(user_id, app_id)
    return {"user_id": user_id, "result": result}


@router.post("/reset")
def reset_priorities(claims=Depends(require_user)):
    """Clear all priority rules for the current user."""
    user_id = claims.get("sub", claims.get("user_id", "anonymous"))
    result = reset_all(user_id)
    return {"success": True, "user_id": user_id, "result": result}


@router.get("/quality")
def quality_predictions(claims=Depends(require_user)):
    """Get quality predictions for the user's current priority setup."""
    user_id = claims.get("sub", claims.get("user_id", "anonymous"))
    preds = get_quality_predictions(user_id)
    return {"user_id": user_id, "predictions": preds}


@router.get("/admin/all-priorities")
def admin_all_priorities(claims=Depends(require_admin)):
    """Admin: view all users' priority settings."""
    return {"all_priorities": get_all_user_priorities()}


# ── Selective IP Degrade ─────────────────────────────────────────
# Narrow-scope, time-bounded per-IP throttle or block. Distinct from the
# App Priority Switch which does a full-app domain block.

@router.get("/selective/candidates/{app_id}")
def selective_candidates(app_id: str, claims=Depends(require_user)):
    """Return pickable IPs/CIDRs for a given app (static CIDRs + live DNS)."""
    if app_id not in APP_SIGNATURES:
        raise HTTPException(404, f"Unknown app_id: {app_id}")
    ips = selective_degrader.candidate_ips_for(app_id)
    sig = APP_SIGNATURES[app_id]
    return {
        "app_id": app_id,
        "display_name": sig.display_name,
        "ips": ips,
        "cidrs": sig.cidrs,
    }


@router.get("/selective")
def selective_list(claims=Depends(require_user)):
    """List currently active selective rules (with remaining seconds)."""
    return {"rules": selective_degrader.list_rules()}


@router.post("/selective")
def selective_create(req: SelectiveRequest, claims=Depends(require_user)):
    """
    Start a time-bounded selective degrade rule.
    Body: {app_id?, ips[], mode, duration_s, throttle_kbps?, reason?}
    """
    try:
        rule = selective_degrader.start_rule(
            ips=req.ips,
            mode=req.mode,  # type: ignore[arg-type]
            duration_s=req.duration_s,
            throttle_kbps=req.throttle_kbps,
            app_id=req.app_id,
            reason=req.reason or "",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    from server.app_qos.bandwidth_enforcer import ENFORCER_MODE
    return {
        "rule": rule.as_dict(),
        "enforcement": {
            "mode": ENFORCER_MODE,
            "active": ENFORCER_MODE != "simulate",
        },
        "message": (
            f"{req.mode.capitalize()} applied to {len(rule.ips)} IP(s) "
            f"for {rule.duration_s}s. Auto-restore when timer expires."
        ),
    }


@router.delete("/selective/{rule_id}")
def selective_stop(rule_id: str, claims=Depends(require_user)):
    """Stop a selective rule early and remove its OS artifacts."""
    ok = selective_degrader.stop_rule(rule_id)
    if not ok:
        raise HTTPException(404, "Rule not found or already expired")
    return {"success": True, "rule_id": rule_id}


@router.post("/selective/stop-all")
def selective_stop_all(claims=Depends(require_user)):
    """Stop every active selective rule."""
    n = selective_degrader.stop_all()
    return {"success": True, "stopped": n}


@router.websocket("/ws/{user_id}/quality")
async def ws_quality_stream(websocket: WebSocket, user_id: str):
    """Push quality updates every 2 seconds."""
    await websocket.accept()
    try:
        while True:
            preds = get_quality_predictions(user_id)
            await websocket.send_json({
                "user_id": user_id,
                "predictions": preds,
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
