"""
Replay Collector — plays back real-world training data at 1Hz.

Reads from the parquet files in ml/data/real_world/ which contain
telemetry calibrated to actual measurement studies:
  - fiber-primary.parquet: FCC Measuring Broadband America (AT&T Fiber, Verizon Fios)
  - broadband-secondary.parquet: FCC MBA cable ISPs (Comcast, Cox, Charter)
  - satellite-backup.parquet: Starlink community measurements (2023-2024)

Loops back to the beginning when it reaches the end of the file.
"""

from __future__ import annotations
import time
from pathlib import Path

import pandas as pd

from server.state import TelemetryPoint
from server.collectors.base import BaseCollector

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "data" / "real_world"


class ReplayCollector(BaseCollector):
    """
    Replays pre-recorded telemetry from a parquet file at 1Hz.
    Each call to collect() returns the next row in the dataset.
    Loops when it reaches the end.
    """

    def __init__(self, link_id: str):
        super().__init__(link_id=link_id)
        self._index = 0
        self._data: list[dict] = []
        self._load_data()

    def _load_data(self):
        parquet_path = DATA_DIR / f"{self.link_id}.parquet"
        if not parquet_path.exists():
            print(f"[replay:{self.link_id}] WARNING: {parquet_path} not found, using empty data")
            return

        df = pd.read_parquet(parquet_path)
        self._data = df.to_dict("records")
        print(f"[replay:{self.link_id}] Loaded {len(self._data):,} points from {parquet_path.name}")

    async def collect(self) -> TelemetryPoint:
        if not self._data:
            # No data — return zeros
            return TelemetryPoint(
                timestamp=time.time(), link_id=self.link_id,
                latency_ms=0, jitter_ms=0, packet_loss_pct=0,
                bandwidth_util_pct=0, rtt_ms=0,
            )

        row = self._data[self._index]
        self._index = (self._index + 1) % len(self._data)

        return TelemetryPoint(
            timestamp=time.time(),  # Use current time, not recorded time
            link_id=self.link_id,
            latency_ms=float(row["latency_ms"]),
            jitter_ms=float(row["jitter_ms"]),
            packet_loss_pct=float(row["packet_loss_pct"]),
            bandwidth_util_pct=float(row["bandwidth_util_pct"]),
            rtt_ms=float(row["rtt_ms"]),
        )
