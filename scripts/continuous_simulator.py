"""
PathWise AI — Continuous Per-User Data Simulator
Generates realistic WAN telemetry for all 8 user sites at 1 Hz.
Start: python scripts/continuous_simulator.py
Auto-started by docker-compose via the 'simulator' service.
"""

import asyncio, random, time, json, os
from datetime import datetime
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL", "postgresql://pathwise:pathwise@localhost:5432/pathwise")
engine = create_engine(DB_URL)

# Site → link configuration
SITE_LINKS = {
    "site-user-001-1": ["fiber", "broadband"],
    "site-user-001-2": ["5g", "broadband"],
    "site-user-002-1": ["fiber", "satellite", "5g"],
    "site-user-002-2": ["fiber", "broadband"],
    "site-user-002-3": ["broadband", "5g"],
    "site-user-003-1": ["fiber", "broadband"],
    "site-user-003-2": ["broadband", "5g"],
    "site-user-003-3": ["fiber", "satellite"],
    "site-user-004-1": ["fiber", "broadband", "5g"],
    "site-user-004-2": ["broadband", "satellite"],
    "site-user-005-1": ["fiber", "broadband"],
    "site-user-005-2": ["fiber", "5g"],
    "site-user-006-1": ["fiber", "broadband", "satellite"],
    "site-user-006-2": ["fiber", "5g"],
    "site-user-007-1": ["broadband", "satellite"],
    "site-user-007-2": ["fiber", "broadband"],
    "site-user-008-1": ["fiber", "5g"],
    "site-user-008-2": ["fiber", "broadband"],
}

# Per-link baseline characteristics
LINK_BASELINES = {
    "fiber":     {"latency": 8,   "jitter": 1.2, "loss": 0.01, "bw": 1000},
    "broadband": {"latency": 22,  "jitter": 3.5, "loss": 0.05, "bw": 300},
    "satellite": {"latency": 590, "jitter": 40,  "loss": 0.3,  "bw": 50},
    "5g":        {"latency": 12,  "jitter": 2.0, "loss": 0.02, "bw": 500},
}

def _gen_metric(base: float, noise_pct: float = 0.15,
                spike_chance: float = 0.03) -> float:
    val = base * (1 + random.uniform(-noise_pct, noise_pct))
    if random.random() < spike_chance:
        val *= random.uniform(1.5, 4.0)  # simulate brownout spike
    return round(max(0, val), 3)

def _health_score(lat: float, jitter: float, loss: float,
                  base_lat: float) -> int:
    lat_penalty  = min(40, (lat / base_lat - 1) * 30) if lat > base_lat else 0
    jit_penalty  = min(20, jitter * 2)
    loss_penalty = min(40, loss * 200)
    return max(0, min(100, round(100 - lat_penalty - jit_penalty - loss_penalty)))

async def simulate_site(site_id: str, links: list):
    with engine.connect() as conn:
        while True:
            for link_type in links:
                b = LINK_BASELINES[link_type]
                lat   = _gen_metric(b["latency"])
                jit   = _gen_metric(b["jitter"])
                loss  = _gen_metric(b["loss"])
                score = _health_score(lat, jit, loss, b["latency"])
                ts    = datetime.utcnow()

                conn.execute(text("""
                INSERT INTO telemetry_live
                    (site_id, link_type, latency_ms, jitter_ms, packet_loss_pct,
                     health_score, bandwidth_mbps, timestamp)
                VALUES
                    (:sid, :lt, :lat, :jit, :loss, :score, :bw, :ts)
                """), {
                    "sid": site_id, "lt": link_type,
                    "lat": lat, "jit": jit, "loss": loss,
                    "score": score, "bw": b["bw"] * random.uniform(0.6, 1.0),
                    "ts": ts
                })
            conn.commit()
            await asyncio.sleep(1)

async def main():
    # Ensure telemetry_live hypertable exists
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS telemetry_live (
            id BIGSERIAL,
            site_id VARCHAR,
            link_type VARCHAR,
            latency_ms NUMERIC(10,3),
            jitter_ms NUMERIC(10,3),
            packet_loss_pct NUMERIC(8,4),
            health_score INT,
            bandwidth_mbps NUMERIC(10,2),
            timestamp TIMESTAMPTZ DEFAULT NOW()
        );
        SELECT create_hypertable('telemetry_live','timestamp',if_not_exists=>TRUE);
        """))
        conn.commit()

    print(f"[Simulator] Starting continuous simulation for {len(SITE_LINKS)} sites...")
    tasks = [simulate_site(sid, links) for sid, links in SITE_LINKS.items()]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
