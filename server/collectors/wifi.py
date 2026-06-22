"""
WiFi Collector — gathers real telemetry from the laptop's WiFi adapter.

Pings a target IP through the WiFi interface and measures:
  - Latency (average RTT)
  - Jitter (standard deviation of RTTs)
  - Packet loss (% of pings lost)
  - Bandwidth utilization (from OS interface counters via psutil)
  - RTT (same as latency for ping)

Configuration via environment variables:
  WIFI_PING_TARGET   = IP to ping             (default: "8.8.8.8")
  WIFI_INTERFACE     = OS interface name       (default: "Wi-Fi")
  WIFI_LINK_SPEED    = link speed in Mbps      (default: 100)
  WIFI_PING_COUNT    = pings per sample        (default: 5)
"""

from __future__ import annotations
import os
import time

from server.state import TelemetryPoint
from server.collectors.base import (
    BaseCollector,
    run_ping,
    get_interface_bandwidth_util,
)


class WiFiCollector(BaseCollector):
    """
    Collects real telemetry from the laptop's WiFi adapter.
    This is what it is — WiFi data, labeled as WiFi.
    """

    def __init__(self):
        super().__init__(link_id="wifi")

        self.ping_target = os.environ.get("WIFI_PING_TARGET", "8.8.8.8")
        self.interface = os.environ.get("WIFI_INTERFACE", "Wi-Fi")
        self.link_speed = float(os.environ.get("WIFI_LINK_SPEED", "100"))
        self.ping_count = int(os.environ.get("WIFI_PING_COUNT", "5"))

        print(f"[wifi] target={self.ping_target}, iface={self.interface}, "
              f"speed={self.link_speed}Mbps, pings={self.ping_count}")

    async def collect(self) -> TelemetryPoint:
        """Ping through WiFi and read interface counters."""
        ping = await run_ping(
            target=self.ping_target,
            count=self.ping_count,
            timeout_ms=2000,
            interface=self.interface,
        )

        bw_util = await get_interface_bandwidth_util(
            interface=self.interface,
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
