"""
5G Mobile Link Collector.

Gathers telemetry from 5G connections via:
  1. 5G CPE router HTTP API (Inseego, Netgear, ZTE, Huawei)
  2. Android Termux/ADB bridge for phone-based probing
  3. Active ping probes as fallback

Configuration via environment variables:
  FIVEG_MODE          = "cpe" | "android" | "ping"  (default: "ping")
  FIVEG_CPE_IP        = CPE router IP                (default: "192.168.1.1")
  FIVEG_CPE_AUTH      = CPE auth token/cookie        (default: "")
  FIVEG_CPE_MODEL     = "inseego" | "netgear" | "zte" | "huawei" | "generic"
  FIVEG_INTERFACE     = OS cellular interface         (default: "wwan0")
  FIVEG_PING_TARGET   = IP to ping through 5G        (default: "8.8.8.8")
  FIVEG_LINK_SPEED    = 5G capacity in Mbps          (default: 300)
  FIVEG_ADB_SERIAL    = Android device serial for ADB (default: "")
"""

from __future__ import annotations
import json
import os
import time
from typing import Optional

from server.state import TelemetryPoint
from server.collectors.base import (
    BaseCollector,
    run_ping,
    get_interface_bandwidth_util,
)


# ── CPE Router API Endpoints by Vendor ─────────────────────────
# Each 5G CPE router exposes status via different HTTP endpoints.
# These are the most common models used as fixed wireless terminals.

CPE_ENDPOINTS = {
    "inseego": {
        # Inseego FW2000e / MiFi X PRO
        "url": "/cgi-bin/qcmap_web_cgi",
        "method": "POST",
        "body": {"module": "signal", "action": "status"},
        "parse": "_parse_inseego",
    },
    "netgear": {
        # Netgear Nighthawk M6 / M6 Pro
        "url": "/api/model.json",
        "method": "GET",
        "body": None,
        "parse": "_parse_netgear",
    },
    "zte": {
        # ZTE MC801A / MC888
        "url": "/goform/goform_get_cmd_process?cmd=network_type,rsrp,rsrq,sinr,cell_id,nr_serving_cell_info",
        "method": "GET",
        "body": None,
        "parse": "_parse_zte",
    },
    "huawei": {
        # Huawei CPE Pro 2 / 5G CPE
        "url": "/api/device/signal",
        "method": "GET",
        "body": None,
        "parse": "_parse_huawei",
    },
    "generic": {
        # Fallback — just use ping, no CPE API
        "url": None,
        "method": None,
        "body": None,
        "parse": None,
    },
}


