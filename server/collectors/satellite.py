"""
Satellite Backup Link Collector.

Gathers telemetry from satellite internet connections via:
  1. Starlink dish gRPC API (LEO satellite — 192.168.100.1:9200)
  2. Traditional VSAT modem SNMP (GEO satellite — Hughes, Viasat)
  3. Active ping probes as fallback

Configuration via environment variables:
  SATELLITE_MODE       = "starlink" | "vsat" | "ping"  (default: "ping")
  SATELLITE_DISH_IP    = Starlink dish IP               (default: "192.168.100.1")
  SATELLITE_GRPC_PORT  = Starlink gRPC port             (default: 9200)
  SATELLITE_VSAT_IP    = VSAT modem SNMP IP             (default: "192.168.1.1")
  SATELLITE_VSAT_COMMUNITY = SNMP community             (default: "public")
  SATELLITE_PING_TARGET = fallback ping target          (default: "8.8.4.4")
  SATELLITE_PING_IFACE  = OS interface for ping         (default: None)
  SATELLITE_LINK_SPEED  = capacity in Mbps              (default: 200)
"""

from __future__ import annotations
import os
import statistics
import time
from typing import Optional

from server.state import TelemetryPoint
from server.collectors.base import (
    BaseCollector,
    run_ping,
    get_interface_bandwidth_util,
    snmp_get,
)


