"""
Bandwidth enforcer -- applies OS-level traffic shaping (or simulates it).

Modes (set via ENFORCER_MODE env var):
  simulate   - (default) compute allocations, log, but touch no OS settings
  tc         - Linux tc/iptables (requires root / NET_ADMIN)
  powershell - Windows NetQoS policies (requires Administrator)
               Uses IP-based throttling so YouTube in ANY browser gets throttled.
"""

from __future__ import annotations

import os
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from server.app_qos.signatures import (
    APP_SIGNATURES, PRIORITY_CLASSES, predict_quality,
)

logger = logging.getLogger("pathwise.enforcer")

ENFORCER_MODE = os.environ.get("ENFORCER_MODE", "simulate").lower()
WAN_INTERFACE = os.environ.get("WAN_INTERFACE", "eth0")
TOTAL_LINK_MBPS = float(os.environ.get("TOTAL_LINK_MBPS", "100"))

# Extended YouTube/Google Video IP ranges for comprehensive coverage
YOUTUBE_EXTRA_CIDRS = [
    "142.250.0.0/15",    # Google global
    "172.217.0.0/16",    # Google
    "216.58.192.0/19",   # Google
    "216.239.32.0/19",   # Google
    "209.85.128.0/17",   # Google
    "74.125.0.0/16",     # Google
    "173.194.0.0/16",    # Google
    "64.233.160.0/19",   # Google
    "108.177.0.0/17",    # Google
    "172.253.0.0/16",    # Google
]


