"""
Detect running applications by matching network connections against signatures.

Uses psutil to inspect active network connections and running processes,
then matches them against the known AppSignature database.
"""

from __future__ import annotations

import struct
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from server.app_qos.signatures import APP_SIGNATURES, AppSignature

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None  # type: ignore
    _HAS_PSUTIL = False


@dataclass
class DetectedApp:
    """An application detected as actively using the network."""
    app_id: str
    display_name: str
    category: str
    icon: str
    matched_by: str              # "process", "port", "cidr", "simulated"
    pid: Optional[int] = None
    process_name: Optional[str] = None
    connections: int = 0
    estimated_bandwidth_mbps: float = 0.0


# ── Internal helpers ──────────────────────────────────────────────

def _get_active_connections() -> List[dict]:
    """Return a list of active network connections with associated PIDs."""
    if not _HAS_PSUTIL:
        return []
    results = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            entry: dict = {
                "fd": conn.fd,
                "family": conn.family,
                "type": conn.type,
                "laddr": conn.laddr,
                "raddr": conn.raddr,
                "status": conn.status,
                "pid": conn.pid,
            }
            # Resolve process name
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    entry["process_name"] = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    entry["process_name"] = None
            else:
                entry["process_name"] = None
            results.append(entry)
    except (psutil.AccessDenied, OSError):
        pass
    return results


def _ip_in_cidr(ip: str, cidr: str) -> bool:
    """Check whether *ip* falls within *cidr* (e.g. '10.0.0.1' in '10.0.0.0/24')."""
    try:
        network, prefix_len = cidr.split("/")
        prefix_len = int(prefix_len)
        ip_int = struct.unpack("!I", socket.inet_aton(ip))[0]
        net_int = struct.unpack("!I", socket.inet_aton(network))[0]
        mask = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
        return (ip_int & mask) == (net_int & mask)
    except Exception:
        return False


def _ip_matches_signature(ip: str, sig: AppSignature) -> bool:
    """Return True if *ip* matches any CIDR in the signature."""
    for cidr in sig.cidrs:
        if _ip_in_cidr(ip, cidr):
            return True
    return False


def _port_matches_signature(port: int, sig: AppSignature) -> bool:
    """Return True if *port* matches the signature's known ports."""
    return port in sig.ports or port in sig.udp_ports


def _process_matches_signature(process_name: Optional[str],
                               sig: AppSignature) -> bool:
    """Return True if *process_name* matches the signature."""
    if not process_name:
        return False
    pn_lower = process_name.lower()
    for known in sig.process_names:
        if known.lower() == pn_lower:
            return True
    return False


def _estimate_bandwidth(connections: int, sig: AppSignature) -> float:
    """Rough bandwidth estimate based on connection count and base bandwidth."""
    # Each connection contributes a fraction; cap at 2x base
    per_conn = sig.base_bandwidth_mbps / max(3, connections)
    return min(connections * per_conn, sig.base_bandwidth_mbps * 2.0)


# ── Public API ────────────────────────────────────────────────────

def detect_active_apps() -> List[DetectedApp]:
    """
    Scan the host for running applications that match known signatures.

    Returns a list of DetectedApp objects.  When psutil is unavailable the
    function returns an empty list (no crash).
    """
    if not _HAS_PSUTIL:
        return []

    connections = _get_active_connections()
    if not connections:
        return []

    # Track matches per app_id
    matches: Dict[str, dict] = {}

    for conn in connections:
        raddr = conn.get("raddr")
        if not raddr:
            continue
        remote_ip = raddr.ip if hasattr(raddr, "ip") else (raddr[0] if raddr else None)
        remote_port = raddr.port if hasattr(raddr, "port") else (raddr[1] if raddr and len(raddr) > 1 else None)
        proc_name = conn.get("process_name")
        pid = conn.get("pid")

        for app_id, sig in APP_SIGNATURES.items():
            matched_by: Optional[str] = None

            # Priority: CIDR > port > process
            if remote_ip and _ip_matches_signature(remote_ip, sig):
                matched_by = "cidr"
            elif remote_port and _port_matches_signature(remote_port, sig):
                # Port match alone is too broad for generic ports (80/443)
                if remote_port not in (80, 443) or _process_matches_signature(proc_name, sig):
                    matched_by = "port"
            elif _process_matches_signature(proc_name, sig):
                matched_by = "process"

            if matched_by:
                if app_id not in matches:
                    matches[app_id] = {
                        "app_id": app_id,
                        "display_name": sig.display_name,
                        "category": sig.category,
                        "icon": sig.icon,
                        "matched_by": matched_by,
                        "pid": pid,
                        "process_name": proc_name,
                        "connections": 0,
                    }
                matches[app_id]["connections"] += 1

    result: List[DetectedApp] = []
    for app_id, m in matches.items():
        sig = APP_SIGNATURES[app_id]
        result.append(DetectedApp(
            app_id=m["app_id"],
            display_name=m["display_name"],
            category=m["category"],
            icon=m["icon"],
            matched_by=m["matched_by"],
            pid=m["pid"],
            process_name=m["process_name"],
            connections=m["connections"],
            estimated_bandwidth_mbps=round(
                _estimate_bandwidth(m["connections"], sig), 2
            ),
        ))

    # Sort by estimated bandwidth descending
    result.sort(key=lambda d: d.estimated_bandwidth_mbps, reverse=True)
    return result