class SatelliteCollector(BaseCollector):
    """
    Collects telemetry from the satellite backup WAN link.

    Supports three modes:

    "starlink" — Starlink LEO satellite:
      Every Starlink dish runs a local gRPC server that exposes detailed
      telemetry without authentication. The GetHistory RPC returns arrays
      of per-second measurements for the last 15 minutes:
        - pop_ping_latency_ms: RTT to nearest Starlink PoP
        - pop_ping_drop_rate: fraction of pings lost (0.0 - 1.0)
        - downlink_throughput_bps / uplink_throughput_bps: current speed
      Jitter is computed as stdev of recent latency samples.

      Unique Starlink patterns captured:
        - Satellite handoffs (~15s intervals, brief latency spikes)
        - Obstruction events (trees/buildings blocking sky → drops)
        - Cell congestion during peak hours
        - Weather-related degradation (rain/snow on Ka-band)

    "vsat" — Traditional GEO satellite (Hughes, Viasat):
      Polls the satellite modem via SNMP for vendor-specific OIDs.
      GEO satellites have inherent ~550-650ms latency (speed of light
      to geostationary orbit at 35,786 km and back).

    "ping" — Active ICMP probes:
      Simplest fallback — pings through the satellite interface.
    """

    def __init__(self):
        super().__init__(link_id="satellite-backup")

        self.mode = os.environ.get("SATELLITE_MODE", "ping").lower()
        self.dish_ip = os.environ.get("SATELLITE_DISH_IP", "192.168.100.1")
        self.grpc_port = int(os.environ.get("SATELLITE_GRPC_PORT", "9200"))
        self.vsat_ip = os.environ.get("SATELLITE_VSAT_IP", "192.168.1.1")
        self.vsat_community = os.environ.get("SATELLITE_VSAT_COMMUNITY", "public")
        self.ping_target = os.environ.get("SATELLITE_PING_TARGET", "8.8.4.4")
        self.ping_iface = os.environ.get("SATELLITE_PING_IFACE", None)
        self.link_speed = float(os.environ.get("SATELLITE_LINK_SPEED", "200"))

        print(f"[satellite] mode={self.mode}, dish={self.dish_ip}:{self.grpc_port}, "
              f"target={self.ping_target}")

    async def collect(self) -> TelemetryPoint:
        if self.mode == "starlink":
            return await self._collect_starlink()
        elif self.mode == "vsat":
            return await self._collect_vsat()
        else:
            return await self._collect_ping()

    # ── Mode: Starlink gRPC ────────────────────────────────────

    async def _collect_starlink(self) -> TelemetryPoint:
        """
        Pull real-time telemetry from Starlink dish via local gRPC API.

        The Starlink dish exposes a gRPC service at 192.168.100.1:9200.
        No authentication required from the local network.

        Uses our lightweight stub (starlink_stub.py) which talks to the
        dish via HTTP JSON or raw gRPC bytes — no compiled .proto files needed.

        Data returned by the dish:
          pop_ping_latency_ms: per-second RTT to nearest Starlink PoP (900 samples)
          pop_ping_drop_rate:  fraction of pings lost per second (0.0 - 1.0)
          downlink/uplink_throughput_bps: current speeds
        """
        try:
            from server.collectors.starlink_stub import fetch_starlink_history

            history = await fetch_starlink_history(self.dish_ip, self.grpc_port)
            if not history or not history.pop_ping_latency_ms:
                return await self._collect_ping()

            # Latest samples
            latency_samples = history.pop_ping_latency_ms[-60:]
            drop_rates = history.pop_ping_drop_rate[-60:]
            dl_bps = history.downlink_throughput_bps[-10:]
            ul_bps = history.uplink_throughput_bps[-10:]

            # Filter out zero-latency samples (dish reports 0 during outages)
            valid_latencies = [l for l in latency_samples if l > 0]
            if not valid_latencies:
                return await self._collect_ping()

            # Current latency = most recent valid sample
            latency = valid_latencies[-1]

            # Jitter = standard deviation of recent samples
            jitter = statistics.stdev(valid_latencies[-20:]) if len(valid_latencies) >= 2 else 0

            # Packet loss from drop rate (average of recent samples)
            valid_drops = [d for d in drop_rates if d is not None]
            packet_loss = (sum(valid_drops[-10:]) / max(len(valid_drops[-10:]), 1)) * 100

            # Bandwidth utilization
            avg_dl = sum(dl_bps[-5:]) / max(len(dl_bps[-5:]), 1) if dl_bps else 0
            avg_ul = sum(ul_bps[-5:]) / max(len(ul_bps[-5:]), 1) if ul_bps else 0
            total_mbps = (avg_dl + avg_ul) / 1_000_000
            bw_util = min(100, (total_mbps / self.link_speed) * 100)

            return TelemetryPoint(
                timestamp=time.time(),
                link_id=self.link_id,
                latency_ms=max(1, latency),
                jitter_ms=max(0, jitter),
                packet_loss_pct=max(0, min(100, packet_loss)),
                bandwidth_util_pct=max(0, bw_util),
                rtt_ms=max(1, latency),  # Starlink reports RTT
            )

        except Exception as e:
            print(f"[satellite:starlink] failed, falling back to ping: {e}")
            return await self._collect_ping()

    # ── Mode: Traditional VSAT SNMP ────────────────────────────

    async def _collect_vsat(self) -> TelemetryPoint:
        """
        Poll traditional GEO satellite modem (Hughes/Viasat) via SNMP.

        GEO satellites orbit at 35,786 km altitude. Signal travels at
        speed of light: ~120ms one-way to satellite + ~120ms back down
        = ~480-650ms total RTT depending on path and processing.

        Vendor-specific OIDs vary by modem manufacturer. Common patterns:
          Hughes HT2000w: enterprises.4491.2.x for DOCSIS-like stats
          Viasat/Exede: enterprises.xxxx for proprietary metrics
          iDirect: enterprises.16857 for iDirect-specific MIB

        Since vendor OIDs are proprietary, this primarily uses the
        standard IP-MIB and IF-MIB, supplemented by ping probes.
        """
        # Standard SNMP for bandwidth
        bw_util = 0.0
        in_octets = await snmp_get(self.vsat_ip, self.vsat_community, "1.3.6.1.2.1.2.2.1.10.1")
        out_octets = await snmp_get(self.vsat_ip, self.vsat_community, "1.3.6.1.2.1.2.2.1.16.1")
        # (Would need delta calculation like FiberCollector — simplified here)

        # Latency via active probe (SNMP doesn't give us RTT on most VSAT modems)
        ping = await run_ping(
            target=self.ping_target,
            count=5,
            timeout_ms=3000,  # GEO satellite needs higher timeout
            interface=self.ping_iface,
        )

        return TelemetryPoint(
            timestamp=time.time(),
            link_id=self.link_id,
            latency_ms=max(1, ping.avg_latency_ms),
            jitter_ms=max(0, ping.jitter_ms),
            packet_loss_pct=ping.packet_loss_pct,
            bandwidth_util_pct=bw_util,
            rtt_ms=max(1, ping.rtt_ms),
        )

    # ── Mode: Active Ping Fallback ─────────────────────────────

    async def _collect_ping(self) -> TelemetryPoint:
        """Simple ping probe through the satellite interface."""
        ping = await run_ping(
            target=self.ping_target,
            count=5,
            timeout_ms=3000,
            interface=self.ping_iface,
        )

        bw_util = await get_interface_bandwidth_util(
            interface=self.ping_iface or "sat0",
            link_speed_mbps=self.link_speed,
            interval=0.5,
        )

        return TelemetryPoint(
            timestamp=time.time(),
            link_id=self.link_id,
            latency_ms=max(1, ping.avg_latency_ms),
            jitter_ms=max(0, ping.jitter_ms),
            packet_loss_pct=ping.packet_loss_pct,
            bandwidth_util_pct=bw_util,
            rtt_ms=max(1, ping.rtt_ms),
        )
