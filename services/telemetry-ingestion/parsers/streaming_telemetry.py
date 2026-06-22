# services/telemetry-ingestion/parsers/streaming_telemetry.py

import json
import logging
from dataclasses import dataclass
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class gNMIUpdate:
    """Parsed gNMI subscription update."""
    path: str
    value: float
    timestamp_ns: int
    origin: str


class StreamingTelemetryParser:
    """
    Parser for model-driven streaming telemetry (gNMI/gRPC).

    Supports OpenConfig YANG paths for network interface metrics:
    - /interfaces/interface[name=*]/state/counters
    - /interfaces/interface[name=*]/state/oper-status
    - /qos/interfaces/interface[name=*]/output/queues/queue[name=*]/state

    gNMI subscriptions push updates at configurable intervals
    (target: 1-second sample interval for PathWise).
    """

    # OpenConfig paths to PathWise metric mapping
    PATH_MAPPING = {
        "/interfaces/interface/state/counters/in-octets": "in_octets",
        "/interfaces/interface/state/counters/out-octets": "out_octets",
        "/interfaces/interface/state/counters/in-errors": "in_errors",
        "/interfaces/interface/state/counters/in-discards": "in_discards",
        "/interfaces/interface/state/counters/out-errors": "out_errors",
        "/interfaces/interface/state/oper-status": "oper_status",
        "/qos/interfaces/interface/output/queues/queue/state/transmit-octets": "queue_tx_octets",
        "/qos/interfaces/interface/output/queues/queue/state/dropped-pkts": "queue_drops",
    }

    def __init__(self):
        self._callbacks: list[Callable] = []
        self._previous_counters: dict[str, dict] = {}

    def register_callback(self, callback: Callable):
        """Register a callback for processed telemetry updates."""
        self._callbacks.append(callback)

    def parse_gnmi_notification(self, notification: dict) -> list[gNMIUpdate]:
        """
        Parse a gNMI SubscribeResponse notification.

        Expected format (JSON-IETF encoding):
        {
            "update": {
                "timestamp": 1706000000000000000,
                "prefix": {"elem": [{"name": "interfaces"}, ...]},
                "update": [
                    {"path": {"elem": [...]}, "val": {"uintVal": 12345}},
                    ...
                ]
            }
        }
        """
        updates = []
        try:
            update_msg = notification.get("update", {})
            timestamp_ns = update_msg.get("timestamp", 0)
            prefix = self._path_to_string(update_msg.get("prefix", {}))

            for upd in update_msg.get("update", []):
                path = prefix + self._path_to_string(upd.get("path", {}))
                value = self._extract_value(upd.get("val", {}))

                if value is not None:
                    updates.append(gNMIUpdate(
                        path=path,
                        value=value,
                        timestamp_ns=timestamp_ns,
                        origin=update_msg.get("prefix", {}).get("origin", "openconfig"),
                    ))
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse gNMI notification: {e}")

        return updates

    def process_updates(
        self, interface_name: str, updates: list[gNMIUpdate]
    ) -> Optional[dict]:
        """
        Convert gNMI counter updates to rate-based telemetry metrics.

        Computes deltas between consecutive updates for counter-based OIDs.
        """
        current = {}
        for update in updates:
            metric_name = self._resolve_metric(update.path)
            if metric_name:
                current[metric_name] = update.value

        if interface_name not in self._previous_counters:
            self._previous_counters[interface_name] = current
            return None

        prev = self._previous_counters[interface_name]
        self._previous_counters[interface_name] = current

        metrics = {}
        if "in_octets" in current and "in_octets" in prev:
            delta_in = current["in_octets"] - prev["in_octets"]
            delta_out = current.get("out_octets", 0) - prev.get("out_octets", 0)
            if delta_in < 0:
                delta_in += 2**64
            if delta_out < 0:
                delta_out += 2**64
            metrics["total_bytes_delta"] = delta_in + delta_out

        if "in_errors" in current and "in_errors" in prev:
            delta_errors = current["in_errors"] - prev["in_errors"]
            delta_discards = current.get("in_discards", 0) - prev.get("in_discards", 0)
            metrics["error_count_delta"] = max(0, delta_errors + delta_discards)

        return metrics if metrics else None

    def _path_to_string(self, path_obj: dict) -> str:
        """Convert gNMI path object to string representation."""
        elements = path_obj.get("elem", [])
        parts = []
        for elem in elements:
            name = elem.get("name", "")
            keys = elem.get("key", {})
            if keys:
                key_str = ",".join(f"{k}={v}" for k, v in keys.items())
                parts.append(f"{name}[{key_str}]")
            else:
                parts.append(name)
        return "/" + "/".join(parts) if parts else ""

    def _extract_value(self, val_obj: dict) -> Optional[float]:
        """Extract numeric value from gNMI TypedValue."""
        for key in ("uintVal", "intVal", "floatVal", "doubleVal"):
            if key in val_obj:
                return float(val_obj[key])
        return None

    def _resolve_metric(self, path: str) -> Optional[str]:
        """Map a gNMI path to a known metric name."""
        for pattern, metric in self.PATH_MAPPING.items():
            if pattern in path:
                return metric
        return None
