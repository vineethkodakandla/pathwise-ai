"""
Fiber Primary Link Collector.

Gathers telemetry from enterprise WAN routers via:
  1. SNMP polling (IF-MIB counters for bandwidth, DISMAN-PING-MIB for latency)
  2. gNMI streaming telemetry (modern alternative to SNMP)
  3. Active ping probes as fallback

Configuration via environment variables:
  FIBER_MODE        = "snmp" | "gnmi" | "ping"  (default: "ping")
  FIBER_ROUTER_IP   = router management IP       (default: "10.0.1.1")
  FIBER_SNMP_COMMUNITY = SNMP v2c community      (default: "public")
  FIBER_INTERFACE   = WAN interface name          (default: "GigabitEthernet0/0")
  FIBER_LINK_SPEED  = link speed in Mbps          (default: 1000)
  FIBER_PING_TARGET = IP to ping through fiber    (default: "8.8.8.8")
  FIBER_PING_IFACE  = OS interface to bind ping   (default: None)
"""

from __future__ import annotations
import os
import time
from typing import Optional

from server.state import TelemetryPoint
from server.collectors.base import (
    BaseCollector,
    run_ping,
    get_interface_bandwidth_util,
    snmp_get,
)


# ── SNMP OIDs for router telemetry ─────────────────────────────

# IF-MIB: Interface byte counters (index 1 = first WAN interface)
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10.1"
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16.1"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5.1"

# DISMAN-PING-MIB: IP SLA ping results
OID_PING_AVG_RTT = "1.3.6.1.2.1.80.1.3.1.5"
OID_PING_MIN_RTT = "1.3.6.1.2.1.80.1.3.1.4"
OID_PING_MAX_RTT = "1.3.6.1.2.1.80.1.3.1.6"
OID_PING_SENT = "1.3.6.1.2.1.80.1.3.1.7"
OID_PING_RECEIVED = "1.3.6.1.2.1.80.1.3.1.8"


