"""
SDN Controller Adapter — PathWise AI
Implements live northbound API calls to OpenDaylight (RESTCONF) and ONOS (REST).
Satisfies: Req-Func-Sw-5, Req-Func-Hw-2

Used by:
  - server.routing (hitless handoff)
  - server.ibn_engine (YANG/NETCONF intent delivery)
  - server.main /api/v1/sdn/health and /api/v1/routing/rollback endpoints
"""

from __future__ import annotations
import os
import json
import logging
import time
from typing import Optional
from enum import Enum

try:
    import httpx  # preferred
    _HTTP = "httpx"
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
    _HTTP = None

logger = logging.getLogger("pathwise.sdn")

ODL_BASE  = f"http://{os.getenv('ODL_HOST','opendaylight')}:{os.getenv('ODL_PORT','8181')}"
ONOS_BASE = f"http://{os.getenv('ONOS_HOST','onos')}:{os.getenv('ONOS_PORT','8182')}"
ODL_AUTH  = (os.getenv("ODL_USER", "admin"), os.getenv("ODL_PASS", "admin"))
ONOS_AUTH = (os.getenv("ONOS_USER", "onos"), os.getenv("ONOS_PASS", "rocks"))
CTRL_TYPE = os.getenv("SDN_CONTROLLER_TYPE", "odl")


class SDNControllerType(str, Enum):
    ODL = "odl"
    ONOS = "onos"
    BOTH = "both"


def _require_httpx():
    if httpx is None:
        raise RuntimeError("httpx is not installed; pip install httpx")


# ─── OpenDaylight helpers ────────────────────────────────────────────────────

def _odl_headers() -> dict:
    return {"Content-Type": "application/json", "Accept": "application/json"}


