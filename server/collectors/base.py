"""
Base collector interface and shared utilities.

All link-type collectors inherit from BaseCollector and implement collect().
"""

from __future__ import annotations
import asyncio
import re
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from server.state import TelemetryPoint


@dataclass
class PingResult:
    """Parsed result from an ICMP ping probe."""
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    jitter_ms: float
    packet_loss_pct: float
    rtt_ms: float
    samples: int


class BaseCollector(ABC):
    """
    Abstract base for all telemetry collectors.

    Each implementation gathers latency, jitter, packet loss, bandwidth
    utilization, and RTT from a specific link type (fiber, broadband,
    satellite, 5G).
    """

    def __init__(self, link_id: str):
        self.link_id = link_id
        self._last_point: Optional[TelemetryPoint] = None

    @abstractmethod
    async def collect(self) -> TelemetryPoint:
        """Gather one telemetry sample. Must be non-blocking."""
        ...

    async def safe_collect(self) -> Optional[TelemetryPoint]:
        """Collect with error handling — returns None on failure."""
        try:
            point = await self.collect()
            self._last_point = point
            return point
        except Exception as e:
            print(f"[collector:{self.link_id}] error: {e}")
            return self._last_point  # Return stale data rather than nothing


# ── Shared Ping Utility ────────────────────────────────────────

async def run_ping(
    target: str,
    count: int = 10,
    timeout_ms: int = 1000,
    interface: Optional[str] = None,
) -> PingResult:
    """
    Run an ICMP ping and parse the results.

    Works on both Linux and Windows.
    - Linux: supports binding to a specific interface via -I (e.g., eth1, wwan0)
    - Windows: supports binding to a specific source IP via -S (pass the IP
      address of the interface you want to use as the `interface` parameter)
    """
    import platform

    is_windows = platform.system() == "Windows"

    if is_windows:
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms)]
        if interface:
            # On Windows, -S binds to a source IP address.
            # If caller passed an interface name, try to resolve its IP.
            source_ip = _resolve_windows_interface_ip(interface)
            if source_ip:
                cmd.extend(["-S", source_ip])
        cmd.append(target)
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_ms // 1000 or 1)]
        if interface:
            cmd.extend(["-I", interface])
        cmd.append(target)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=count + 5)
    output = stdout.decode(errors="replace")

    # Parse individual RTT values
    if is_windows:
        rtts = [float(m) for m in re.findall(r"time[=<](\d+\.?\d*)ms", output)]
    else:
        rtts = [float(m) for m in re.findall(r"time=(\d+\.?\d*)\s*ms", output)]

    # Parse loss percentage
    loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*(?:loss|packet loss)", output)
    loss_pct = float(loss_match.group(1)) if loss_match else 0.0

    if not rtts:
        # All packets lost
        return PingResult(
            avg_latency_ms=0,
            min_latency_ms=0,
            max_latency_ms=0,
            jitter_ms=0,
            packet_loss_pct=100.0,
            rtt_ms=0,
            samples=0,
        )

    avg = statistics.mean(rtts)
    jitter = statistics.stdev(rtts) if len(rtts) > 1 else 0.0

    return PingResult(
        avg_latency_ms=avg,
        min_latency_ms=min(rtts),
        max_latency_ms=max(rtts),
        jitter_ms=jitter,
        packet_loss_pct=loss_pct,
        rtt_ms=avg,
        samples=len(rtts),
    )


# ── Windows Interface IP Resolution ────────────────────────────

def _resolve_windows_interface_ip(interface: str) -> Optional[str]:
    """
    Resolve a network interface name or IP to a usable source IP on Windows.

    If `interface` is already an IP address (e.g., "192.168.1.5"), return it.
    If it's an interface name (e.g., "Ethernet 2", "Wi-Fi"), look up its IP
    via ipconfig or the socket/psutil approach.
    """
    import re as _re

    # If it's already an IP address, return as-is
    if _re.match(r"^\d{1,3}(\.\d{1,3}){3}$", interface):
        return interface

    # Try psutil for clean interface → IP mapping
    try:
        import psutil
        addrs = psutil.net_if_addrs()
        for name, addr_list in addrs.items():
            if interface.lower() in name.lower():
                for addr in addr_list:
                    if addr.family.name == "AF_INET":
                        return addr.address
    except ImportError:
        pass

    # Fallback: parse ipconfig output
    try:
        import subprocess
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.split("\n")
        in_section = False
        for line in lines:
            if interface.lower() in line.lower():
                in_section = True
            elif in_section and "IPv4" in line:
                match = _re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", line)
                if match:
                    return match.group(1)
            elif in_section and line.strip() == "":
                in_section = False
    except Exception:
        pass

    return None


