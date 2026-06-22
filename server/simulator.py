"""
Real-time network telemetry simulator.

Generates 1 Hz telemetry for 4 WAN links with realistic patterns:
- Diurnal traffic cycles
- Random noise
- Periodic brownout events (gradual degradation)

When LSTM is enabled, steering decisions proactively avoid brownouts,
resulting in better "effective" metrics seen by users.
"""

from __future__ import annotations
import asyncio
import math
import os
import random
import time
import uuid

from server.state import state, TelemetryPoint, SteeringEvent

LINK_PROFILES = {
    "fiber-primary": {
        "base_latency": 12, "base_jitter": 1.0, "base_loss": 0.01,
        "base_bw": 45, "noise_scale": 1.0, "brownout_freq": 0.008,
    },
    "broadband-secondary": {
        "base_latency": 22, "base_jitter": 2.5, "base_loss": 0.05,
        "base_bw": 35, "noise_scale": 1.5, "brownout_freq": 0.012,
    },
    "satellite-backup": {
        "base_latency": 55, "base_jitter": 8.0, "base_loss": 0.15,
        "base_bw": 15, "noise_scale": 3.0, "brownout_freq": 0.015,
    },
    "5g-mobile": {
        "base_latency": 18, "base_jitter": 3.0, "base_loss": 0.08,
        "base_bw": 40, "noise_scale": 2.0, "brownout_freq": 0.010,
    },
}

_brownout_state: dict[str, dict] = {}


def _diurnal_factor(t: float) -> float:
    hour = (t / 3600) % 24
    return 0.3 * math.sin(2 * math.pi * (hour - 6) / 24) + 0.7


def _generate_raw_point(link_id: str, t: float) -> TelemetryPoint:
    """Generate a single raw telemetry point for a link."""
    p = LINK_PROFILES[link_id]
    diurnal = _diurnal_factor(t)

    latency = p["base_latency"] + 8 * diurnal + random.gauss(0, p["noise_scale"])
    jitter = p["base_jitter"] + 2 * diurnal + random.gauss(0, p["noise_scale"] * 0.3)
    loss = p["base_loss"] + 0.03 * diurnal + random.gauss(0, 0.005)
    bw = p["base_bw"] + 25 * diurnal + random.gauss(0, 3)
    rtt = latency * 2 + random.gauss(0, 0.5)

    bs = _brownout_state.get(link_id, {})
    if bs.get("active"):
        elapsed = t - bs["start"]
        duration = bs["duration"]
        if elapsed < duration:
            ramp = elapsed / duration
            severity = bs["severity"]
            latency += severity * 25 * ramp
            jitter += severity * 8 * ramp
            loss += severity * 3 * ramp
        else:
            _brownout_state[link_id] = {"active": False}
            state.brownout_active[link_id] = False
    elif random.random() < p["brownout_freq"]:
        _brownout_state[link_id] = {
            "active": True,
            "start": t,
            "duration": random.uniform(15, 45),
            "severity": random.uniform(2, 6),
        }
        state.brownout_active[link_id] = True

    return TelemetryPoint(
        timestamp=t,
        link_id=link_id,
        latency_ms=max(1, latency),
        jitter_ms=max(0, jitter),
        packet_loss_pct=max(0, min(100, loss)),
        bandwidth_util_pct=max(0, min(100, bw)),
        rtt_ms=max(1, rtt),
    )


def _compute_effective_point(
    raw: TelemetryPoint, link_id: str, lstm_on: bool
) -> TelemetryPoint:
    """
    Compute what the user actually experiences, factoring in:
    1. LSTM proactive steering (when enabled)
    2. Manually applied routing rules from sandbox
    """
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
        # Source link sheds load — metrics improve (lower utilization)
        bw = max(5, bw * 0.4 + random.gauss(0, 1))
        if is_brownout:
            # Brownout still happens on the wire but users aren't on this link
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

    # --- LSTM proactive steering (on top of manual rules) ---
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


async def simulation_loop():
    """Main simulation loop — runs at 1 Hz generating telemetry for all links."""
    sim_time = 6 * 3600  # Start at 6am for diurnal variation

    for link_id in state.active_links:
        m = state.metrics_lstm_off
        p = LINK_PROFILES[link_id]
        m.avg_latency = (m.avg_latency + p["base_latency"]) / 2 if m.avg_latency else p["base_latency"]
        m.avg_jitter = (m.avg_jitter + p["base_jitter"]) / 2 if m.avg_jitter else p["base_jitter"]
        state.metrics_lstm_on.avg_latency = m.avg_latency * 0.8
        state.metrics_lstm_on.avg_jitter = m.avg_jitter * 0.8

    # Deadline-based loop: sleep until next_tick, not for a fixed delta, so
    # tick work doesn't accumulate drift below the 1 Hz target of Req-Func-Sw-1.
    # Slight undershoot of the 1.0 s period leaves headroom for asyncio.sleep's
    # ~15 ms granularity on Windows; over many ticks the effective rate
    # stabilises just above 1 Hz on Windows and at ~1.01 Hz on Linux.
    loop = asyncio.get_event_loop()
    tick_period = float(os.environ.get("SIM_TICK_PERIOD_S", "0.98"))
    next_tick = loop.time()
    while True:
        sim_time += 1
        state.tick_count += 1

        for link_id in state.active_links:
            raw = _generate_raw_point(link_id, sim_time)
            state.telemetry[link_id].append(raw)

            eff = _compute_effective_point(raw, link_id, state.lstm_enabled)
            state.effective_telemetry[link_id].append(eff)

            _check_and_steer(link_id, raw, state.lstm_enabled)
            _update_comparison_metrics(link_id, raw, eff)

        next_tick += tick_period
        delay = next_tick - loop.time()
        if delay < 0:
            # Tick work overran the period; resync the deadline to avoid
            # bursting many catch-up ticks in a row.
            next_tick = loop.time()
            delay = 0
        await asyncio.sleep(delay)
