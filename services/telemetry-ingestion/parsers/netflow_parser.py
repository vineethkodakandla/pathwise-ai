# services/telemetry-ingestion/parsers/netflow_parser.py

import struct
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NetFlowRecord:
    """Parsed NetFlow v9 flow record."""
    src_addr: str
    dst_addr: str
    src_port: int
    dst_port: int
    protocol: int
    bytes_count: int
    packets_count: int
    first_switched: int
    last_switched: int
    tcp_flags: int
    tos: int
    input_snmp: int
    output_snmp: int


class NetFlowParser:
    """
    Parser for NetFlow v9 / IPFIX flow records.

    Extracts flow-level metrics used for:
    - Application-level traffic classification (by port/protocol/DSCP)
    - Per-flow bandwidth utilization
    - Flow duration analysis for anomaly detection

    NetFlow v9 Header Format:
    - Version (2 bytes): 9
    - Count (2 bytes): Number of FlowSets
    - SysUptime (4 bytes)
    - Unix Seconds (4 bytes)
    - Sequence Number (4 bytes)
    - Source ID (4 bytes)
    """

    # NetFlow v9 field type IDs
    FIELD_TYPES = {
        1: ("bytes_count", "I"),
        2: ("packets_count", "I"),
        4: ("protocol", "B"),
        6: ("tcp_flags", "B"),
        7: ("src_port", "H"),
        8: ("src_addr", "4s"),
        10: ("input_snmp", "H"),
        11: ("dst_port", "H"),
        12: ("dst_addr", "4s"),
        14: ("output_snmp", "H"),
        21: ("last_switched", "I"),
        22: ("first_switched", "I"),
    }

    def __init__(self):
        self._templates: dict[int, list] = {}

    def parse_packet(self, data: bytes) -> list[NetFlowRecord]:
        """Parse a raw NetFlow v9 UDP packet into flow records."""
        if len(data) < 20:
            logger.warning("NetFlow packet too short")
            return []

        version, count = struct.unpack("!HH", data[:4])
        if version != 9:
            logger.warning(f"Unsupported NetFlow version: {version}")
            return []

        records = []
        offset = 20  # Skip header

        while offset < len(data) and len(records) < count:
            if offset + 4 > len(data):
                break

            flowset_id, flowset_length = struct.unpack("!HH", data[offset:offset+4])

            if flowset_id == 0:
                # Template FlowSet
                self._parse_template(data[offset+4:offset+flowset_length])
            elif flowset_id > 255:
                # Data FlowSet
                new_records = self._parse_data_flowset(
                    flowset_id, data[offset+4:offset+flowset_length]
                )
                records.extend(new_records)

            offset += flowset_length

        return records

    def _parse_template(self, data: bytes):
        """Parse a template FlowSet and store for future data parsing."""
        offset = 0
        while offset + 4 <= len(data):
            template_id, field_count = struct.unpack("!HH", data[offset:offset+4])
            offset += 4
            fields = []
            for _ in range(field_count):
                if offset + 4 > len(data):
                    break
                field_type, field_length = struct.unpack("!HH", data[offset:offset+4])
                fields.append((field_type, field_length))
                offset += 4
            self._templates[template_id] = fields

    def _parse_data_flowset(
        self, template_id: int, data: bytes
    ) -> list[NetFlowRecord]:
        """Parse data FlowSet using a previously received template."""
        if template_id not in self._templates:
            return []

        template = self._templates[template_id]
        record_size = sum(length for _, length in template)
        records = []
        offset = 0

        while offset + record_size <= len(data):
            values = {}
            for field_type, field_length in template:
                raw = data[offset:offset+field_length]
                if field_type in self.FIELD_TYPES:
                    name, fmt = self.FIELD_TYPES[field_type]
                    if name in ("src_addr", "dst_addr"):
                        import socket
                        values[name] = socket.inet_ntoa(raw)
                    else:
                        values[name] = struct.unpack(f"!{fmt}", raw[:struct.calcsize(fmt)])[0]
                offset += field_length

            try:
                records.append(NetFlowRecord(**values))
            except TypeError:
                pass

        return records

    def compute_flow_metrics(self, record: NetFlowRecord) -> dict:
        """Derive telemetry-relevant metrics from a flow record."""
        duration_ms = max(1, record.last_switched - record.first_switched)
        bits_per_sec = (record.bytes_count * 8 * 1000) / duration_ms

        return {
            "flow_bps": bits_per_sec,
            "flow_pps": (record.packets_count * 1000) / duration_ms,
            "duration_ms": duration_ms,
            "src": f"{record.src_addr}:{record.src_port}",
            "dst": f"{record.dst_addr}:{record.dst_port}",
            "protocol": record.protocol,
        }
