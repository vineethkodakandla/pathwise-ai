"""
Broadband Secondary Link Collector.

Gathers telemetry from a cable/DSL broadband connection via:
  1. Active ICMP ping probes bound to the broadband interface
  2. Linux interface byte counters for bandwidth utilization
  3. Optional: Cable modem SNMP for DOCSIS signal quality

Configuration via environment variables:
  BROADBAND_PING_TARGET  = IP to ping              (default: "1.1.1.1")
  BROADBAND_INTERFACE    = OS network interface     (default: "eth1")
  BROADBAND_LINK_SPEED   = link speed in Mbps       (default: 100)
  BROADBAND_PING_COUNT   = pings per sample         (default: 5)
  BROADBAND_MODEM_IP     = cable modem SNMP IP      (default: "192.168.100.1")
  BROADBAND_MODEM_COMMUNITY = SNMP community        (default: "public")
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

# DOCSIS cable modem SNMP OIDs
# docsIfSignalQuality — signal-to-noise ratio
OID_DOCSIS_SNR = "1.3.6.1.2.1.10.127.1.1.4.1.5"
# docsIfSigQUncorrectables — uncorrectable codeword errors (≈ packet loss)
OID_DOCSIS_UNCORRECTABLE = "1.3.6.1.2.1.10.127.1.1.4.1.4"
# docsIfSigQCorrecteds — correctable errors
OID_DOCSIS_CORRECTABLE = "1.3.6.1.2.1.10.127.1.1.4.1.3"
# docsIfDownChannelPower — downstream power level (dBmV)
OID_DOCSIS_DS_POWER = "1.3.6.1.2.1.10.127.1.1.1.1.6"


class BroadbandCollector(BaseCollector):
    """
    Collects telemetry from the broadband secondary WAN link.

    Primary method: active ICMP probes through the broadband-connected
    interface, combined with OS-level interface counters for bandwidth.

    Optional: polls the cable modem via SNMP for DOCSIS signal quality
    metrics (SNR, power levels, error rates). These are logged but the
    main telemetry still comes from active probing since DOCSIS stats
    don't directly give latency/jitter.

    Why active probing for broadband:
      - Home/office routers (Netgear, TP-Link) rarely support SNMP
      - No gNMI on consumer equipment
      - Ping accurately captures bufferbloat (the main broadband issue)
      - Cable modem stats are supplementary (signal quality context)
    """

    def __init__(self):
        super().__init__(link_id="broadband-secondary")

        self.ping_target = os.environ.get("BROADBAND_PING_TARGET", "1.1.1.1")
        self.interface = os.environ.get("BROADBAND_INTERFACE", "eth1")
        self.link_speed = float(os.environ.get("BROADBAND_LINK_SPEED", "100"))
        self.ping_count = int(os.environ.get("BROADBAND_PING_COUNT", "5"))
        self.modem_ip = os.environ.get("BROADBAND_MODEM_IP", "192.168.100.1")
        self.modem_community = os.environ.get("BROADBAND_MODEM_COMMUNITY", "public")

        # Track cable modem errors for delta-based loss estimation
        self._prev_uncorrectable: Optional[int] = None
        self._prev_correctable: Optional[int] = None

        print(f"[broadband] target={self.ping_target}, iface={self.interface}, "
              f"speed={self.link_speed}Mbps, modem={self.modem_ip}")

    async def collect(self) -> TelemetryPoint:
        """
        Collect broadband telemetry via active probing.

        Pipeline:
          1. Run ping probe bound to broadband interface → latency, jitter, loss
          2. Read interface byte counters → bandwidth utilization
          3. (Optional) Poll cable modem SNMP → DOCSIS signal quality
        """

        # ── Step 1: Active ICMP probe ──────────────────────────
        ping = await run_ping(
            target=self.ping_target,
            count=self.ping_count,
            timeout_ms=2000,  # Broadband can be slow, wider timeout
            interface=self.interface,
        )

        # ── Step 2: Bandwidth from OS interface counters ───────
        bw_util = await get_interface_bandwidth_util(
            interface=self.interface,
            link_speed_mbps=self.link_speed,
            interval=0.5,
        )

        # ── Step 3: Cable modem health (optional enrichment) ───
        modem_health = await self._poll_cable_modem()
        # If modem reports high error rate, supplement the loss figure
        if modem_health and modem_health["error_rate_pps"] > 0:
            # Blend: 80% from ping, 20% from modem error rate
            modem_loss_est = min(5.0, modem_health["error_rate_pps"] * 0.01)
            adjusted_loss = 0.8 * ping.packet_loss_pct + 0.2 * modem_loss_est
        else:
            adjusted_loss = ping.packet_loss_pct

        return TelemetryPoint(
            timestamp=time.time(),
            link_id=self.link_id,
            latency_ms=max(1, ping.avg_latency_ms),
            jitter_ms=max(0, ping.jitter_ms),
            packet_loss_pct=max(0, adjusted_loss),
            bandwidth_util_pct=bw_util,
            rtt_ms=max(1, ping.rtt_ms),
        )

    async def _poll_cable_modem(self) -> Optional[dict]:
        """
        Poll cable modem DOCSIS stats via SNMP.

        Returns signal quality metrics:
          - snr_db: Signal-to-noise ratio in dB (>30 is good)
          - ds_power_dbmv: Downstream power level
          - error_rate_pps: Uncorrectable errors per second (delta)

        Returns None if SNMP is unavailable (pysnmp not installed
        or modem doesn't respond).
        """
        try:
            snr_str = await snmp_get(self.modem_ip, self.modem_community, OID_DOCSIS_SNR)
            ds_power_str = await snmp_get(self.modem_ip, self.modem_community, OID_DOCSIS_DS_POWER)
            uncorr_str = await snmp_get(self.modem_ip, self.modem_community, OID_DOCSIS_UNCORRECTABLE)
            corr_str = await snmp_get(self.modem_ip, self.modem_community, OID_DOCSIS_CORRECTABLE)

            if not any([snr_str, ds_power_str, uncorr_str]):
                return None

            snr = float(snr_str) / 10.0 if snr_str else 0  # Often reported in 1/10 dB
            ds_power = float(ds_power_str) / 10.0 if ds_power_str else 0
            uncorr = int(uncorr_str) if uncorr_str else 0
            corr = int(corr_str) if corr_str else 0

            # Compute error delta
            error_rate = 0.0
            if self._prev_uncorrectable is not None:
                delta = uncorr - self._prev_uncorrectable
                if delta < 0:
                    delta += 2 ** 32  # Counter wrap
                error_rate = float(delta)  # errors in this interval
            self._prev_uncorrectable = uncorr
            self._prev_correctable = corr

            return {
                "snr_db": snr,
                "ds_power_dbmv": ds_power,
                "uncorrectable_errors": uncorr,
                "correctable_errors": corr,
                "error_rate_pps": error_rate,
            }
        except Exception:
            return None
