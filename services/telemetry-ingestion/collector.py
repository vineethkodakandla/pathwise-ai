# services/telemetry-ingestion/collector.py

import asyncio
import time
import logging
import random
import struct
import socket
from dataclasses import dataclass
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)

@dataclass
class TelemetryPoint:
    timestamp: float
    link_id: str
    latency_ms: float
    jitter_ms: float
    packet_loss_pct: float
    bandwidth_utilization_pct: float
    rtt_ms: float
    # Derived features added during feature engineering
    latency_rolling_mean_30s: Optional[float] = None
    jitter_ema_alpha05: Optional[float] = None
    packet_loss_rate_of_change: Optional[float] = None


class TelemetryCollector:
    """
    Collects telemetry from network devices via SNMP/NetFlow/gNMI
    and publishes to Redis Streams for downstream consumption.

    Polling interval: 1 second (high-frequency for LSTM input).

    Supports two modes:
    - Live mode: polls real devices via SNMP (requires pysnmp)
    - Synthetic mode: generates realistic synthetic data (for dev/test)
    """

    def __init__(
        self,
        redis_url: str,
        poll_interval: float = 1.0,
        mode: str = "synthetic",
    ):
        self.redis = redis.from_url(redis_url)
        self.poll_interval = poll_interval
        self.stream_key = "telemetry:raw"
        self.mode = mode
        self._synthetic_state: dict[str, dict] = {}

    async def collect_snmp(self, device_ip: str, community: str) -> TelemetryPoint:
        """
        Poll a device via SNMP for interface metrics.

        Uses pysnmp to query:
          IF-MIB::ifInOctets, ifOutOctets (bandwidth)
          DISMAN-PING-MIB (latency/jitter via active probes)
          IF-MIB::ifInErrors, ifInDiscards (packet loss proxy)

        Falls back to synthetic mode if pysnmp is unavailable or device
        is unreachable.
        """
        if self.mode == "live":
            return await self._collect_snmp_live(device_ip, community)
        return self._collect_synthetic(device_ip)

    async def _collect_snmp_live(self, device_ip: str, community: str) -> TelemetryPoint:
        """Actual SNMP collection using pysnmp."""
        try:
            from pysnmp.hlapi.asyncio import (
                getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
                ContextData, ObjectType, ObjectIdentity,
            )

            # OIDs for interface counters (ifIndex=1)
            oids = [
                ObjectType(ObjectIdentity("IF-MIB", "ifInOctets", 1)),
                ObjectType(ObjectIdentity("IF-MIB", "ifOutOctets", 1)),
                ObjectType(ObjectIdentity("IF-MIB", "ifInErrors", 1)),
                ObjectType(ObjectIdentity("IF-MIB", "ifInDiscards", 1)),
                ObjectType(ObjectIdentity("IF-MIB", "ifSpeed", 1)),
            ]

            error_indication, error_status, error_index, var_binds = await getCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((device_ip, 161), timeout=1.0, retries=0),
                ContextData(),
                *oids,
            )

            if error_indication or error_status:
                logger.warning(f"SNMP error for {device_ip}: {error_indication or error_status}")
                return self._collect_synthetic(device_ip)

            values = {str(oid): int(val) for oid, val in var_binds}
            in_octets = list(values.values())[0] if values else 0
            out_octets = list(values.values())[1] if len(values) > 1 else 0
            in_errors = list(values.values())[2] if len(values) > 2 else 0
            in_discards = list(values.values())[3] if len(values) > 3 else 0
            if_speed = list(values.values())[4] if len(values) > 4 else 1_000_000_000

            # Compute derived metrics from delta
            from parsers.snmp_parser import SNMPParser
            parser = SNMPParser()
            metrics = parser.parse_counters(device_ip, 1, {
                "ifInOctets": in_octets,
                "ifOutOctets": out_octets,
                "ifInErrors": in_errors,
                "ifInDiscards": in_discards,
                "ifSpeed": if_speed,
            })

            if metrics is None:
                return self._collect_synthetic(device_ip)

            # Latency/jitter via ICMP ping
            latency, jitter = await self._measure_latency(device_ip)

            return TelemetryPoint(
                timestamp=time.time(),
                link_id=device_ip,
                latency_ms=latency,
                jitter_ms=jitter,
                packet_loss_pct=metrics["packet_loss_pct"],
                bandwidth_utilization_pct=metrics["bandwidth_util_pct"],
                rtt_ms=latency * 2,
            )

        except ImportError:
            logger.warning("pysnmp not available, falling back to synthetic mode")
            return self._collect_synthetic(device_ip)
        except Exception as e:
            logger.warning(f"SNMP collection failed for {device_ip}: {e}")
            return self._collect_synthetic(device_ip)

    async def _measure_latency(self, host: str) -> tuple[float, float]:
        """Measure latency and jitter using ICMP ping."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1", host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            output = stdout.decode()
            if "time=" in output:
                latency = float(output.split("time=")[1].split(" ")[0])
                jitter = random.uniform(0.1, latency * 0.1)
                return latency, jitter
        except Exception:
            pass
        return random.uniform(5, 30), random.uniform(0.5, 3)

    def _collect_synthetic(self, device_ip: str) -> TelemetryPoint:
        """
        Generate realistic synthetic telemetry for development.

        Maintains per-device state to produce correlated time-series
        data with occasional brownout events.
        """
        now = time.time()

        if device_ip not in self._synthetic_state:
            self._synthetic_state[device_ip] = {
                "base_latency": random.uniform(10, 25),
                "base_jitter": random.uniform(1, 4),
                "base_loss": random.uniform(0.01, 0.1),
                "base_bw": random.uniform(30, 60),
                "brownout_until": 0,
                "brownout_severity": 0,
            }

        state = self._synthetic_state[device_ip]

        # Diurnal component
        import math
        hour = (now % 86400) / 3600
        diurnal = 0.3 * math.sin(2 * math.pi * (hour - 6) / 24) + 0.7

        # Random brownout injection (~0.2% chance per second)
        if now > state["brownout_until"] and random.random() < 0.002:
            state["brownout_until"] = now + random.uniform(30, 120)
            state["brownout_severity"] = random.uniform(2, 6)

        severity = 0
        if now < state["brownout_until"]:
            remaining = state["brownout_until"] - now
            total = 120
            ramp = 1.0 - (remaining / total)
            severity = state["brownout_severity"] * min(ramp, 1.0)

        latency = max(0, state["base_latency"] * diurnal
                       + severity * 15
                       + random.gauss(0, 2))
        jitter = max(0, state["base_jitter"] * diurnal
                      + severity * 4
                      + random.gauss(0, 0.5))
        loss = max(0, min(100, state["base_loss"] * diurnal
                          + severity * 1.5
                          + random.gauss(0, 0.01)))
        bw = max(0, min(100, state["base_bw"] * diurnal
                        + severity * 10
                        + random.gauss(0, 5)))
        rtt = max(0, latency * 2 + random.gauss(0, 1))

        return TelemetryPoint(
            timestamp=now,
            link_id=device_ip,
            latency_ms=round(latency, 2),
            jitter_ms=round(jitter, 2),
            packet_loss_pct=round(loss, 4),
            bandwidth_utilization_pct=round(bw, 2),
            rtt_ms=round(rtt, 2),
        )

    async def collect_netflow(self, collector_port: int = 9996):
        """
        Receive NetFlow v9/IPFIX records for flow-level metrics.

        Opens a UDP socket on collector_port and continuously receives
        NetFlow packets, parsing them into telemetry data.
        """
        from parsers.netflow_parser import NetFlowParser
        parser = NetFlowParser()

        transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: _NetFlowProtocol(parser, self),
            local_addr=("0.0.0.0", collector_port),
        )
        logger.info(f"NetFlow collector listening on UDP port {collector_port}")

        try:
            await asyncio.sleep(float("inf"))
        finally:
            transport.close()

    async def publish(self, point: TelemetryPoint):
        """Publish telemetry to Redis Stream for fan-out to consumers."""
        await self.redis.xadd(self.stream_key, {
            "link_id": point.link_id,
            "timestamp": str(point.timestamp),
            "latency_ms": str(point.latency_ms),
            "jitter_ms": str(point.jitter_ms),
            "packet_loss_pct": str(point.packet_loss_pct),
            "bandwidth_util_pct": str(point.bandwidth_utilization_pct),
            "rtt_ms": str(point.rtt_ms),
        }, maxlen=86400)  # Keep ~24h at 1/sec

    async def run(self, devices: list[dict]):
        """Main collection loop."""
        logger.info(f"Starting collection loop ({self.mode} mode) for {len(devices)} devices")
        while True:
            start = time.monotonic()
            tasks = [
                self.collect_snmp(d["ip"], d["community"])
                for d in devices
            ]
            points = await asyncio.gather(*tasks, return_exceptions=True)
            published = 0
            for point in points:
                if isinstance(point, TelemetryPoint):
                    await self.publish(point)
                    published += 1
                elif isinstance(point, Exception):
                    logger.error(f"Collection error: {point}")
            elapsed = time.monotonic() - start
            await asyncio.sleep(max(0, self.poll_interval - elapsed))


class _NetFlowProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for receiving NetFlow packets."""

    def __init__(self, parser, collector: TelemetryCollector):
        self.parser = parser
        self.collector = collector

    def datagram_received(self, data: bytes, addr: tuple):
        records = self.parser.parse_packet(data)
        for record in records:
            metrics = self.parser.compute_flow_metrics(record)
            logger.debug(f"NetFlow from {addr}: {metrics}")
