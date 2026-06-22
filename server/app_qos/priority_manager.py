"""
Priority manager -- stateful layer that tracks per-user app priority settings
and orchestrates the bandwidth enforcer.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from server.app_qos.signatures import (
    APP_SIGNATURES, PRIORITY_CLASSES, predict_quality, get_all_app_ids,
)
from server.app_qos.flow_detector import detect_active_apps, DetectedApp
from server.app_qos.bandwidth_enforcer import BandwidthEnforcer, TOTAL_LINK_MBPS

# In-memory per-user priorities: {user_id: {app_id: priority_class}}
_user_priorities: Dict[str, Dict[str, str]] = {}

# Shared enforcer instance
_enforcer = BandwidthEnforcer()

# Audit trail (in-memory for now)
_priority_log: List[dict] = []


# ── Public API ────────────────────────────────────────────────────

def get_active_apps() -> List[dict]:
    """Return currently detected applications on this host."""
    detected = detect_active_apps()
    return [
        {
            "app_id": d.app_id,
            "display_name": d.display_name,
            "category": d.category,
            "icon": d.icon,
            "matched_by": d.matched_by,
            "pid": d.pid,
            "process_name": d.process_name,
            "connections": d.connections,
            "estimated_bandwidth_mbps": d.estimated_bandwidth_mbps,
        }
        for d in detected
    ]


def set_priorities(
    user_id: str,
    priorities: Dict[str, str],
    total_mbps: Optional[float] = None,
) -> Dict[str, dict]:
    """
    Set app priorities for *user_id*.

    *priorities*: ``{app_id: priority_class}`` e.g. ``{"zoom": "HIGH", "youtube": "LOW"}``.

    Returns the enforcer's allocation result.
    """
    # Validate
    for app_id, pclass in priorities.items():
        if app_id not in APP_SIGNATURES:
            raise ValueError(f"Unknown app_id: {app_id}")
        if pclass not in PRIORITY_CLASSES:
            raise ValueError(
                f"Unknown priority class '{pclass}'. "
                f"Valid: {list(PRIORITY_CLASSES.keys())}"
            )

    old = _user_priorities.get(user_id, {})
    _user_priorities[user_id] = dict(priorities)

    result = _enforcer.apply_priorities(priorities, total_mbps)

    _log_priority_change(user_id, old, priorities, result)
    return result


def get_priorities(user_id: str) -> Dict[str, str]:
    """Return the current priority map for *user_id*."""
    return dict(_user_priorities.get(user_id, {}))


def remove_app_priority(user_id: str, app_id: str) -> Dict[str, dict]:
    """Remove a single app from the user's priority set and re-enforce."""
    priors = _user_priorities.get(user_id, {})
    old = dict(priors)
    priors.pop(app_id, None)
    _user_priorities[user_id] = priors

    if priors:
        result = _enforcer.apply_priorities(priors)
    else:
        result = _enforcer.clear_all_rules()

    _log_priority_change(user_id, old, priors, result)
    return result


def reset_all(user_id: str) -> dict:
    """Clear all priorities for *user_id* and remove OS rules."""
    old = _user_priorities.pop(user_id, {})
    result = _enforcer.clear_all_rules()
    _log_priority_change(user_id, old, {}, result)
    return result


def get_quality_predictions(
    user_id: str,
    total_mbps: Optional[float] = None,
) -> List[dict]:
    """
    For the user's current priorities, return predicted quality per app.
    """
    priors = _user_priorities.get(user_id, {})
    if not priors:
        return []

    total = total_mbps or TOTAL_LINK_MBPS
    allocations = _enforcer._compute_allocations(priors, total)

    results: List[dict] = []
    for app_id, alloc in allocations.items():
        sig = APP_SIGNATURES.get(app_id)
        results.append({
            "app_id": app_id,
            "display_name": sig.display_name if sig else app_id,
            "priority": alloc["priority"],
            "allocated_mbps": alloc["allocated_mbps"],
            "quality": alloc["quality"],
        })
    return results


def get_all_user_priorities() -> Dict[str, Dict[str, str]]:
    """Admin view: return all users' priorities."""
    return {uid: dict(p) for uid, p in _user_priorities.items()}


# ── Audit helper ──────────────────────────────────────────────────

def _log_priority_change(
    user_id: str,
    old: Dict[str, str],
    new: Dict[str, str],
    result: dict,
) -> None:
    """Append a priority change event to the in-memory audit trail."""
    _priority_log.append({
        "timestamp": time.time(),
        "user_id": user_id,
        "old_priorities": old,
        "new_priorities": new,
        "result_summary": {
            k: v.get("allocated_mbps") if isinstance(v, dict) else v
            for k, v in (result.items() if isinstance(result, dict) else {})
        },
    })