class BandwidthEnforcer:
    """Compute bandwidth allocations and optionally enforce them on the OS."""

    def __init__(self) -> None:
        self._active_rules: Dict[str, dict] = {}
        self._mode = ENFORCER_MODE
        self._commands_log: list[dict] = []
        logger.info("BandwidthEnforcer mode=%s interface=%s total=%sMbps",
                    self._mode, WAN_INTERFACE, TOTAL_LINK_MBPS)

    # ── Public API ────────────────────────────────────────────

    def apply_priorities(
        self,
        priorities: Dict[str, str],
        total_mbps: Optional[float] = None,
    ) -> Dict[str, dict]:
        total = total_mbps or TOTAL_LINK_MBPS
        allocations = self._compute_allocations(priorities, total)

        self._commands_log = []
        if self._mode == "tc":
            self._apply_tc_rules(allocations)
        elif self._mode == "powershell":
            self._apply_powershell_rules(allocations)
        else:
            self._apply_simulate(allocations)

        self._active_rules = allocations
        return allocations

    def clear_all_rules(self) -> dict:
        cleared = list(self._active_rules.keys())
        self._commands_log = []

        if self._mode == "tc":
            self._run(f"tc qdisc del dev {WAN_INTERFACE} root 2>/dev/null || true")
        elif self._mode == "powershell":
            # Remove all PathWise QoS policies
            self._run_ps(
                "Get-NetQosPolicy | Where-Object {$_.Name -like 'PW_*'} | "
                "Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue"
            )

        self._active_rules = {}
        logger.info("Cleared all QoS rules: %s", cleared)
        return {"status": "cleared", "rules_removed": cleared}

    def get_active_allocations(self) -> Dict[str, dict]:
        return dict(self._active_rules)

    def get_commands_log(self) -> list[dict]:
        return list(self._commands_log)

    # ── Allocation computation ────────────────────────────────

    def _compute_allocations(
        self,
        priorities: Dict[str, str],
        total_mbps: float,
    ) -> Dict[str, dict]:
        if not priorities:
            return {}

        raw: Dict[str, float] = {}
        for app_id, pclass in priorities.items():
            cls = PRIORITY_CLASSES.get(pclass, PRIORITY_CLASSES["NORMAL"])
            raw[app_id] = cls["bandwidth_pct"]

        total_pct = sum(raw.values())
        if total_pct <= 0:
            return {
                app_id: {
                    "app_id": app_id, "priority": priorities[app_id],
                    "allocated_mbps": 0.0, "bandwidth_pct": 0.0,
                    "quality": predict_quality(app_id, 0.0),
                    "enforced": self._mode != "simulate",
                }
                for app_id in priorities
            }

        scale = min(1.0, 1.0 / total_pct)
        allocations: Dict[str, dict] = {}
        for app_id, pct in raw.items():
            actual_pct = pct * scale
            mbps = round(actual_pct * total_mbps, 2)
            allocations[app_id] = {
                "app_id": app_id, "priority": priorities[app_id],
                "allocated_mbps": mbps,
                "bandwidth_pct": round(actual_pct * 100, 1),
                "quality": predict_quality(app_id, mbps),
                "enforced": self._mode != "simulate",
            }
        return allocations

    # ── Linux tc (HTB) ────────────────────────────────────────

    def _apply_tc_rules(self, allocations: Dict[str, dict]) -> None:
        iface = WAN_INTERFACE
        self._run(f"tc qdisc del dev {iface} root 2>/dev/null || true")
        self._run(f"tc qdisc add dev {iface} root handle 1: htb default 99")
        self._run(f"tc class add dev {iface} parent 1: classid 1:1 htb rate {int(TOTAL_LINK_MBPS)}mbit")

        class_id = 10
        for app_id, alloc in allocations.items():
            rate = max(1, int(alloc["allocated_mbps"] * 1000))
            self._run(
                f"tc class add dev {iface} parent 1:1 classid 1:{class_id} "
                f"htb rate {rate}kbit ceil {rate}kbit"
            )
            sig = APP_SIGNATURES.get(app_id)
            if sig:
                for cidr in sig.cidrs[:5]:
                    self._run(
                        f"tc filter add dev {iface} parent 1: protocol ip prio {class_id} "
                        f"u32 match ip dst {cidr} flowid 1:{class_id}"
                    )
            class_id += 1
        logger.info("tc rules applied for %d apps on %s", len(allocations), iface)

    # ── Windows PowerShell (IP-based throttling) ──────────────

    def _apply_powershell_rules(self, allocations: Dict[str, dict]) -> None:
        """
        Apply Windows QoS policies using New-NetQosPolicy with IP-based matching.

        This throttles by DESTINATION IP PREFIX — works for ANY browser.
        When YouTube is set to LOW, Chrome/Edge/Firefox ALL get throttled
        because the QoS policy matches the destination IP (Google servers),
        not the process name.

        YouTube uses DASH adaptive streaming — when throughput drops,
        the DASH engine detects it within 2-3 seconds and switches to
        a lower quality tier automatically.
        """
        # Step 1: Remove ALL existing PathWise QoS policies
        self._run_ps(
            "Get-NetQosPolicy -ErrorAction SilentlyContinue | "
            "Where-Object {$_.Name -like 'PW_*'} | "
            "Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue"
        )

        # Step 2: Create policies per app
        policy_count = 0
        for app_id, alloc in allocations.items():
            sig = APP_SIGNATURES.get(app_id)
            if not sig:
                continue

            rate_bps = max(1000, int(alloc["allocated_mbps"] * 1_000_000))
            priority_class = alloc.get("priority", "NORMAL")

            if priority_class == "BLOCKED":
                rate_bps = 1000  # 1 Kbps = effectively blocked

            # Get IP ranges for this app
            cidrs = list(sig.cidrs)
            # Add extra YouTube ranges for comprehensive coverage
            if app_id == "youtube":
                cidrs.extend(YOUTUBE_EXTRA_CIDRS)

            # Create IP-based throttle policies (one per CIDR)
            for i, cidr in enumerate(cidrs[:8]):  # max 8 CIDRs per app
                policy_name = f"PW_{app_id}_{i}"
                cmd = (
                    f"New-NetQosPolicy -Name '{policy_name}' "
                    f"-IPDstPrefixMatchCondition '{cidr}' "
                    f"-ThrottleRateActionBitsPerSecond {rate_bps} "
                    f"-PolicyStore ActiveStore "
                    f"-ErrorAction SilentlyContinue"
                )
                result = self._run_ps(cmd)
                if result.get("ok"):
                    policy_count += 1

            # Also create process-based policy for desktop apps (Zoom.exe etc)
            # This catches traffic that doesn't go through browser
            if sig.process_names and app_id not in ("youtube", "netflix", "twitch"):
                for proc in sig.process_names[:1]:
                    policy_name = f"PW_{app_id}_proc"
                    cmd = (
                        f"New-NetQosPolicy -Name '{policy_name}' "
                        f"-AppPathNameMatchCondition '{proc}' "
                        f"-ThrottleRateActionBitsPerSecond {rate_bps} "
                        f"-PolicyStore ActiveStore "
                        f"-ErrorAction SilentlyContinue"
                    )
                    result = self._run_ps(cmd)
                    if result.get("ok"):
                        policy_count += 1

        logger.info("Windows QoS: %d policies applied for %d apps", policy_count, len(allocations))

    # ── Simulation mode ───────────────────────────────────────

    def _apply_simulate(self, allocations: Dict[str, dict]) -> None:
        logger.info("[SIMULATE] Would apply rules for %d apps (no OS changes)", len(allocations))

    # ── Subprocess helpers ────────────────────────────────────

    def _run(self, cmd: str) -> dict:
        logger.debug("[shell] %s", cmd)
        result_dict = {"cmd": cmd, "ok": False, "stdout": "", "stderr": ""}
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            result_dict["ok"] = result.returncode == 0
            result_dict["stdout"] = result.stdout.strip()
            result_dict["stderr"] = result.stderr.strip()
            result_dict["returncode"] = result.returncode
        except subprocess.TimeoutExpired:
            result_dict["error"] = "timeout"
        except Exception as exc:
            result_dict["error"] = str(exc)
        self._commands_log.append(result_dict)
        return result_dict

    def _run_ps(self, script: str) -> dict:
        logger.debug("[powershell] %s", script)
        result_dict = {"cmd": script, "ok": False, "stdout": "", "stderr": ""}
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, timeout=15,
            )
            result_dict["ok"] = result.returncode == 0
            result_dict["stdout"] = result.stdout.strip()
            result_dict["stderr"] = result.stderr.strip()
            result_dict["returncode"] = result.returncode
        except subprocess.TimeoutExpired:
            result_dict["error"] = "timeout"
        except Exception as exc:
            result_dict["error"] = str(exc)
        self._commands_log.append(result_dict)
        return result_dict