def odl_get_topology() -> dict:
    """Fetch the current network topology from ODL RESTCONF."""
    _require_httpx()
    url = (f"{ODL_BASE}/restconf/operational/"
           "network-topology:network-topology/topology/flow:1")
    r = httpx.get(url, auth=ODL_AUTH, headers=_odl_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def odl_get_flow_table(node_id: str, table_id: int = 0) -> dict:
    """Read flow table from an ODL-managed OpenFlow switch."""
    _require_httpx()
    url = (f"{ODL_BASE}/restconf/operational/opendaylight-inventory:nodes"
           f"/node/{node_id}/table/{table_id}")
    r = httpx.get(url, auth=ODL_AUTH, headers=_odl_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def odl_install_flow(node_id: str, flow_id: str, flow_body: dict,
                     table_id: int = 0) -> bool:
    """
    Install a flow rule on an ODL-managed switch via RESTCONF PUT.
    Returns True on success (HTTP 200 or 201).
    """
    _require_httpx()
    url = (f"{ODL_BASE}/restconf/config/opendaylight-inventory:nodes"
           f"/node/{node_id}/table/{table_id}/flow/{flow_id}")
    payload = {"flow-node-inventory:flow": [flow_body]}
    r = httpx.put(url, auth=ODL_AUTH, headers=_odl_headers(),
                  content=json.dumps(payload), timeout=15)
    if r.status_code in (200, 201):
        logger.info("ODL flow %s installed on node %s", flow_id, node_id)
        return True
    logger.error("ODL flow install failed: %s %s", r.status_code, r.text[:300])
    return False


def odl_delete_flow(node_id: str, flow_id: str, table_id: int = 0) -> bool:
    """Delete (rollback) a flow rule from ODL."""
    _require_httpx()
    url = (f"{ODL_BASE}/restconf/config/opendaylight-inventory:nodes"
           f"/node/{node_id}/table/{table_id}/flow/{flow_id}")
    r = httpx.delete(url, auth=ODL_AUTH, headers=_odl_headers(), timeout=10)
    if r.status_code in (200, 204):
        logger.info("ODL flow %s deleted from node %s", flow_id, node_id)
        return True
    logger.error("ODL flow delete failed: %s", r.status_code)
    return False


# ─── ONOS helpers ────────────────────────────────────────────────────────────

def _onos_headers() -> dict:
    return {"Content-Type": "application/json", "Accept": "application/json"}


def onos_get_devices() -> list:
    """List all devices registered with ONOS."""
    _require_httpx()
    url = f"{ONOS_BASE}/onos/v1/devices"
    r = httpx.get(url, auth=ONOS_AUTH, headers=_onos_headers(), timeout=10)
    r.raise_for_status()
    return r.json().get("devices", [])


def onos_get_flows(device_id: str) -> list:
    """Get all flow rules on an ONOS-managed device."""
    _require_httpx()
    url = f"{ONOS_BASE}/onos/v1/flows/{device_id}"
    r = httpx.get(url, auth=ONOS_AUTH, headers=_onos_headers(), timeout=10)
    r.raise_for_status()
    return r.json().get("flows", [])


def onos_install_flow(device_id: str, flow_body: dict) -> Optional[str]:
    """
    POST a flow rule to ONOS. Returns the flow ID assigned by ONOS, or None.
    """
    _require_httpx()
    url = f"{ONOS_BASE}/onos/v1/flows/{device_id}"
    payload = {"flows": [flow_body]}
    r = httpx.post(url, auth=ONOS_AUTH, headers=_onos_headers(),
                   content=json.dumps(payload), timeout=15)
    if r.status_code in (200, 201):
        flow_ids = r.json().get("flowIds", [])
        assigned_id = flow_ids[0] if flow_ids else None
        logger.info("ONOS flow installed on device %s -> id %s", device_id, assigned_id)
        return assigned_id
    logger.error("ONOS flow install failed: %s %s", r.status_code, r.text[:300])
    return None


def onos_delete_flow(device_id: str, flow_id: str) -> bool:
    """Delete (rollback) a flow rule from ONOS."""
    _require_httpx()
    url = f"{ONOS_BASE}/onos/v1/flows/{device_id}/{flow_id}"
    r = httpx.delete(url, auth=ONOS_AUTH, headers=_onos_headers(), timeout=10)
    if r.status_code in (200, 204):
        logger.info("ONOS flow %s deleted from device %s", flow_id, device_id)
        return True
    logger.error("ONOS flow delete failed: %s", r.status_code)
    return False


# ─── Unified SDNControllerAdapter ────────────────────────────────────────────

class SDNControllerAdapter:
    """
    Unified adapter that routes calls to ODL, ONOS, or both based on
    SDN_CONTROLLER_TYPE environment variable.
    Satisfies Req-Func-Sw-5 runtime flow table modification.
    """

    def __init__(self):
        try:
            self.controller_type = SDNControllerType(CTRL_TYPE)
        except ValueError:
            self.controller_type = SDNControllerType.ODL
        # flow_id -> (node_id, table_id, controller, [onos_assigned_id])
        self._installed_flows: dict[str, tuple] = {}

    def health_check(self) -> dict:
        """Return liveness status for each configured controller."""
        status: dict[str, str] = {}
        if self.controller_type in (SDNControllerType.ODL, SDNControllerType.BOTH):
            try:
                odl_get_topology()
                status["odl"] = "up"
            except Exception as exc:
                status["odl"] = f"down: {exc}"
        if self.controller_type in (SDNControllerType.ONOS, SDNControllerType.BOTH):
            try:
                onos_get_devices()
                status["onos"] = "up"
            except Exception as exc:
                status["onos"] = f"down: {exc}"
        return status

    def get_flow_state(self, node_id: str) -> dict:
        """
        Read current flow tables from the live controller.
        Used by routing rollback and audit.
        """
        if self.controller_type == SDNControllerType.ONOS:
            return {"onos_flows": onos_get_flows(node_id)}
        return {"odl_flows": odl_get_flow_table(node_id)}

    def update_flow_table(self, node_id: str, flow_id: str,
                          flow_body: dict, table_id: int = 0) -> bool:
        """
        Install a routing rule on the live SDN controller.
        Records the installation for rollback support.
        Returns True on success.
        """
        t0 = time.perf_counter()
        success = False

        if self.controller_type in (SDNControllerType.ODL, SDNControllerType.BOTH):
            try:
                success = odl_install_flow(node_id, flow_id, flow_body, table_id)
                if success:
                    self._installed_flows[flow_id] = (node_id, table_id, "odl")
            except Exception as exc:
                logger.error("ODL install exception: %s", exc)

        if self.controller_type in (SDNControllerType.ONOS, SDNControllerType.BOTH):
            try:
                onos_id = onos_install_flow(node_id, flow_body)
                if onos_id:
                    success = True
                    self._installed_flows[flow_id] = (node_id, table_id, "onos", onos_id)
            except Exception as exc:
                logger.error("ONOS install exception: %s", exc)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("update_flow_table: flow=%s node=%s elapsed=%.1fms ok=%s",
                    flow_id, node_id, elapsed_ms, success)
        return success

    def rollback_flow(self, flow_id: str) -> bool:
        """
        Remove a previously installed flow rule (one-click rollback).
        Satisfies the rollback requirement in Req-Func-Sw-5.
        """
        entry = self._installed_flows.pop(flow_id, None)
        if entry is None:
            logger.warning("rollback_flow: flow_id %s not found in installed map", flow_id)
            return False
        node_id, table_id, ctrl = entry[0], entry[1], entry[2]
        try:
            if ctrl == "odl":
                return odl_delete_flow(node_id, flow_id, table_id)
            if ctrl == "onos":
                onos_flow_id = entry[3] if len(entry) > 3 else flow_id
                return onos_delete_flow(node_id, onos_flow_id)
        except Exception as exc:
            logger.error("rollback_flow exception: %s", exc)
        return False

    def authenticate(self) -> bool:
        """Verify credentials against the configured controller on startup."""
        status = self.health_check()
        return all(v == "up" for v in status.values())


# Module-level singleton — convenient for routing/IBN imports
_adapter_singleton: Optional[SDNControllerAdapter] = None


def get_adapter() -> SDNControllerAdapter:
    global _adapter_singleton
    if _adapter_singleton is None:
        _adapter_singleton = SDNControllerAdapter()
    return _adapter_singleton
