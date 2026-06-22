"""
Starlink gRPC stub — lightweight replacement for compiled protobufs.

Instead of requiring the full spacex.api.device protobuf compilation,
this module talks to the Starlink dish using raw gRPC reflection or
the JSON-over-HTTP fallback that newer Starlink firmware exposes.

This eliminates the need for protoc-compiled Starlink .proto files.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StarlinkHistory:
    """Parsed Starlink dish history data."""
    pop_ping_latency_ms: list[float] = field(default_factory=list)
    pop_ping_drop_rate: list[float] = field(default_factory=list)
    downlink_throughput_bps: list[float] = field(default_factory=list)
    uplink_throughput_bps: list[float] = field(default_factory=list)
    snr: float = 0.0
    uptime_s: int = 0
    obstruction_pct: float = 0.0


async def fetch_starlink_history(
    dish_ip: str = "192.168.100.1",
    grpc_port: int = 9200,
) -> Optional[StarlinkHistory]:
    """
    Fetch telemetry history from a Starlink dish.

    Tries two methods:
      1. HTTP JSON endpoint (newer firmware exposes this)
      2. Raw gRPC with hand-crafted protobuf bytes

    Returns StarlinkHistory or None on failure.
    """
    # Method 1: Try HTTP JSON (firmware 2023.48+)
    result = await _try_http_json(dish_ip)
    if result:
        return result

    # Method 2: Raw gRPC with minimal protobuf encoding
    result = await _try_raw_grpc(dish_ip, grpc_port)
    if result:
        return result

    return None


async def _try_http_json(dish_ip: str) -> Optional[StarlinkHistory]:
    """
    Some Starlink firmware versions expose a JSON status endpoint
    at http://192.168.100.1/api/v1/history for the last 15 minutes.
    """
    try:
        import aiohttp

        url = f"http://{dish_ip}/api/v1/history"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

        return StarlinkHistory(
            pop_ping_latency_ms=data.get("popPingLatencyMs", []),
            pop_ping_drop_rate=data.get("popPingDropRate", []),
            downlink_throughput_bps=data.get("downlinkThroughputBps", []),
            uplink_throughput_bps=data.get("uplinkThroughputBps", []),
            snr=data.get("snr", 0),
            uptime_s=data.get("uptimeS", 0),
            obstruction_pct=data.get("obstructionPct", 0),
        )
    except Exception:
        return None


async def _try_raw_grpc(dish_ip: str, grpc_port: int) -> Optional[StarlinkHistory]:
    """
    Talk to the Starlink dish gRPC API using raw protobuf bytes.

    The GetHistory request is a simple protobuf message:
      Field 7 (GetHistoryRequest): empty message {}

    We encode this by hand to avoid needing compiled proto files.

    Wire format:
      - Tag: field_number=7, wire_type=2 (length-delimited) → byte 0x3A
      - Length: 0 (empty sub-message) → byte 0x00
    """
    try:
        import grpc

        # Raw protobuf: Request { get_history: {} }
        # Field 7, wire type 2 (length-delimited), length 0
        raw_request = b"\x3a\x00"

        channel = grpc.insecure_channel(f"{dish_ip}:{grpc_port}")

        # Use the generic unary-unary call with raw bytes
        method = "/SpaceX.API.Device.Device/Handle"
        response_bytes = channel.unary_unary(
            method,
            request_serializer=lambda x: x,
            response_deserializer=lambda x: x,
        )(raw_request, timeout=3)

        channel.close()

        # Parse the response — the history is in field 7 of the response
        # This is a simplified parser for the specific fields we need
        return _parse_history_response(response_bytes)

    except Exception:
        return None


def _parse_history_response(data: bytes) -> Optional[StarlinkHistory]:
    """
    Minimal protobuf parser for Starlink GetHistory response.

    We only extract the arrays we need:
      - Field 1: pop_ping_latency_ms (repeated float)
      - Field 2: pop_ping_drop_rate (repeated float)
      - Field 3: downlink_throughput_bps (repeated float)
      - Field 4: uplink_throughput_bps (repeated float)
    """
    import struct

    if not data or len(data) < 4:
        return None

    history = StarlinkHistory()

    try:
        i = 0
        while i < len(data):
            if i >= len(data):
                break
            byte = data[i]
            field_number = byte >> 3
            wire_type = byte & 0x07
            i += 1

            if wire_type == 2:  # Length-delimited
                length, i = _decode_varint(data, i)
                sub_data = data[i:i + length]
                i += length

                # Field 7 of the outer Response = DishGetHistory
                if field_number == 7:
                    # Parse inner history message
                    j = 0
                    while j < len(sub_data):
                        if j >= len(sub_data):
                            break
                        inner_byte = sub_data[j]
                        inner_field = inner_byte >> 3
                        inner_wire = inner_byte & 0x07
                        j += 1

                        if inner_wire == 2:  # packed repeated float
                            inner_len, j = _decode_varint(sub_data, j)
                            packed = sub_data[j:j + inner_len]
                            j += inner_len
                            floats = []
                            for k in range(0, len(packed) - 3, 4):
                                floats.append(struct.unpack("<f", packed[k:k + 4])[0])
                            if inner_field == 1:
                                history.pop_ping_latency_ms = floats
                            elif inner_field == 2:
                                history.pop_ping_drop_rate = floats
                            elif inner_field == 3:
                                history.downlink_throughput_bps = floats
                            elif inner_field == 4:
                                history.uplink_throughput_bps = floats
                        elif inner_wire == 0:  # varint
                            _, j = _decode_varint(sub_data, j)
                        elif inner_wire == 5:  # 32-bit
                            j += 4
                        elif inner_wire == 1:  # 64-bit
                            j += 8
                        else:
                            break
            elif wire_type == 0:  # varint
                _, i = _decode_varint(data, i)
            elif wire_type == 5:  # 32-bit fixed
                i += 4
            elif wire_type == 1:  # 64-bit fixed
                i += 8
            else:
                break
    except Exception:
        pass

    if history.pop_ping_latency_ms:
        return history
    return None


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a protobuf varint starting at pos. Returns (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos
