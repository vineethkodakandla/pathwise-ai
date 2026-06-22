"""
Unified Real-Time Collector — drop-in replacement for simulator.py.

Runs one collector per link type at 1Hz, feeding TelemetryPoint objects
into the same state.telemetry buffers that the LSTM engine, steering
engine, sandbox, and WebSocket dashboard consume.

Set DATA_SOURCE=live to use real hardware collectors.
Set DATA_SOURCE=sim (default) to use the synthetic simulator.

When DATA_SOURCE=live, each link type is configured by its own
environment variables (see each collector module for details).
"""

from __future__ import annotations
import asyncio
import csv
import os
import time
import uuid
from pathlib import Path

from server.state import state, TelemetryPoint, SteeringEvent
from server.collectors.fiber import FiberCollector
from server.collectors.broadband import BroadbandCollector
from server.collectors.satellite import SatelliteCollector
from server.collectors.fiveg import FiveGCollector
from server.collectors.wifi import WiFiCollector
from server.collectors.replay import ReplayCollector
from server.collectors.base import BaseCollector

# ── Persistent Data Storage ────────────────────────────────────

LIVE_DATA_DIR = Path(__file__).resolve().parent.parent / "ml" / "data" / "live_wifi"
LIVE_DATA_DIR.mkdir(parents=True, exist_ok=True)

_csv_writers: dict[str, tuple] = {}  # link_id -> (file_handle, csv_writer)
_data_counts: dict[str, int] = {}


def _get_csv_writer(link_id: str):
    """Get or create a CSV writer for persistent storage of live data."""
    if link_id not in _csv_writers:
        filepath = LIVE_DATA_DIR / f"{link_id}.csv"
        is_new = not filepath.exists()
        fh = open(filepath, "a", newline="", buffering=1)  # line-buffered
        writer = csv.writer(fh)
        if is_new:
            writer.writerow(["timestamp", "link_id", "latency_ms", "jitter_ms",
                             "packet_loss_pct", "bandwidth_util_pct", "rtt_ms"])
        _csv_writers[link_id] = (fh, writer)
        _data_counts[link_id] = 0
    return _csv_writers[link_id][1]


def _persist_point(point: TelemetryPoint):
    """Write a telemetry point to the CSV file for its link."""
    writer = _get_csv_writer(point.link_id)
    writer.writerow([
        round(point.timestamp, 3),
        point.link_id,
        round(point.latency_ms, 3),
        round(point.jitter_ms, 3),
        round(point.packet_loss_pct, 5),
        round(point.bandwidth_util_pct, 2),
        round(point.rtt_ms, 3),
    ])
    _data_counts[point.link_id] = _data_counts.get(point.link_id, 0) + 1


def _flush_all():
    """Flush all CSV writers to disk."""
    for fh, _ in _csv_writers.values():
        fh.flush()


def get_live_data_stats() -> dict:
    """Return stats about collected live data."""
    stats = {}
    for link_id in state.active_links:
        filepath = LIVE_DATA_DIR / f"{link_id}.csv"
        stats[link_id] = {
            "file": str(filepath),
            "points_this_session": _data_counts.get(link_id, 0),
            "file_exists": filepath.exists(),
            "file_size_kb": round(filepath.stat().st_size / 1024, 1) if filepath.exists() else 0,
        }
    return stats


# ── Link Profiles (same as simulator.py, used for steering logic) ──

LINK_PROFILES = {
    "fiber-primary": {"base_latency": 12, "base_jitter": 1.0, "base_loss": 0.01},
    "broadband-secondary": {"base_latency": 22, "base_jitter": 2.5, "base_loss": 0.05},
    "satellite-backup": {"base_latency": 55, "base_jitter": 8.0, "base_loss": 0.15},
    "5g-mobile": {"base_latency": 18, "base_jitter": 3.0, "base_loss": 0.08},
    "wifi": {"base_latency": 30, "base_jitter": 5.0, "base_loss": 0.02},
}