# ── Shared Interface Bandwidth Utility ─────────────────────────

_win_prev_counters: dict[str, tuple[float, int, int]] = {}


async def get_interface_bandwidth_util(
    interface: str,
    link_speed_mbps: float,
    interval: float = 1.0,
) -> float:
    """
    Measure bandwidth utilization on a network interface.

    Linux: reads byte counters from /sys/class/net/<iface>/statistics/.
    Windows: uses psutil for per-interface I/O counters.

    Returns utilization as a percentage (0-100).
    """
    import platform

    if platform.system() == "Windows":
        return await _get_bandwidth_windows(interface, link_speed_mbps, interval)

    rx_path = f"/sys/class/net/{interface}/statistics/rx_bytes"
    tx_path = f"/sys/class/net/{interface}/statistics/tx_bytes"

    try:
        with open(rx_path) as f:
            rx_before = int(f.read().strip())
        with open(tx_path) as f:
            tx_before = int(f.read().strip())

        await asyncio.sleep(interval)

        with open(rx_path) as f:
            rx_after = int(f.read().strip())
        with open(tx_path) as f:
            tx_after = int(f.read().strip())

        total_bytes = (rx_after - rx_before) + (tx_after - tx_before)
        total_bits = total_bytes * 8
        throughput_mbps = total_bits / (interval * 1_000_000)
        utilization = (throughput_mbps / link_speed_mbps) * 100

        return max(0.0, min(100.0, utilization))
    except (FileNotFoundError, ValueError):
        return 0.0


async def _get_bandwidth_windows(
    interface: str, link_speed_mbps: float, interval: float
) -> float:
    """
    Measure bandwidth utilization on Windows using psutil per-NIC I/O counters.
    Falls back to 0.0 if psutil is not installed.
    """
    try:
        import psutil
    except ImportError:
        return 0.0

    # Find the matching NIC name (partial match)
    def _find_nic():
        counters = psutil.net_io_counters(pernic=True)
        for name in counters:
            if interface.lower() in name.lower():
                return name
        # If no match, return the first non-loopback NIC
        for name in counters:
            if "loopback" not in name.lower():
                return name
        return None

    nic_name = _find_nic()
    if not nic_name:
        return 0.0

    counters_before = psutil.net_io_counters(pernic=True).get(nic_name)
    if not counters_before:
        return 0.0

    before_bytes = counters_before.bytes_sent + counters_before.bytes_recv
    before_time = asyncio.get_event_loop().time()

    await asyncio.sleep(interval)

    counters_after = psutil.net_io_counters(pernic=True).get(nic_name)
    if not counters_after:
        return 0.0

    after_bytes = counters_after.bytes_sent + counters_after.bytes_recv
    after_time = asyncio.get_event_loop().time()

    dt = after_time - before_time
    if dt <= 0:
        return 0.0

    throughput_mbps = ((after_bytes - before_bytes) * 8) / (dt * 1_000_000)
    utilization = (throughput_mbps / link_speed_mbps) * 100
    return max(0.0, min(100.0, utilization))


# ── SNMP Utility ───────────────────────────────────────────────

async def snmp_get(host: str, community: str, oid: str, port: int = 161) -> Optional[str]:
    """
    Perform a single SNMP GET using pysnmp.
    Returns the value as a string, or None on failure.
    """
    try:
        from pysnmp.hlapi.v3arch.asyncio import (
            SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity, get_cmd,
        )

        engine = SnmpEngine()
        transport = await UdpTransportTarget.create((host, port))

        error_indication, error_status, error_index, var_binds = await get_cmd(
            engine, CommunityData(community), transport,
            ContextData(), ObjectType(ObjectIdentity(oid)),
        )

        if error_indication or error_status:
            return None

        for _, val in var_binds:
            return str(val)
    except ImportError:
        return None
    except Exception:
        return None
    return None
