"""
Traffic Steering / Routing module — PathWise AI
Implements hitless handoff orchestration that talks to the live SDN controller.
Satisfies: Req-Func-Sw-4, Req-Func-Sw-6, Req-Func-Sw-7, Req-Qual-Perf-2 (<50ms).
"""

from __future__ import annotations
import os
import time
import uuid
import logging
from typing import Optional

from server.sdn_adapter import get_adapter

logger = logging.getLogger("pathwise.routing")


def _priority_for_class(tc: str) -> int:
    return {"voip": 65535, "video": 50000, "critical": 45000,
            "bulk": 10000}.get(tc, 20000)


def _dscp_for_class(tc: str) -> int:
    return {"voip": 46, "video": 34, "critical": 26, "bulk": 0}.get(tc, 0)


def _resolve_node_id(link_name: str) -> str:
    """Map WAN link name (or canonical link_id) to SDN OpenFlow node ID."""
    n = (link_name or "").lower()
    mapping = {
        "fiber": "openflow:1", "fiber-primary": "openflow:1",
        "broadband": "openflow:2", "broadband-secondary": "openflow:2",
        "satellite": "openflow:3", "satellite-backup": "openflow:3",
        "5g": "openflow:4", "5g-mobile": "openflow:4",
        "wifi": "openflow:5",
    }
    return mapping.get(n, "openflow:1")


def build_flow_body(target_link: str, traffic_class: str, flow_id: str,
                    timeout_s: Optional[int] = None) -> dict:
    """Construct an OpenFlow 1.3 flow body for a given traffic class."""
    if timeout_s is None:
        timeout_s = int(os.getenv("SDN_FLOW_TIMEOUT_S", "30"))
    return {
        "id": flow_id,
        "priority": _priority_for_class(traffic_class),
        "timeout": timeout_s,
        "isPermanent": timeout_s == 0,
        "tableId": 0,
        "treatment": {
            "instructions": [{"type": "OUTPUT", "port": target_link}]
        },
        "selector": {
            "criteria": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IP_DSCP", "ipDscp": _dscp_for_class(traffic_class)},
            ]
        },
        "traffic_class": traffic_class,
    }


def execute_hitless_handoff(source_link: str, target_link: str,
                            traffic_class: str,
                            flow_id: Optional[str] = None) -> dict:
    """
    Pre-emptively reroute traffic from source_link to target_link with zero loss.
    Satisfies Req-Func-Sw-6, Req-Func-Sw-7. Must complete in <50 ms (Req-Qual-Perf-2).

    Pipeline:
      1. Build OpenFlow 1.3 flow body
      2. Validate in Digital Twin sandbox (Req-Func-Sw-8)
      3. Submit to live SDN controller via SDNControllerAdapter
      4. Return timing + status
    """
    flow_id = flow_id or f"steer-{uuid.uuid4().hex[:8]}"
    t0 = time.perf_counter()

    flow_body = build_flow_body(target_link, traffic_class, flow_id)

    # Sandbox validation BEFORE touching the live network (Req-Func-Sw-8)
    try:
        from server.sandbox import run_sandbox_validation
        sandbox_result = run_sandbox_validation(
            source_link=source_link,
            target_link=target_link,
            flow_body=flow_body,
        )
    except Exception as exc:
        logger.exception("Sandbox validation error")
        sandbox_result = {"passed": False, "error": str(exc)}

    if not sandbox_result.get("passed"):
        return {
            "success": False,
            "reason": "sandbox_rejected",
            "flow_id": flow_id,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "sandbox": sandbox_result,
        }

    # Preserve all active sessions before switching (Req-Func-Sw-7)
    from server.session_manager import get_session_manager
    sm = get_session_manager()
    session_snapshot = sm.snapshot_sessions(source_link)
    handoff_result = sm.migrate_sessions(source_link, target_link)

    # Apply to live SDN controller
    node_id = _resolve_node_id(target_link)
    ok = get_adapter().update_flow_table(node_id, flow_id, flow_body)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {
        "success": ok,
        "elapsed_ms": round(elapsed_ms, 2),
        "flow_id": flow_id,
        "source": source_link,
        "target": target_link,
        "traffic_class": traffic_class,
        "node_id": node_id,
        "sandbox": sandbox_result,
        "sessions": {
            "total": handoff_result.total_sessions,
            "migrated": handoff_result.migrated_sessions,
            "dropped": handoff_result.dropped_sessions,
            "preserved": handoff_result.preserved,
            "migration_time_ms": handoff_result.migration_time_ms,
        },
    }


def rollback_handoff(flow_id: str) -> bool:
    """One-click rollback of a previously installed steering rule."""
    return get_adapter().rollback_flow(flow_id)