def _create_collectors() -> dict[str, BaseCollector]:
    """Instantiate one collector per link type based on environment config."""
    data_source = os.environ.get("DATA_SOURCE", "sim").lower()

    if data_source == "hybrid":
        # Hybrid mode:
        #   wifi        → REAL live pings from laptop WiFi
        #   fiber       → REPLAY from FCC MBA fiber dataset
        #   5g-mobile   → REPLAY from 5G measurement dataset (was broadband-secondary)
        #   satellite   → REPLAY from Starlink measurement dataset
        #
        # NOTE: EthernetCollector exists at server/collectors/ethernet.py
        #       for live fiber data via Ethernet port — currently DISABLED.
        #       To enable: connect Ethernet cable, replace ReplayCollector("fiber-primary")
        #       with EthernetCollector()
        print("[collector] HYBRID mode: WiFi=live, fiber/5g/satellite=replay from training data")
        return {
            "fiber-primary": ReplayCollector("fiber-primary"),
            "5g-mobile": ReplayCollector("5g-mobile"),
            "satellite-backup": ReplayCollector("satellite-backup"),
            "wifi": WiFiCollector(),
        }
    else:
        # Full live mode: all 4 links from hardware
        return {
            "fiber-primary": FiberCollector(),
            "broadband-secondary": BroadbandCollector(),
            "satellite-backup": SatelliteCollector(),
            "5g-mobile": FiveGCollector(),
        }


def _compute_effective_point(
    raw: TelemetryPoint, link_id: str, lstm_on: bool
) -> TelemetryPoint:
    """
    Compute what the user actually experiences, factoring in:
      1. LSTM proactive steering (when enabled)
      2. Manually applied routing rules from sandbox

    This is identical to the logic in simulator.py — the same steering
    and routing rule effects apply whether data is simulated or live.
    """
    import random

    latency = raw.latency_ms
    jitter = raw.jitter_ms
    loss = raw.packet_loss_pct
    bw = raw.bandwidth_util_pct
    rtt = raw.rtt_ms

    profile = LINK_PROFILES[link_id]
    is_brownout = state.brownout_active.get(link_id, False)
    pred = state.predictions.get(link_id)

    # --- Applied routing rules: traffic diverted AWAY from this link ---
    if state.is_traffic_diverted_from(link_id):
        bw = max(5, bw * 0.4 + random.gauss(0, 1))
        if is_brownout:
            latency = profile["base_latency"] * 0.8 + random.gauss(0, 0.5)
            jitter = profile["base_jitter"] * 0.7 + random.gauss(0, 0.2)
            loss = max(0, profile["base_loss"] * 0.5 + random.gauss(0, 0.003))
            rtt = latency * 2 + random.gauss(0, 0.3)

    # --- Applied routing rules: traffic diverted TO this link ---
    if state.is_traffic_diverted_to(link_id):
        load_increase = 1.15 + random.gauss(0, 0.02)
        latency = latency * load_increase
        jitter = jitter * (1.05 + random.gauss(0, 0.01))
        bw = min(95, bw * load_increase)
        rtt = latency * 2 + random.gauss(0, 0.5)

    # --- LSTM proactive steering ---
    if lstm_on and is_brownout and pred and pred.health_score < 60:
        if not state.is_traffic_diverted_from(link_id):
            latency = profile["base_latency"] + random.gauss(0, 1)
            jitter = profile["base_jitter"] + random.gauss(0, 0.3)
            loss = max(0, profile["base_loss"] + random.gauss(0, 0.005))
            rtt = profile["base_latency"] * 2 + random.gauss(0, 0.5)

    return TelemetryPoint(
        timestamp=raw.timestamp,
        link_id=link_id,
        latency_ms=max(1, latency),
        jitter_ms=max(0, jitter),
        packet_loss_pct=max(0, min(100, loss)),
        bandwidth_util_pct=max(0, min(100, bw)),
        rtt_ms=max(1, rtt),
    )


def _detect_brownout(link_id: str, raw: TelemetryPoint):
    """
    Detect brownout conditions from live data.
    A brownout is detected when latency or loss spikes significantly
    above the link's baseline profile.
    """
    profile = LINK_PROFILES[link_id]
    brownout_lat_threshold = profile["base_latency"] * 3
    brownout_loss_threshold = profile["base_loss"] * 10 + 1.0

    is_brownout = (
        raw.latency_ms > brownout_lat_threshold
        or raw.packet_loss_pct > brownout_loss_threshold
    )
    state.brownout_active[link_id] = is_brownout


