# ml/scripts/generate_synthetic_data.py

import numpy as np
import pandas as pd
import argparse
from pathlib import Path

def generate_link_telemetry(
    link_id: str,
    duration_hours: int = 24 * 30,  # 30 days
    interval_sec: int = 1,
    brownout_probability: float = 0.002,  # ~5 brownouts per hour
) -> pd.DataFrame:
    """
    Generate realistic synthetic telemetry with:
    - Base patterns: diurnal traffic cycles, random normal noise
    - Brownout events: gradual degradation (latency spike, jitter increase)
    - Congestion events: bandwidth saturation -> packet loss correlation
    """
    n_points = (duration_hours * 3600) // interval_sec
    timestamps = pd.date_range(start="2026-01-01", periods=n_points, freq=f"{interval_sec}s")
    
    # Diurnal pattern (peak at 10am and 2pm local time)
    hour_of_day = (timestamps.hour + timestamps.minute / 60.0).to_numpy()
    diurnal = 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24) + 0.7
    
    # Base metrics with noise (ensure numpy arrays for mutable slice assignment)
    base_latency = np.array(15 + 10 * diurnal + np.random.normal(0, 2, n_points), dtype=np.float64)
    base_jitter = np.array(1 + 3 * diurnal + np.random.normal(0, 0.5, n_points), dtype=np.float64)
    base_loss = np.clip(np.array(0.01 + 0.05 * diurnal + np.random.normal(0, 0.01, n_points), dtype=np.float64), 0, 100)
    base_bw = np.clip(np.array(30 + 40 * diurnal + np.random.normal(0, 5, n_points), dtype=np.float64), 0, 100)
    base_rtt = np.array(base_latency * 2 + np.random.normal(0, 1, n_points), dtype=np.float64)
    
    # Inject brownout events (gradual degradation over 30-120 seconds)
    brownout_mask = np.random.random(n_points) < brownout_probability
    brownout_starts = np.where(brownout_mask)[0]
    
    for start in brownout_starts:
        duration = np.random.randint(30, 120)
        end = min(start + duration, n_points)
        ramp = np.linspace(0, 1, end - start)
        severity = np.random.uniform(2, 8)  # multiplier
        
        base_latency[start:end] += severity * 20 * ramp
        base_jitter[start:end] += severity * 5 * ramp
        base_loss[start:end] += severity * 2 * ramp
    
    df = pd.DataFrame({
        "time": timestamps,
        "link_id": link_id,
        "latency_ms": np.clip(base_latency, 0, None),
        "jitter_ms": np.clip(base_jitter, 0, None),
        "packet_loss_pct": np.clip(base_loss, 0, 100),
        "bandwidth_util_pct": np.clip(base_bw, 0, 100),
        "rtt_ms": np.clip(base_rtt, 0, None),
    })
    
    return df

# Generate for multiple link types
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic telemetry data")
    parser.add_argument("--duration-hours", type=int, default=24 * 30,
                        help="Duration in hours (default: 720 = 30 days)")
    parser.add_argument("--output-dir", type=str, default="ml/data/synthetic",
                        help="Output directory for parquet files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    links = [
        ("fiber-primary", args.duration_hours),
        ("broadband-secondary", args.duration_hours),
        ("satellite-backup", args.duration_hours),
        ("5g-mobile", args.duration_hours),
    ]
    for link_id, hours in links:
        df = generate_link_telemetry(link_id, hours)
        df.to_parquet(output_dir / f"{link_id}.parquet", index=False)
        print(f"Generated {len(df):,} points for {link_id}")
