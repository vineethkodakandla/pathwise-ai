"""
Ethernet (Fiber Primary) Collector — gathers real telemetry from the laptop's
Ethernet port, representing a fiber optic WAN connection.

Pings a target IP through the Ethernet interface and measures:
  - Latency (average RTT)
  - Jitter (standard deviation of RTTs)
  - Packet loss (% of pings lost)
  - Bandwidth utilization (from OS interface counters via psutil)
  - RTT (same as latency for ping)

Configuration via environment variables:
  ETHERNET_PING_TARGET   = IP to ping               (default: "1.1.1.1")
  ETHERNET_INTERFACE     = OS interface name         (default: "Ethernet")
  ETHERNET_LINK_SPEED    = link speed in Mbps        (default: 1000)
  ETHERNET_PING_COUNT    = pings per sample          (default: 5)

STATUS: DISABLED — This collector is implemented but not active.
To enable, set DATA_SOURCE=fiber_live and connect an Ethernet cable.
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


class EthernetCollector(BaseCollector):
    """
    Collects real telemetry from the laptop's Ethernet port.

    This represents the Fiber Primary WAN link. Ethernet provides a
    direct wired connection to the ISP's fiber network, giving the
    lowest latency and most stable connection of all link types.

    Typical fiber-via-Ethernet characteristics:
      - Latency: 2-15ms (very low, no wireless overhead)
      - Jitter: 0.1-2ms (extremely stable)
      - Packet loss: <0.01% (wired = reliable)
      - Bandwidth: 100Mbps-10Gbps depending on NIC and plan

    Requirements:
      - Ethernet cable plugged into the laptop's RJ-45 port
      - Connected to a fiber ONT/router (AT&T BGW320, Verizon G3100, etc.)
      - Interface must be "Up" in network settings

    How it works:
      1. Resolves the Ethernet interface name to its IP (via psutil)
      2. Sends ICMP pings bound to that IP using "ping -S <ip>"
      3. Reads interface byte counters via psutil for bandwidth
      4. Returns a TelemetryPoint with all 5 metrics
    """

    def __init__(self):
        super().__init__(link_id="fiber-primary")

        self.ping_target = os.environ.get("ETHERNET_PING_TARGET", "1.1.1.1")
        self.interface = os.environ.get("ETHERNET_INTERFACE", "Ethernet")
        self.link_speed = float(os.environ.get("ETHERNET_LINK_SPEED", "1000"))
        self.ping_count = int(os.environ.get("ETHERNET_PING_COUNT", "5"))

        print(f"[ethernet] target={self.ping_target}, iface={self.interface}, "
              f"speed={self.link_speed}Mbps, pings={self.ping_count}")

    async def collect(self) -> TelemetryPoint:
        """
        Collect one telemetry sample from the Ethernet interface.

        Pipeline:
          1. Run 5 ICMP pings through Ethernet → latency, jitter, loss
          2. Read psutil NIC byte counters → bandwidth utilization
          3. Package into TelemetryPoint
        """
        # Step 1: Active ICMP probe through Ethernet
        ping = await run_ping(
            target=self.ping_target,
            count=self.ping_count,
            timeout_ms=1000,
            interface=self.interface,
        )

        # Step 2: Bandwidth from OS interface counters
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