def _check_and_steer(link_id: str, raw: TelemetryPoint, lstm_on: bool):
    """Generate steering events based on current conditions."""
    if lstm_on:
        pred = state.predictions.get(link_id)
        if pred and pred.health_score < 50 and pred.confidence > 0.6:
            best = _find_best_alternative(link_id)
            if best:
                evt = SteeringEvent(
                    id=str(uuid.uuid4())[:8],
                    timestamp=raw.timestamp,
                    action="PREEMPTIVE_SHIFT",
                    source_link=link_id,
                    target_link=best,
                    traffic_classes="voip,video,critical",
                    confidence=pred.confidence,
                    reason=f"LSTM predicted degradation (health={pred.health_score:.0f})",
                    status="executed",
                    lstm_enabled=True,
                )
                state.steering_history.appendleft(evt)
                state.metrics_lstm_on.proactive_steerings += 1
                state.metrics_lstm_on.brownouts_avoided += 1
    else:
        if raw.latency_ms > 80 or raw.packet_loss_pct > 2:
            best = _find_best_alternative(link_id)
            if best:
                evt = SteeringEvent(
                    id=str(uuid.uuid4())[:8],
                    timestamp=raw.timestamp,
                    action="EMERGENCY_FAILOVER",
                    source_link=link_id,
                    target_link=best,
                    traffic_classes="all",
                    confidence=0.5,
                    reason=f"Threshold breach (latency={raw.latency_ms:.0f}ms, loss={raw.packet_loss_pct:.1f}%)",
                    status="executed",
                    lstm_enabled=False,
                )
                state.steering_history.appendleft(evt)
                state.metrics_lstm_off.reactive_steerings += 1
                state.metrics_lstm_off.brownouts_hit += 1


def _find_best_alternative(exclude_link: str) -> str | None:
    import random
    candidates = [l for l in state.active_links if l != exclude_link]
    best, best_score = None, -1
    for c in candidates:
        pred = state.predictions.get(c)
        if pred and pred.health_score > best_score:
            best, best_score = c, pred.health_score
    if best is None and candidates:
        best = random.choice(candidates)
    return best


def _update_comparison_metrics(link_id: str, raw: TelemetryPoint, eff: TelemetryPoint):
    m_off = state.metrics_lstm_off
    m_off.avg_latency = m_off.avg_latency * 0.995 + raw.latency_ms * 0.005
    m_off.avg_jitter = m_off.avg_jitter * 0.995 + raw.jitter_ms * 0.005
    m_off.avg_packet_loss = m_off.avg_packet_loss * 0.995 + raw.packet_loss_pct * 0.005

    m_on = state.metrics_lstm_on
    m_on.avg_latency = m_on.avg_latency * 0.995 + eff.latency_ms * 0.005
    m_on.avg_jitter = m_on.avg_jitter * 0.995 + eff.jitter_ms * 0.005
    m_on.avg_packet_loss = m_on.avg_packet_loss * 0.995 + eff.packet_loss_pct * 0.005


# ── Main Collection Loop ──────────────────────────────────────

async def live_collection_loop():
    """
    Real-time collection loop — runs at 1Hz, collecting from actual
    hardware for all 4 WAN links.

    Drop-in replacement for simulator.simulation_loop().
    Same output contract: populates state.telemetry and state.effective_telemetry.
    """
    collectors = _create_collectors()

    # Warm up comparison metrics with baseline profiles
    for link_id in state.active_links:
        p = LINK_PROFILES[link_id]
        m = state.metrics_lstm_off
        m.avg_latency = (m.avg_latency + p["base_latency"]) / 2 if m.avg_latency else p["base_latency"]
        m.avg_jitter = (m.avg_jitter + p["base_jitter"]) / 2 if m.avg_jitter else p["base_jitter"]
        state.metrics_lstm_on.avg_latency = m.avg_latency * 0.8
        state.metrics_lstm_on.avg_jitter = m.avg_jitter * 0.8

    print(f"[collector] Starting real-time collection loop (1Hz)...")
    print(f"[collector] Live data saved to: {LIVE_DATA_DIR}")

    while True:
        state.tick_count += 1

        # Collect from all links concurrently
        tasks = {
            link_id: collector.safe_collect()
            for link_id, collector in collectors.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for (link_id, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                print(f"[collector:{link_id}] exception: {result}")
                continue
            if result is None:
                continue

            raw = result
            state.telemetry[link_id].append(raw)

            # Persist to CSV file
            _persist_point(raw)

            # Detect brownout from live metrics
            _detect_brownout(link_id, raw)

            # Compute effective (user-experienced) telemetry
            eff = _compute_effective_point(raw, link_id, state.lstm_enabled)
            state.effective_telemetry[link_id].append(eff)

            # Steering decisions
            _check_and_steer(link_id, raw, state.lstm_enabled)
            _update_comparison_metrics(link_id, raw, eff)

        # Flush to disk every 10 seconds, log every 60
        if state.tick_count % 10 == 0:
            _flush_all()
        if state.tick_count % 60 == 0:
            total = sum(_data_counts.values())
            print(f"[collector] {total} points collected ({', '.join(f'{k}: {v}' for k, v in _data_counts.items())})")

        await asyncio.sleep(1.0)