class FiveGCollector(BaseCollector):
    """
    Collects telemetry from the 5G mobile WAN link.

    5G telemetry is unique because the transport layer (cellular radio)
    introduces variable latency that depends on:
      - Radio conditions (RSRP, SINR)
      - Handoff events (tower-to-tower transitions)
      - Frequency band (sub-6 GHz vs mmWave)
      - Network load (shared cell capacity)

    The collector combines two data sources:
      1. CPE router API → radio-level metrics (signal quality, band, state)
      2. Active ping probes → user-experienced latency/jitter/loss
         (Must be bound to the cellular interface to avoid going over WiFi)

    Modes:
      "cpe"     — Polls 5G CPE router HTTP API + active ping
      "android" — Uses ADB to query Android telephony + ping from phone
      "ping"    — Active ICMP probes only (simplest)
    """

    def __init__(self):
        super().__init__(link_id="5g-mobile")

        self.mode = os.environ.get("FIVEG_MODE", "ping").lower()
        self.cpe_ip = os.environ.get("FIVEG_CPE_IP", "192.168.1.1")
        self.cpe_auth = os.environ.get("FIVEG_CPE_AUTH", "")
        self.cpe_model = os.environ.get("FIVEG_CPE_MODEL", "generic").lower()
        self.interface = os.environ.get("FIVEG_INTERFACE", "wwan0")
        self.ping_target = os.environ.get("FIVEG_PING_TARGET", "8.8.8.8")
        self.link_speed = float(os.environ.get("FIVEG_LINK_SPEED", "300"))
        self.adb_serial = os.environ.get("FIVEG_ADB_SERIAL", "")

        # Cache for radio metrics (updated from CPE, used for context)
        self._radio_state: dict = {}

        print(f"[5g] mode={self.mode}, cpe={self.cpe_ip} ({self.cpe_model}), "
              f"iface={self.interface}, target={self.ping_target}")

    async def collect(self) -> TelemetryPoint:
        if self.mode == "cpe":
            return await self._collect_cpe()
        elif self.mode == "android":
            return await self._collect_android()
        else:
            return await self._collect_ping()

    # ── Mode: CPE Router API + Ping ────────────────────────────

    async def _collect_cpe(self) -> TelemetryPoint:
        """
        Poll the 5G CPE router's HTTP API for radio metrics, then
        run active ping probes for latency/jitter/loss.

        Radio metrics from CPE:
          - RSRP (Reference Signal Received Power): -44 to -140 dBm
            > -80 = excellent, -80 to -90 = good, -90 to -100 = fair, < -100 = poor
          - SINR (Signal to Interference + Noise Ratio): -20 to 30 dB
            > 20 = excellent, 13-20 = good, 0-13 = fair, < 0 = poor
          - Band info: n41 (2.5 GHz), n77 (3.7 GHz), n258/n260 (mmWave)
          - Connection state: connected, searching, handoff

        These don't directly give us latency, but they predict it:
          - Low SINR → expect higher latency + jitter
          - Handoff events → 200-500ms latency spikes
          - mmWave → lower latency than sub-6 GHz
        """
        import asyncio

        # Fetch radio metrics from CPE (non-blocking)
        radio = await self._fetch_cpe_radio()
        if radio:
            self._radio_state = radio

        # Active ping through cellular interface
        ping = await run_ping(
            target=self.ping_target,
            count=5,
            timeout_ms=2000,
            interface=self.interface,
        )

        # Bandwidth from OS counters
        bw_util = await get_interface_bandwidth_util(
            interface=self.interface,
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

    async def _fetch_cpe_radio(self) -> Optional[dict]:
        """Fetch radio-level metrics from the CPE router's HTTP API."""
        endpoint = CPE_ENDPOINTS.get(self.cpe_model, CPE_ENDPOINTS["generic"])
        if not endpoint["url"]:
            return None

        try:
            import aiohttp

            url = f"http://{self.cpe_ip}{endpoint['url']}"
            headers = {}
            if self.cpe_auth:
                headers["Authorization"] = f"Bearer {self.cpe_auth}"

            async with aiohttp.ClientSession() as session:
                if endpoint["method"] == "POST":
                    async with session.post(url, json=endpoint["body"],
                                            headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        data = await resp.json()
                elif endpoint["method"] == "GET":
                    async with session.get(url, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        data = await resp.json()
                else:
                    return None

            # Parse vendor-specific response
            parser = getattr(self, endpoint["parse"], None)
            if parser:
                return parser(data)
            return None

        except ImportError:
            # aiohttp not installed
            return None
        except Exception as e:
            print(f"[5g:cpe] API error: {e}")
            return None

    def _parse_inseego(self, data: dict) -> dict:
        """Parse Inseego FW2000e / MiFi X PRO response."""
        return {
            "rsrp": data.get("rsrp", 0),
            "sinr": data.get("sinr", 0),
            "band": data.get("nr_band", "unknown"),
            "connection_state": data.get("connection_state", "unknown"),
            "technology": "5G-NR" if data.get("nr_band") else "LTE",
        }

    def _parse_netgear(self, data: dict) -> dict:
        """Parse Netgear Nighthawk M6 response."""
        wwan = data.get("wwan", {})
        signal = wwan.get("signalBar", {})
        return {
            "rsrp": signal.get("rsrp", 0),
            "sinr": signal.get("sinr", 0),
            "band": wwan.get("currentNRBand", wwan.get("currentLTEBand", "unknown")),
            "connection_state": wwan.get("connectionStatus", "unknown"),
            "technology": "5G-NR" if wwan.get("currentNRBand") else "LTE",
        }

    def _parse_zte(self, data: dict) -> dict:
        """Parse ZTE MC801A / MC888 response."""
        return {
            "rsrp": int(data.get("rsrp", "0").rstrip("dBm") or 0),
            "sinr": int(data.get("sinr", "0").rstrip("dB") or 0),
            "band": data.get("nr_serving_cell_info", "unknown"),
            "connection_state": data.get("network_type", "unknown"),
            "technology": "5G-NR" if "NR" in data.get("network_type", "") else "LTE",
        }

    def _parse_huawei(self, data: dict) -> dict:
        """Parse Huawei CPE Pro 2 response."""
        return {
            "rsrp": int(data.get("rsrp", "0").rstrip("dBm") or 0),
            "sinr": int(data.get("sinr", "0").rstrip("dB") or 0),
            "band": data.get("band", "unknown"),
            "connection_state": data.get("workmode", "unknown"),
            "technology": "5G-NR" if "NR" in data.get("workmode", "") else "LTE",
        }

    # ── Mode: Android ADB Bridge ───────────────────────────────

    async def _collect_android(self) -> TelemetryPoint:
        """
        Use ADB to query an Android phone for 5G telemetry, then
        run ping from the phone over mobile data.

        Requirements:
          - Android phone connected via USB with ADB debugging enabled
          - ADB installed on the PathWise server
          - Phone on mobile data (WiFi off or using mobile for data)

        ADB commands used:
          adb shell dumpsys telephony.registry
            → SignalStrength, CellInfo, DataConnectionState
          adb shell ping -c 5 -I rmnet_data0 8.8.8.8
            → Latency/jitter/loss through cellular interface

        Android internal interface is typically rmnet_data0 (Qualcomm)
        or ccmni0 (MediaTek).
        """
        import asyncio

        adb_prefix = ["adb"]
        if self.adb_serial:
            adb_prefix.extend(["-s", self.adb_serial])

        # Get signal strength from Android telephony
        try:
            proc = await asyncio.create_subprocess_exec(
                *adb_prefix, "shell", "dumpsys", "telephony.registry",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            output = stdout.decode(errors="replace")

            # Parse SignalStrength from dumpsys output
            import re
            rsrp_match = re.search(r"mRsrp=(-?\d+)", output)
            sinr_match = re.search(r"mSinr=(-?\d+)", output)
            if rsrp_match:
                self._radio_state["rsrp"] = int(rsrp_match.group(1))
            if sinr_match:
                self._radio_state["sinr"] = int(sinr_match.group(1))

        except Exception as e:
            print(f"[5g:android] telephony query failed: {e}")

        # Run ping from the phone
        try:
            proc = await asyncio.create_subprocess_exec(
                *adb_prefix, "shell",
                "ping", "-c", "5", "-W", "2", "-I", "rmnet_data0", self.ping_target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            output = stdout.decode(errors="replace")

            import re
            rtts = [float(m) for m in re.findall(r"time=(\d+\.?\d*)\s*ms", output)]
            loss_match = re.search(r"(\d+)%\s*packet loss", output)
            loss_pct = float(loss_match.group(1)) if loss_match else 0

            if rtts:
                import statistics
                latency = statistics.mean(rtts)
                jitter = statistics.stdev(rtts) if len(rtts) > 1 else 0
            else:
                latency = 0
                jitter = 0

        except Exception as e:
            print(f"[5g:android] ping failed: {e}")
            # Fallback to local ping
            ping = await run_ping(self.ping_target, count=5)
            latency = ping.avg_latency_ms
            jitter = ping.jitter_ms
            loss_pct = ping.packet_loss_pct

        return TelemetryPoint(
            timestamp=time.time(),
            link_id=self.link_id,
            latency_ms=max(1, latency),
            jitter_ms=max(0, jitter),
            packet_loss_pct=max(0, loss_pct),
            bandwidth_util_pct=0,  # Can't easily get from ADB
            rtt_ms=max(1, latency),
        )

    # ── Mode: Active Ping Fallback ─────────────────────────────

    async def _collect_ping(self) -> TelemetryPoint:
        """Simple ping probe through the 5G interface."""
        ping = await run_ping(
            target=self.ping_target,
            count=5,
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
            latency_ms=max(1, ping.avg_latency_ms),
            jitter_ms=max(0, ping.jitter_ms),
            packet_loss_pct=ping.packet_loss_pct,
            bandwidth_util_pct=bw_util,
            rtt_ms=max(1, ping.rtt_ms),
        )
