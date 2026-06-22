# services/telemetry-ingestion/parsers/snmp_parser.py

import time
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SNMPMetrics:
    """Raw SNMP counter values from a device interface."""
    if_in_octets: int
    if_out_octets: int
    if_in_errors: int
    if_in_discards: int
    if_speed: int  # bits per second
    timestamp: float


class SNMPParser:
    """
    Parses SNMP MIB data into telemetry metrics.

    Monitored OIDs:
    - IF-MIB::ifInOctets.{ifIndex}    (1.3.6.1.2.1.2.2.1.10)
    - IF-MIB::ifOutOctets.{ifIndex}   (1.3.6.1.2.1.2.2.1.16)
    - IF-MIB::ifInErrors.{ifIndex}    (1.3.6.1.2.1.2.2.1.14)
    - IF-MIB::ifInDiscards.{ifIndex}  (1.3.6.1.2.1.2.2.1.13)
    - IF-MIB::ifSpeed.{ifIndex}       (1.3.6.1.2.1.2.2.1.5)
    """

    def __init__(self):
        self._previous: dict[str, SNMPMetrics] = {}

    def parse_counters(
        self, device_id: str, if_index: int, raw_values: dict
    ) -> Optional[dict]:
        """
        Convert raw SNMP counter values to rate-based metrics.

        Uses delta between consecutive polls to compute:
        - bandwidth_util_pct: (delta_octets * 8) / (if_speed * delta_time) * 100
        - packet_loss_pct: (delta_errors + delta_discards) / delta_packets * 100
        """
        key = f"{device_id}:{if_index}"
        current = SNMPMetrics(
            if_in_octets=raw_values.get("ifInOctets", 0),
            if_out_octets=raw_values.get("ifOutOctets", 0),
            if_in_errors=raw_values.get("ifInErrors", 0),
            if_in_discards=raw_values.get("ifInDiscards", 0),
            if_speed=raw_values.get("ifSpeed", 1_000_000_000),
            timestamp=time.time(),
        )

        if key not in self._previous:
            self._previous[key] = current
            return None

        prev = self._previous[key]
        dt = current.timestamp - prev.timestamp
        if dt <= 0:
            return None

        delta_in = current.if_in_octets - prev.if_in_octets
        delta_out = current.if_out_octets - prev.if_out_octets
        delta_errors = current.if_in_errors - prev.if_in_errors
        delta_discards = current.if_in_discards - prev.if_in_discards

        # Handle 32-bit counter wraps
        if delta_in < 0:
            delta_in += 2**32
        if delta_out < 0:
            delta_out += 2**32

        total_bytes = delta_in + delta_out
        total_bits = total_bytes * 8
        bandwidth_util_pct = min(100.0, (total_bits / (current.if_speed * dt)) * 100)

        total_packets = max(1, total_bytes // 1500)  # Approximate packet count
        error_count = max(0, delta_errors + delta_discards)
        packet_loss_pct = min(100.0, (error_count / total_packets) * 100)

        self._previous[key] = current

        return {
            "bandwidth_util_pct": round(bandwidth_util_pct, 2),
            "packet_loss_pct": round(packet_loss_pct, 4),
            "timestamp": current.timestamp,
        }