class FiberCollector(BaseCollector):
    """
    Collects telemetry from the fiber primary WAN link.

    Supports three modes:
      - "snmp": Polls a Cisco/Juniper/MikroTik router via SNMP v2c.
                Uses IF-MIB for bandwidth utilization and DISMAN-PING-MIB
                for latency/jitter/loss (requires IP SLA probes configured).
      - "gnmi": Subscribes to gNMI streaming telemetry from the router.
                Most efficient — data pushed at configured interval.
      - "ping": Active ICMP probes through the fiber interface.
                Simplest setup — no router configuration needed.
                Bandwidth utilization read from OS interface counters.
    """

    def __init__(self):
        super().__init__(link_id="fiber-primary")

        self.mode = os.environ.get("FIBER_MODE", "ping").lower()
        self.router_ip = os.environ.get("FIBER_ROUTER_IP", "10.0.1.1")
        self.community = os.environ.get("FIBER_SNMP_COMMUNITY", "public")
        self.interface = os.environ.get("FIBER_INTERFACE", "GigabitEthernet0/0")
        self.link_speed = float(os.environ.get("FIBER_LINK_SPEED", "1000"))
        self.ping_target = os.environ.get("FIBER_PING_TARGET", "8.8.8.8")
        self.ping_iface = os.environ.get("FIBER_PING_IFACE", None)

        # State for SNMP delta calculations
        self._prev_in_octets: Optional[int] = None
        self._prev_out_octets: Optional[int] = None
        self._prev_time: Optional[float] = None

        print(f"[fiber] mode={self.mode}, router={self.router_ip}, "
              f"target={self.ping_target}, speed={self.link_speed}Mbps")

    async def collect(self) -> TelemetryPoint:
        if self.mode == "snmp":
            return await self._collect_snmp()
        elif self.mode == "gnmi":
            return await self._collect_gnmi()
        else:
            return await self._collect_ping()

    # ── Mode: Active Ping Probes ───────────────────────────────

    async def _collect_ping(self) -> TelemetryPoint:
        """
        Simplest collection method: ICMP ping through the fiber interface.
        Bandwidth from OS interface byte counters.
        """
        ping = await run_ping(
            target=self.ping_target,
            count=5,
            timeout_ms=1000,
            interface=self.ping_iface,
        )

        bw_util = await get_interface_bandwidth_util(
            interface=self.ping_iface or "eth0",
            link_speed_mbps=self.link_speed,
            interval=0.5,
        )

        return TelemetryPoint(
            timestamp=time.time(),
            link_id=self.link_id,
            latency_ms=max(0.5, ping.avg_latency_ms),
            jitter_ms=max(0, ping.jitter_ms),
            packet_loss_pct=ping.packet_loss_pct,
            bandwidth_util_pct=bw_util,
            rtt_ms=max(1, ping.rtt_ms),
        )

    # ── Mode: SNMP Polling ─────────────────────────────────────

    async def _collect_snmp(self) -> TelemetryPoint:
        """
        Poll router via SNMP v2c:
          - IF-MIB counters → bandwidth utilization (delta between polls)
          - DISMAN-PING-MIB → latency, jitter, loss (from router's IP SLA probes)

        Requires the router to have IP SLA/ping probes configured:
          Cisco: ip sla 1 / icmp-echo <far-end-ip> / frequency 1
          Juniper: services rpm probe ...
          MikroTik: /tool netwatch
        """
        now = time.time()

        # --- Bandwidth utilization from IF-MIB ---
        bw_util = 0.0
        in_octets_str = await snmp_get(self.router_ip, self.community, OID_IF_IN_OCTETS)
        out_octets_str = await snmp_get(self.router_ip, self.community, OID_IF_OUT_OCTETS)

        if in_octets_str and out_octets_str:
            in_octets = int(in_octets_str)
            out_octets = int(out_octets_str)

            if self._prev_in_octets is not None and self._prev_time is not None:
                dt = now - self._prev_time
                if dt > 0:
                    delta_bytes = (in_octets - self._prev_in_octets) + (out_octets - self._prev_out_octets)
                    # Handle 32-bit counter wrap (IF-MIB counters are Counter32)
                    if delta_bytes < 0:
                        delta_bytes += 2 ** 32
                    throughput_mbps = (delta_bytes * 8) / (dt * 1_000_000)
                    bw_util = min(100, (throughput_mbps / self.link_speed) * 100)

            self._prev_in_octets = in_octets
            self._prev_out_octets = out_octets
            self._prev_time = now

        # --- Latency/jitter/loss from DISMAN-PING-MIB ---
        avg_rtt_str = await snmp_get(self.router_ip, self.community, OID_PING_AVG_RTT)
        min_rtt_str = await snmp_get(self.router_ip, self.community, OID_PING_MIN_RTT)
        max_rtt_str = await snmp_get(self.router_ip, self.community, OID_PING_MAX_RTT)
        sent_str = await snmp_get(self.router_ip, self.community, OID_PING_SENT)
        rcvd_str = await snmp_get(self.router_ip, self.community, OID_PING_RECEIVED)

        latency = float(avg_rtt_str) if avg_rtt_str else 0
        min_rtt = float(min_rtt_str) if min_rtt_str else latency
        max_rtt = float(max_rtt_str) if max_rtt_str else latency
        jitter = (max_rtt - min_rtt) if max_rtt > min_rtt else latency * 0.1
        sent = int(sent_str) if sent_str else 1
        rcvd = int(rcvd_str) if rcvd_str else sent
        loss = ((sent - rcvd) / max(sent, 1)) * 100

        # If SNMP fails, fall back to active ping
        if latency == 0:
            ping = await run_ping(self.ping_target, count=5, timeout_ms=1000)
            latency = ping.avg_latency_ms
            jitter = ping.jitter_ms
            loss = ping.packet_loss_pct

        return TelemetryPoint(
            timestamp=now,
            link_id=self.link_id,
            latency_ms=max(0.5, latency),
            jitter_ms=max(0, jitter),
            packet_loss_pct=max(0, loss),
            bandwidth_util_pct=max(0, bw_util),
            rtt_ms=max(1, latency),
        )

    # ── Mode: gNMI Streaming ──────────────────────────────────

    async def _collect_gnmi(self) -> TelemetryPoint:
        """
        Receive streaming telemetry via gNMI (gRPC Network Management Interface).

        gNMI is the modern replacement for SNMP. The router pushes data at
        a configured interval (typically 1-10 seconds) rather than being polled.

        Requires:
          - pygnmi library (pip install pygnmi)
          - Router with gNMI enabled (Cisco IOS-XR, Juniper, Arista, Nokia)
          - gNMI port open (typically 57400)

        YANG paths subscribed:
          - openconfig-interfaces:interfaces/interface/state/counters
          - openconfig-network-instance:network-instances/.../bgp/...
        """
        try:
            from pygnmi.client import gNMIclient

            with gNMIclient(
                target=(self.router_ip, 57400),
                username=os.environ.get("FIBER_GNMI_USER", "admin"),
                password=os.environ.get("FIBER_GNMI_PASS", "admin"),
                insecure=True,
            ) as gc:
                result = gc.get(path=[
                    f"interfaces/interface[name={self.interface}]/state/counters"
                ])

                # Parse OpenConfig interface counters
                counters = result.get("notification", [{}])[0].get("update", [])
                in_octets = out_octets = 0
                for update in counters:
                    path = update.get("path", "")
                    val = update.get("val", 0)
                    if "in-octets" in path:
                        in_octets = int(val)
                    elif "out-octets" in path:
                        out_octets = int(val)

                # Compute bandwidth delta
                bw_util = 0.0
                now = time.time()
                if self._prev_in_octets is not None and self._prev_time:
                    dt = now - self._prev_time
                    if dt > 0:
                        delta = (in_octets - self._prev_in_octets) + (out_octets - self._prev_out_octets)
                        if delta < 0:
                            delta += 2 ** 64  # gNMI uses 64-bit counters
                        bw_util = min(100, (delta * 8) / (dt * 1_000_000 * self.link_speed) * 100)
                self._prev_in_octets = in_octets
                self._prev_out_octets = out_octets
                self._prev_time = now

        except (ImportError, Exception) as e:
            print(f"[fiber:gnmi] falling back to ping: {e}")
            bw_util = 0.0

        # Latency still via active probe (gNMI doesn't report ping metrics)
        ping = await run_ping(self.ping_target, count=5, timeout_ms=1000, interface=self.ping_iface)

        return TelemetryPoint(
            timestamp=time.time(),
            link_id=self.link_id,
            latency_ms=max(0.5, ping.avg_latency_ms),
            jitter_ms=max(0, ping.jitter_ms),
            packet_loss_pct=ping.packet_loss_pct,
            bandwidth_util_pct=bw_util,
            rtt_ms=max(1, ping.rtt_ms),
        )
