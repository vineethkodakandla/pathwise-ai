# PathWise AI — Complete Implementation Guide

**Version 1.0 | February 2026**
**Team Pathfinders | COSC6370-001 Advanced Software Engineering**

---

## Executive Summary

This guide provides a senior-engineer-level blueprint for building PathWise AI end-to-end. It covers system architecture, ML pipeline, backend services, frontend dashboard, integration layer, testing strategy, and deployment. Every section maps directly to the five features defined in the PVD: Predictive Telemetry Engine, Autonomous Traffic Steering, Digital Twin Validation Sandbox, Intent-Based Management Interface, and Multi-Link Health Scoreboard.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + D3)                        │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────────────┐ │
│  │ IBN Interface │  │ Health Scoreboard  │  │ Digital Twin Viewer  │ │
│  └──────┬───────┘  └────────┬──────────┘  └──────────┬───────────┘ │
│         │                   │                        │             │
│         └───────────────────┼────────────────────────┘             │
│                             │  REST / WebSocket                    │
├─────────────────────────────┼──────────────────────────────────────┤
│                        API GATEWAY (FastAPI)                        │
│  ┌──────────────┐  ┌───────┴───────┐  ┌───────────────────────┐   │
│  │ Auth / RBAC  │  │ Policy Engine │  │ WebSocket Manager     │   │
│  └──────────────┘  └───────────────┘  └───────────────────────┘   │
├────────────────────────────────────────────────────────────────────┤
│                       CORE SERVICES LAYER                          │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ Telemetry      │ │ Prediction   │ │ Traffic Steering         │ │
│  │ Ingestion      │ │ Service      │ │ Service                  │ │
│  │ Service        │ │ (LSTM)       │ │ (SDN Controller Client)  │ │
│  └───────┬────────┘ └──────┬───────┘ └──────────┬───────────────┘ │
│          │                 │                     │                 │
│  ┌───────┴─────────────────┴─────────────────────┴───────────────┐ │
│  │                  Message Bus (Redis Streams / Kafka-lite)     │ │
│  └──────────────────────────┬────────────────────────────────────┘ │
│                             │                                      │
│  ┌──────────────────────────┴────────────────────────────────────┐ │
│  │              Digital Twin Sandbox (Mininet + Batfish)          │ │
│  └───────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────┤
│                       DATA / INFRASTRUCTURE                        │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐  │
│  │ TimescaleDB   │  │ Redis Cache   │  │ SDN Controllers        │  │
│  │ (Telemetry)   │  │ (State)       │  │ (OpenDaylight / ONOS)  │  │
│  └──────────────┘  └───────────────┘  └────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Frontend | React 18 + TypeScript, D3.js, TailwindCSS | Component-based UI, real-time viz |
| API Gateway | FastAPI (Python 3.11+) | Async-native, auto OpenAPI docs, WebSocket support |
| ML Engine | PyTorch 2.x, LSTM | Fine-grained control over LSTM architecture |
| Telemetry Store | TimescaleDB (PostgreSQL extension) | Purpose-built for time-series, SQL-compatible |
| Cache / Pub-Sub | Redis 7+ (Streams) | Low-latency state + event bus |
| SDN Controllers | OpenDaylight (Beryllium+) / ONOS | Open-source, REST API, OpenFlow support |
| Network Emulation | Mininet | Lightweight, SDN-native virtual networks |
| Config Validation | Batfish | Vendor-neutral network config analysis |
| Containerization | Docker + Docker Compose | Reproducible dev/test/deploy |
| CI/CD | GitHub Actions | Free for academic, good ecosystem |

### 1.3 Repository Structure

```
pathwise-ai/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .github/workflows/
│   ├── ci.yml
│   └── ml-tests.yml
├── services/
│   ├── api-gateway/            # FastAPI application
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── routers/
│   │   │   │   ├── telemetry.py
│   │   │   │   ├── predictions.py
│   │   │   │   ├── steering.py
│   │   │   │   ├── sandbox.py
│   │   │   │   └── policies.py
│   │   │   ├── models/         # Pydantic schemas
│   │   │   ├── middleware/
│   │   │   └── websocket/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── telemetry-ingestion/    # Telemetry collection agent
│   │   ├── collector.py
│   │   ├── parsers/
│   │   │   ├── snmp_parser.py
│   │   │   ├── netflow_parser.py
│   │   │   └── streaming_telemetry.py
│   │   └── Dockerfile
│   ├── prediction-engine/      # LSTM ML service
│   │   ├── model/
│   │   │   ├── lstm_network.py
│   │   │   ├── trainer.py
│   │   │   ├── inference.py
│   │   │   └── feature_engineering.py
│   │   ├── serve.py            # Model serving (gRPC or REST)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── traffic-steering/       # SDN integration service
│   │   ├── steering_engine.py
│   │   ├── sdn_clients/
│   │   │   ├── opendaylight.py
│   │   │   └── onos.py
│   │   ├── flow_manager.py
│   │   └── Dockerfile
│   └── digital-twin/           # Sandbox validation
│       ├── twin_manager.py
│       ├── mininet_topology.py
│       ├── batfish_validator.py
│       └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── PolicyManager.tsx
│   │   │   └── SandboxViewer.tsx
│   │   ├── components/
│   │   │   ├── HealthScoreboard/
│   │   │   ├── TopologyMap/
│   │   │   ├── IBNConsole/
│   │   │   └── PredictionChart/
│   │   ├── hooks/
│   │   ├── services/           # API client layer
│   │   └── store/              # Zustand state management
│   ├── Dockerfile
│   └── package.json
├── ml/
│   ├── notebooks/
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_feature_engineering.ipynb
│   │   ├── 03_model_training.ipynb
│   │   └── 04_evaluation.ipynb
│   ├── data/
│   │   ├── raw/
│   │   ├── processed/
│   │   └── synthetic/
│   └── scripts/
│       ├── generate_synthetic_data.py
│       └── train.py
├── infra/
│   ├── mininet/
│   │   ├── topologies/
│   │   └── scripts/
│   └── batfish/
│       └── configs/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## 2. Feature 1 — Predictive Telemetry Engine (LSTM)

This is the core differentiator. Build this first — everything else depends on it.

### 2.1 Data Pipeline

#### Telemetry Collection

```python
# services/telemetry-ingestion/collector.py

import asyncio
import time
from dataclasses import dataclass
from typing import Optional
import redis.asyncio as redis

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
    """

    def __init__(self, redis_url: str, poll_interval: float = 1.0):
        self.redis = redis.from_url(redis_url)
        self.poll_interval = poll_interval
        self.stream_key = "telemetry:raw"

    async def collect_snmp(self, device_ip: str, community: str) -> TelemetryPoint:
        """Poll a device via SNMP for interface metrics."""
        # Use pysnmp to query:
        #   IF-MIB::ifInOctets, ifOutOctets (bandwidth)
        #   DISMAN-PING-MIB (latency/jitter via active probes)
        #   IF-MIB::ifInErrors, ifInDiscards (packet loss proxy)
        ...

    async def collect_netflow(self, collector_port: int = 9996):
        """Receive NetFlow v9/IPFIX records for flow-level metrics."""
        ...

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
        while True:
            start = time.monotonic()
            tasks = [
                self.collect_snmp(d["ip"], d["community"])
                for d in devices
            ]
            points = await asyncio.gather(*tasks, return_exceptions=True)
            for point in points:
                if isinstance(point, TelemetryPoint):
                    await self.publish(point)
            elapsed = time.monotonic() - start
            await asyncio.sleep(max(0, self.poll_interval - elapsed))
```

#### TimescaleDB Schema

```sql
-- Hypertable for high-frequency telemetry storage
CREATE TABLE telemetry (
    time        TIMESTAMPTZ NOT NULL,
    link_id     TEXT NOT NULL,
    latency_ms  DOUBLE PRECISION,
    jitter_ms   DOUBLE PRECISION,
    packet_loss_pct DOUBLE PRECISION,
    bandwidth_util_pct DOUBLE PRECISION,
    rtt_ms      DOUBLE PRECISION
);

SELECT create_hypertable('telemetry', 'time');

-- Continuous aggregate for 10-second rollups (model training)
CREATE MATERIALIZED VIEW telemetry_10s
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('10 seconds', time) AS bucket,
    link_id,
    AVG(latency_ms) AS avg_latency,
    STDDEV(latency_ms) AS std_latency,
    AVG(jitter_ms) AS avg_jitter,
    MAX(jitter_ms) AS max_jitter,
    AVG(packet_loss_pct) AS avg_packet_loss,
    MAX(packet_loss_pct) AS max_packet_loss,
    AVG(bandwidth_util_pct) AS avg_bw_util,
    AVG(rtt_ms) AS avg_rtt
FROM telemetry
GROUP BY bucket, link_id;

-- Retention policy: raw data 7 days, aggregates 90 days
SELECT add_retention_policy('telemetry', INTERVAL '7 days');
SELECT add_retention_policy('telemetry_10s', INTERVAL '90 days');

-- Index for fast range queries per link
CREATE INDEX idx_telemetry_link_time ON telemetry (link_id, time DESC);
```

### 2.2 Feature Engineering

```python
# services/prediction-engine/model/feature_engineering.py

import numpy as np
import pandas as pd
from typing import Tuple

class FeatureEngineer:
    """
    Transforms raw telemetry into LSTM-ready feature sequences.
    
    Input window:  60 data points (60 seconds at 1Hz)
    Output horizon: 30-60 seconds ahead (configurable)
    
    Feature set per timestep (13 features):
      - Raw: latency, jitter, packet_loss, bandwidth_util, rtt
      - Rolling 30s: mean_latency, std_latency, mean_jitter
      - EMA (alpha=0.3): ema_latency, ema_packet_loss
      - Rate of change: d_latency, d_jitter, d_packet_loss
    """
    
    WINDOW_SIZE = 60        # 60 timesteps input
    HORIZON = 30            # predict 30 steps ahead (30 seconds)
    NUM_FEATURES = 13

    def __init__(self):
        self.scalers = {}   # Per-link min-max scalers

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add engineered features to raw telemetry DataFrame."""
        df = df.sort_values("time").copy()
        
        # Rolling statistics (30-second window)
        df["mean_latency_30s"] = df["latency_ms"].rolling(30, min_periods=1).mean()
        df["std_latency_30s"] = df["latency_ms"].rolling(30, min_periods=1).std().fillna(0)
        df["mean_jitter_30s"] = df["jitter_ms"].rolling(30, min_periods=1).mean()
        
        # Exponential Moving Averages
        df["ema_latency"] = df["latency_ms"].ewm(alpha=0.3, adjust=False).mean()
        df["ema_packet_loss"] = df["packet_loss_pct"].ewm(alpha=0.3, adjust=False).mean()
        
        # Rate of change (first derivative)
        df["d_latency"] = df["latency_ms"].diff().fillna(0)
        df["d_jitter"] = df["jitter_ms"].diff().fillna(0)
        df["d_packet_loss"] = df["packet_loss_pct"].diff().fillna(0)
        
        return df

    def create_sequences(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sliding-window sequences for LSTM training.
        
        Returns:
            X: (num_samples, WINDOW_SIZE, NUM_FEATURES)
            y: (num_samples, HORIZON, 3)  # predict latency, jitter, packet_loss
        """
        feature_cols = [
            "latency_ms", "jitter_ms", "packet_loss_pct",
            "bandwidth_util_pct", "rtt_ms",
            "mean_latency_30s", "std_latency_30s", "mean_jitter_30s",
            "ema_latency", "ema_packet_loss",
            "d_latency", "d_jitter", "d_packet_loss"
        ]
        target_cols = ["latency_ms", "jitter_ms", "packet_loss_pct"]
        
        features = df[feature_cols].values
        targets = df[target_cols].values
        
        X, y = [], []
        for i in range(len(features) - self.WINDOW_SIZE - self.HORIZON):
            X.append(features[i : i + self.WINDOW_SIZE])
            y.append(targets[i + self.WINDOW_SIZE : i + self.WINDOW_SIZE + self.HORIZON])
        
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

    def normalize(self, X: np.ndarray, link_id: str, fit: bool = True) -> np.ndarray:
        """Per-link min-max normalization to [0, 1]."""
        if fit:
            self.scalers[link_id] = {
                "min": X.reshape(-1, X.shape[-1]).min(axis=0),
                "max": X.reshape(-1, X.shape[-1]).max(axis=0),
            }
        s = self.scalers[link_id]
        denom = s["max"] - s["min"]
        denom[denom == 0] = 1  # Avoid division by zero
        return (X - s["min"]) / denom
```

### 2.3 LSTM Model Architecture

```python
# services/prediction-engine/model/lstm_network.py

import torch
import torch.nn as nn

class PathWiseLSTM(nn.Module):
    """
    Multi-output LSTM for network telemetry forecasting.
    
    Architecture rationale:
    - 2-layer stacked LSTM: captures both short-term jitter patterns
      and longer-term degradation trends without excessive depth.
    - Dropout between layers: regularization critical for small datasets
      (initial 30 days ≈ 2.6M points per link, but correlated).
    - Attention mechanism: lets the model focus on critical moments
      (e.g., sudden latency spikes) within the 60-step window.
    - Separate prediction heads for latency, jitter, and packet_loss
      to allow different optimization dynamics per metric.
    """
    
    def __init__(
        self,
        input_size: int = 13,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2,
        horizon: int = 30,
        num_targets: int = 3,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.horizon = horizon
        
        # Core LSTM encoder
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        
        # Temporal attention over LSTM outputs
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )
        
        # Prediction heads — one per target metric
        self.latency_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )
        self.jitter_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )
        self.packet_loss_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )
        
        # Confidence estimation head (used by Health Scoreboard)
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),  # Output in [0, 1]
        )

    def forward(self, x: torch.Tensor):
        """
        Args:
            x: (batch, seq_len=60, features=13)
        Returns:
            predictions: dict with keys 'latency', 'jitter', 'packet_loss'
                         each of shape (batch, horizon)
            confidence:  (batch, 1)  — model's self-assessed prediction quality
        """
        # LSTM encoding
        lstm_out, (h_n, _) = self.lstm(x)  # lstm_out: (batch, 60, 128)
        
        # Attention: weighted sum of all timestep outputs
        attn_weights = self.attention(lstm_out)          # (batch, 60, 1)
        attn_weights = torch.softmax(attn_weights, dim=1)
        context = (lstm_out * attn_weights).sum(dim=1)   # (batch, 128)
        
        # Predictions
        predictions = {
            "latency": self.latency_head(context),       # (batch, 30)
            "jitter": self.jitter_head(context),
            "packet_loss": self.packet_loss_head(context),
        }
        confidence = self.confidence_head(context)        # (batch, 1)
        
        return predictions, confidence


class PathWiseLoss(nn.Module):
    """
    Composite loss function:
    - Weighted MSE for each target (packet_loss weighted higher because
      even small prediction errors there have outsized business impact)
    - Penalty term for underestimating degradation (asymmetric loss):
      missing a real brownout is much worse than a false positive.
    """

    def __init__(
        self,
        weights: dict = None,
        underestimate_penalty: float = 2.0,
    ):
        super().__init__()
        self.weights = weights or {"latency": 1.0, "jitter": 1.0, "packet_loss": 2.0}
        self.penalty = underestimate_penalty

    def forward(self, preds: dict, targets: torch.Tensor):
        """
        targets: (batch, horizon, 3) — latency, jitter, packet_loss
        """
        total_loss = 0.0
        target_map = {
            "latency": targets[:, :, 0],
            "jitter": targets[:, :, 1],
            "packet_loss": targets[:, :, 2],
        }
        
        for key, weight in self.weights.items():
            pred = preds[key]
            target = target_map[key]
            error = pred - target
            
            # Asymmetric MSE: penalize underestimates more
            mse = error ** 2
            underestimate_mask = (error < 0).float()  # pred < actual = missed degradation
            asymmetric_mse = mse * (1 + underestimate_mask * (self.penalty - 1))
            
            total_loss += weight * asymmetric_mse.mean()
        
        return total_loss
```

### 2.4 Training Pipeline

```python
# services/prediction-engine/model/trainer.py

import torch
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class LSTMTrainer:
    """
    Training configuration optimized for network telemetry:
    - AdamW optimizer (better weight decay for time-series)
    - ReduceLROnPlateau scheduler (adapts to loss plateaus)
    - Early stopping with patience=10
    - Model checkpointing (best val loss)
    """

    def __init__(
        self,
        model: "PathWiseLSTM",
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        batch_size: int = 256,
        max_epochs: int = 100,
        patience: int = 10,
        checkpoint_dir: str = "./checkpoints",
    ):
        self.model = model
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=lr, weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5
        )
        self.criterion = PathWiseLoss()

    def train(self, X_train, y_train, X_val, y_val) -> dict:
        train_ds = TensorDataset(
            torch.tensor(X_train), torch.tensor(y_train)
        )
        val_ds = TensorDataset(
            torch.tensor(X_val), torch.tensor(y_val)
        )
        train_loader = DataLoader(
            train_ds, batch_size=self.batch_size, shuffle=True, drop_last=True
        )
        val_loader = DataLoader(
            val_ds, batch_size=self.batch_size, shuffle=False
        )
        
        best_val_loss = float("inf")
        epochs_no_improve = 0
        history = {"train_loss": [], "val_loss": []}
        
        for epoch in range(self.max_epochs):
            # --- Training ---
            self.model.train()
            train_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                self.optimizer.zero_grad()
                preds, confidence = self.model(X_batch)
                loss = self.criterion(preds, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            
            # --- Validation ---
            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)
                    preds, _ = self.model(X_batch)
                    loss = self.criterion(preds, y_batch)
                    val_loss += loss.item()
            val_loss /= len(val_loader)
            
            self.scheduler.step(val_loss)
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            
            logger.info(
                f"Epoch {epoch+1}/{self.max_epochs} | "
                f"Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                f"LR: {self.optimizer.param_groups[0]['lr']:.2e}"
            )
            
            # Checkpoint best model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                epochs_no_improve = 0
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": self.model.state_dict(),
                    "optimizer_state_dict": self.optimizer.state_dict(),
                    "val_loss": val_loss,
                }, self.checkpoint_dir / "best_model.pt")
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= self.patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break
        
        return history
```

### 2.5 Synthetic Data Generation (For Development & Testing)

Since real network telemetry requires 30 days of collection, generate realistic synthetic data for initial development.

```python
# ml/scripts/generate_synthetic_data.py

import numpy as np
import pandas as pd

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
    - Congestion events: bandwidth saturation → packet loss correlation
    """
    n_points = (duration_hours * 3600) // interval_sec
    timestamps = pd.date_range(start="2026-01-01", periods=n_points, freq=f"{interval_sec}s")
    
    # Diurnal pattern (peak at 10am and 2pm local time)
    hour_of_day = timestamps.hour + timestamps.minute / 60.0
    diurnal = 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24) + 0.7
    
    # Base metrics with noise
    base_latency = 15 + 10 * diurnal + np.random.normal(0, 2, n_points)
    base_jitter = 1 + 3 * diurnal + np.random.normal(0, 0.5, n_points)
    base_loss = np.clip(0.01 + 0.05 * diurnal + np.random.normal(0, 0.01, n_points), 0, 100)
    base_bw = np.clip(30 + 40 * diurnal + np.random.normal(0, 5, n_points), 0, 100)
    base_rtt = base_latency * 2 + np.random.normal(0, 1, n_points)
    
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
    links = [
        ("fiber-primary", 24 * 30),
        ("broadband-secondary", 24 * 30),
        ("satellite-backup", 24 * 30),
        ("5g-mobile", 24 * 30),
    ]
    for link_id, hours in links:
        df = generate_link_telemetry(link_id, hours)
        df.to_parquet(f"ml/data/synthetic/{link_id}.parquet", index=False)
        print(f"Generated {len(df):,} points for {link_id}")
```

### 2.6 Model Serving (Inference Service)

```python
# services/prediction-engine/serve.py

import torch
import numpy as np
import asyncio
import redis.asyncio as redis
from fastapi import FastAPI
from contextlib import asynccontextmanager
from model.lstm_network import PathWiseLSTM
from model.feature_engineering import FeatureEngineer

# Global state
model: PathWiseLSTM = None
feature_eng: FeatureEngineer = None
redis_client: redis.Redis = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, feature_eng, redis_client
    
    # Load model
    model = PathWiseLSTM()
    checkpoint = torch.load("checkpoints/best_model.pt", map_location="cpu")
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    
    feature_eng = FeatureEngineer()
    redis_client = redis.from_url("redis://redis:6379")
    
    # Start background prediction loop
    asyncio.create_task(prediction_loop())
    
    yield
    
    await redis_client.close()

app = FastAPI(title="PathWise Prediction Engine", lifespan=lifespan)

async def prediction_loop():
    """
    Continuous prediction: every second, fetch latest 60 telemetry
    points per link, run inference, publish predictions.
    
    This runs as a background coroutine, not triggered by HTTP.
    """
    while True:
        try:
            # Get all active link IDs from Redis
            link_ids = await redis_client.smembers("active_links")
            
            for link_id_bytes in link_ids:
                link_id = link_id_bytes.decode()
                
                # Fetch last 60 telemetry points from Redis Stream
                raw_points = await redis_client.xrevrange(
                    "telemetry:raw", count=60
                )
                
                if len(raw_points) < 60:
                    continue  # Not enough data yet
                
                # Build feature tensor
                window = build_feature_window(raw_points, link_id)
                if window is None:
                    continue
                
                # Inference
                with torch.no_grad():
                    x = torch.tensor(window).unsqueeze(0)  # (1, 60, 13)
                    preds, confidence = model(x)
                
                # Compute health score (0-100, higher is healthier)
                health_score = compute_health_score(preds, confidence)
                
                # Publish prediction to Redis for consumers
                await redis_client.hset(f"prediction:{link_id}", mapping={
                    "latency_forecast": preds["latency"][0].numpy().tolist().__str__(),
                    "jitter_forecast": preds["jitter"][0].numpy().tolist().__str__(),
                    "packet_loss_forecast": preds["packet_loss"][0].numpy().tolist().__str__(),
                    "confidence": float(confidence[0]),
                    "health_score": health_score,
                    "timestamp": str(asyncio.get_event_loop().time()),
                })
                
                # Publish event if degradation predicted
                if health_score < 50:
                    await redis_client.xadd("alerts:degradation", {
                        "link_id": link_id,
                        "health_score": str(health_score),
                        "confidence": str(float(confidence[0])),
                    })
        
        except Exception as e:
            print(f"Prediction loop error: {e}")
        
        await asyncio.sleep(1.0)


def compute_health_score(preds: dict, confidence: torch.Tensor) -> float:
    """
    Composite health score (0-100):
    - Latency: <30ms = 100, >200ms = 0  (weight: 0.4)
    - Jitter: <5ms = 100, >50ms = 0     (weight: 0.3)
    - Packet Loss: <0.1% = 100, >5% = 0 (weight: 0.3)
    
    Averaged over the 30-second horizon, scaled by confidence.
    """
    lat = preds["latency"][0].mean().item()
    jit = preds["jitter"][0].mean().item()
    pkt = preds["packet_loss"][0].mean().item()
    conf = confidence[0].item()
    
    lat_score = max(0, min(100, 100 * (1 - (lat - 30) / 170)))
    jit_score = max(0, min(100, 100 * (1 - (jit - 5) / 45)))
    pkt_score = max(0, min(100, 100 * (1 - (pkt - 0.1) / 4.9)))
    
    raw_score = 0.4 * lat_score + 0.3 * jit_score + 0.3 * pkt_score
    return round(raw_score * (0.5 + 0.5 * conf), 1)  # Discount by confidence


def build_feature_window(raw_points: list, link_id: str):
    """Convert Redis Stream entries to feature-engineered numpy array."""
    # Implementation: parse raw points, compute rolling/EMA features,
    # normalize, return (60, 13) array
    ...
```

---

## 3. Feature 2 — Autonomous Traffic Steering (Hitless Handoff)

### 3.1 Steering Decision Engine

```python
# services/traffic-steering/steering_engine.py

import asyncio
import json
import redis.asyncio as redis
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SteeringAction(Enum):
    HOLD = "hold"               # No change needed
    PREEMPTIVE_SHIFT = "shift"  # Predicted degradation — move traffic
    EMERGENCY_FAILOVER = "failover"  # Immediate degradation detected
    REBALANCE = "rebalance"     # Load-balance across healthy links

@dataclass
class SteeringDecision:
    action: SteeringAction
    source_link: str
    target_link: str
    traffic_classes: list[str]  # ["voip", "video", "critical", "bulk"]
    confidence: float
    reason: str
    requires_sandbox_validation: bool

class SteeringEngine:
    """
    Decision engine that consumes predictions and determines
    optimal traffic placement across available WAN links.
    
    Decision logic:
    1. If any link health_score < CRITICAL_THRESHOLD (30): emergency failover
    2. If any link health_score < WARNING_THRESHOLD (50) and confidence > 0.7:
       preemptive shift to the highest-scoring alternative
    3. If score variance across links > REBALANCE_THRESHOLD: rebalance
    4. Otherwise: hold
    
    ALL preemptive shifts go through Digital Twin validation first.
    Emergency failovers execute immediately but are validated post-hoc.
    """
    
    CRITICAL_THRESHOLD = 30
    WARNING_THRESHOLD = 50
    CONFIDENCE_THRESHOLD = 0.7
    REBALANCE_THRESHOLD = 30

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.sdn_client = None  # Injected based on controller type

    async def evaluate(self) -> list[SteeringDecision]:
        """Evaluate all links and return steering decisions."""
        link_ids = await self.redis.smembers("active_links")
        link_scores = {}
        
        for link_id_bytes in link_ids:
            link_id = link_id_bytes.decode()
            pred = await self.redis.hgetall(f"prediction:{link_id}")
            if pred:
                link_scores[link_id] = {
                    "health_score": float(pred[b"health_score"]),
                    "confidence": float(pred[b"confidence"]),
                }
        
        decisions = []
        sorted_links = sorted(
            link_scores.items(), key=lambda x: x[1]["health_score"], reverse=True
        )
        best_link = sorted_links[0][0] if sorted_links else None
        
        for link_id, scores in link_scores.items():
            if scores["health_score"] < self.CRITICAL_THRESHOLD:
                # Emergency: execute immediately
                if best_link and best_link != link_id:
                    decisions.append(SteeringDecision(
                        action=SteeringAction.EMERGENCY_FAILOVER,
                        source_link=link_id,
                        target_link=best_link,
                        traffic_classes=["voip", "video", "critical", "bulk"],
                        confidence=scores["confidence"],
                        reason=f"Link {link_id} health critical ({scores['health_score']})",
                        requires_sandbox_validation=False,  # Post-hoc validation
                    ))
            
            elif (scores["health_score"] < self.WARNING_THRESHOLD
                  and scores["confidence"] > self.CONFIDENCE_THRESHOLD):
                # Preemptive: validate first
                if best_link and best_link != link_id:
                    decisions.append(SteeringDecision(
                        action=SteeringAction.PREEMPTIVE_SHIFT,
                        source_link=link_id,
                        target_link=best_link,
                        traffic_classes=["voip", "video", "critical"],
                        confidence=scores["confidence"],
                        reason=(
                            f"Predicted degradation on {link_id} "
                            f"(score: {scores['health_score']}, "
                            f"confidence: {scores['confidence']:.0%})"
                        ),
                        requires_sandbox_validation=True,
                    ))
        
        return decisions

    async def execute(self, decision: SteeringDecision):
        """
        Execute a steering decision via the SDN controller.
        
        For hitless handoff:
        1. Install new flow rules on target path FIRST (make-before-break)
        2. Update priority so new path is preferred
        3. Remove old flow rules after traffic has migrated
        4. Log the entire operation for audit trail
        """
        audit_entry = {
            "action": decision.action.value,
            "source": decision.source_link,
            "target": decision.target_link,
            "traffic_classes": decision.traffic_classes,
            "confidence": decision.confidence,
            "reason": decision.reason,
        }
        
        if decision.requires_sandbox_validation:
            # Validate in Digital Twin first
            is_valid = await self.validate_in_sandbox(decision)
            audit_entry["sandbox_validated"] = is_valid
            
            if not is_valid:
                audit_entry["status"] = "blocked_by_sandbox"
                await self.log_audit(audit_entry)
                return False
        
        # Execute make-before-break handoff
        success = await self.sdn_client.install_flow_rules(
            source_link=decision.source_link,
            target_link=decision.target_link,
            traffic_classes=decision.traffic_classes,
            strategy="make-before-break",
        )
        
        audit_entry["status"] = "executed" if success else "failed"
        await self.log_audit(audit_entry)
        return success
```

### 3.2 SDN Controller Integration

```python
# services/traffic-steering/sdn_clients/opendaylight.py

import httpx
from typing import Optional

class OpenDaylightClient:
    """
    Integration with OpenDaylight SDN Controller via RESTCONF API.
    
    Key endpoints used:
    - GET/PUT /restconf/config/opendaylight-inventory:nodes/node/{id}/flow-node-inventory:table/{table}/flow/{flow}
    - GET /restconf/operational/opendaylight-inventory:nodes
    - POST /restconf/operations/sal-flow:add-flow
    """
    
    def __init__(self, base_url: str, username: str = "admin", password: str = "admin"):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def install_flow_rules(
        self,
        source_link: str,
        target_link: str,
        traffic_classes: list[str],
        strategy: str = "make-before-break",
    ) -> bool:
        """
        Make-before-break hitless handoff:
        
        Step 1: Install new higher-priority flow on target link
        Step 2: Wait for flow to be confirmed active (flow stats show hits)
        Step 3: Remove old flow on source link
        """
        async with httpx.AsyncClient(auth=self.auth) as client:
            # Step 1: Install new flows on target
            for tc in traffic_classes:
                flow = self._build_flow_entry(
                    match=self._traffic_class_match(tc),
                    output_port=self._link_to_port(target_link),
                    priority=200,  # Higher than existing (100)
                    flow_id=f"pathwise-{tc}-{target_link}",
                )
                resp = await client.put(
                    f"{self.base_url}/restconf/config/opendaylight-inventory:nodes"
                    f"/node/openflow:1/flow-node-inventory:table/0"
                    f"/flow/pathwise-{tc}-{target_link}",
                    json=flow,
                    headers=self.headers,
                )
                if resp.status_code not in (200, 201):
                    return False
            
            # Step 2: Verify flows are active
            await self._wait_for_flows_active(target_link, traffic_classes)
            
            # Step 3: Remove old flows
            for tc in traffic_classes:
                await client.delete(
                    f"{self.base_url}/restconf/config/opendaylight-inventory:nodes"
                    f"/node/openflow:1/flow-node-inventory:table/0"
                    f"/flow/pathwise-{tc}-{source_link}",
                    headers=self.headers,
                )
            
            return True

    def _build_flow_entry(self, match: dict, output_port: int, priority: int, flow_id: str) -> dict:
        return {
            "flow-node-inventory:flow": [{
                "id": flow_id,
                "table_id": 0,
                "priority": priority,
                "match": match,
                "instructions": {
                    "instruction": [{
                        "order": 0,
                        "apply-actions": {
                            "action": [{
                                "order": 0,
                                "output-action": {
                                    "output-node-connector": str(output_port),
                                    "max-length": 65535,
                                }
                            }]
                        }
                    }]
                }
            }]
        }

    def _traffic_class_match(self, traffic_class: str) -> dict:
        """Map traffic class names to OpenFlow match criteria."""
        match_map = {
            "voip": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                "ip-match": {"ip-protocol": 17},  # UDP
                "udp-source-port-match": {"port": 5060},  # SIP
            },
            "video": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                "ip-match": {"ip-dscp": 34},  # AF41
            },
            "critical": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                "ip-match": {"ip-dscp": 46},  # EF
            },
            "bulk": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                # Default match — all IP traffic not matched above
            },
        }
        return match_map.get(traffic_class, {})
```

---

## 4. Feature 3 — Digital Twin Validation Sandbox

### 4.1 Sandbox Manager

```python
# services/digital-twin/twin_manager.py

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from mininet_topology import MininetTopologyBuilder
from batfish_validator import BatfishValidator

class ValidationResult(Enum):
    PASS = "pass"
    FAIL_LOOP_DETECTED = "fail_loop"
    FAIL_POLICY_VIOLATION = "fail_policy"
    FAIL_UNREACHABLE = "fail_unreachable"
    FAIL_TIMEOUT = "fail_timeout"

@dataclass
class SandboxReport:
    result: ValidationResult
    details: str
    loop_free: bool
    policy_compliant: bool
    reachability_verified: bool
    execution_time_ms: float
    topology_snapshot: Optional[dict] = None

class DigitalTwinManager:
    """
    Orchestrates the validation pipeline:
    
    1. Snapshot current production topology
    2. Replicate in Mininet virtual network
    3. Apply proposed routing change
    4. Run Batfish analysis (loop detection, policy compliance)
    5. Run Mininet traffic test (actual packet forwarding)
    6. Return pass/fail with detailed report
    
    Target: Complete validation in <5 seconds (PVD quality requirement).
    """

    def __init__(self):
        self.topology_builder = MininetTopologyBuilder()
        self.batfish = BatfishValidator()
        self._active_sandbox = None

    async def validate_steering_decision(
        self,
        decision: "SteeringDecision",
        current_topology: dict,
        current_flows: list[dict],
    ) -> SandboxReport:
        """Full validation pipeline for a proposed steering change."""
        import time
        start = time.monotonic()
        
        try:
            # Step 1: Build virtual topology matching production
            topo = self.topology_builder.build_from_production(current_topology)
            
            # Step 2: Apply current flow rules
            self.topology_builder.apply_flows(topo, current_flows)
            
            # Step 3: Apply proposed change
            proposed_flows = self._generate_proposed_flows(decision, current_flows)
            self.topology_builder.apply_flows(topo, proposed_flows)
            
            # Step 4: Batfish static analysis
            batfish_result = await self.batfish.analyze(
                topology=current_topology,
                proposed_flows=proposed_flows,
            )
            
            if not batfish_result["loop_free"]:
                return SandboxReport(
                    result=ValidationResult.FAIL_LOOP_DETECTED,
                    details=f"Routing loop detected: {batfish_result['loop_path']}",
                    loop_free=False,
                    policy_compliant=batfish_result.get("policy_compliant", False),
                    reachability_verified=False,
                    execution_time_ms=(time.monotonic() - start) * 1000,
                )
            
            if not batfish_result["policy_compliant"]:
                return SandboxReport(
                    result=ValidationResult.FAIL_POLICY_VIOLATION,
                    details=f"Policy violation: {batfish_result['violations']}",
                    loop_free=True,
                    policy_compliant=False,
                    reachability_verified=False,
                    execution_time_ms=(time.monotonic() - start) * 1000,
                )
            
            # Step 5: Mininet live traffic test
            reachability = await asyncio.wait_for(
                self.topology_builder.test_reachability(topo),
                timeout=3.0,  # 3 second timeout for traffic test
            )
            
            elapsed = (time.monotonic() - start) * 1000
            
            return SandboxReport(
                result=ValidationResult.PASS if reachability else ValidationResult.FAIL_UNREACHABLE,
                details="All validations passed" if reachability else "Reachability test failed",
                loop_free=True,
                policy_compliant=True,
                reachability_verified=reachability,
                execution_time_ms=elapsed,
                topology_snapshot=current_topology,
            )
        
        except asyncio.TimeoutError:
            return SandboxReport(
                result=ValidationResult.FAIL_TIMEOUT,
                details="Sandbox validation exceeded 5-second timeout",
                loop_free=False,
                policy_compliant=False,
                reachability_verified=False,
                execution_time_ms=5000,
            )
        finally:
            if topo:
                self.topology_builder.cleanup(topo)
```

### 4.2 Mininet Topology Builder

```python
# services/digital-twin/mininet_topology.py

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel

class MininetTopologyBuilder:
    """
    Builds Mininet virtual networks that mirror production topology.
    
    Design:
    - Each WAN link becomes a Mininet link with tc-based QoS emulation
    - SDN switches use OVSSwitch with OpenFlow 1.3
    - Remote controller points to test SDN controller instance
    - Link characteristics (bandwidth, delay, loss) match production data
    """
    
    def build_from_production(self, topology: dict) -> Mininet:
        """
        Topology dict format:
        {
            "switches": [{"id": "s1", "dpid": "0000000000000001"}, ...],
            "hosts": [{"id": "h1", "ip": "10.0.1.1/24"}, ...],
            "links": [
                {"src": "s1", "dst": "s2", "bw": 100, "delay": "5ms", "loss": 0.1,
                 "link_id": "fiber-primary"},
                ...
            ]
        }
        """
        net = Mininet(
            switch=OVSSwitch,
            controller=RemoteController,
            link=TCLink,
            autoSetMacs=True,
        )
        
        # Add controller
        net.addController("c0", ip="127.0.0.1", port=6633)
        
        # Add switches
        switches = {}
        for sw in topology["switches"]:
            switches[sw["id"]] = net.addSwitch(
                sw["id"], dpid=sw["dpid"], protocols="OpenFlow13"
            )
        
        # Add hosts
        hosts = {}
        for h in topology["hosts"]:
            hosts[h["id"]] = net.addHost(h["id"], ip=h["ip"])
        
        # Add links with production-matched characteristics
        for link in topology["links"]:
            src = switches.get(link["src"]) or hosts.get(link["src"])
            dst = switches.get(link["dst"]) or hosts.get(link["dst"])
            net.addLink(
                src, dst,
                bw=link.get("bw", 100),
                delay=link.get("delay", "2ms"),
                loss=link.get("loss", 0),
            )
        
        net.start()
        return net

    def apply_flows(self, net: Mininet, flows: list[dict]):
        """Install OpenFlow rules on switches via ovs-ofctl."""
        for flow in flows:
            switch = net.get(flow["switch_id"])
            cmd = (
                f"ovs-ofctl -O OpenFlow13 add-flow {switch.name} "
                f"priority={flow['priority']},"
                f"{flow['match']},"
                f"actions={flow['actions']}"
            )
            switch.cmd(cmd)

    async def test_reachability(self, net: Mininet) -> bool:
        """Run ping and iperf tests to verify forwarding works."""
        hosts = net.hosts
        if len(hosts) < 2:
            return True
        
        # Ping test between all host pairs
        loss = net.pingAll(timeout=1)
        return loss == 0  # 0% loss = full reachability

    def cleanup(self, net: Mininet):
        """Tear down the virtual network."""
        net.stop()
```

### 4.3 Batfish Configuration Validator

```python
# services/digital-twin/batfish_validator.py

from pybatfish.client.session import Session
from pybatfish.datamodel.flow import HeaderConstraints

class BatfishValidator:
    """
    Uses Batfish for static network configuration analysis:
    - Routing loop detection
    - ACL/firewall policy compliance verification
    - Reachability analysis without live traffic
    
    Batfish analyzes configs statically (no live network needed),
    making it fast enough for the <5 second validation budget.
    """

    def __init__(self, batfish_host: str = "localhost"):
        self.bf = Session(host=batfish_host)

    async def analyze(self, topology: dict, proposed_flows: list[dict]) -> dict:
        """
        Run Batfish analysis on proposed configuration.
        
        Returns:
            {
                "loop_free": bool,
                "policy_compliant": bool,
                "loop_path": Optional[str],
                "violations": Optional[list[str]],
            }
        """
        # Initialize Batfish snapshot from topology configs
        self.bf.init_snapshot_from_text(
            self._topology_to_configs(topology, proposed_flows),
            name="validation_snapshot",
            overwrite=True,
        )
        
        # Loop detection
        loop_results = self.bf.q.detectLoops().answer().frame()
        has_loops = len(loop_results) > 0
        
        # ACL/Firewall compliance
        acl_results = self.bf.q.searchFilters(
            headers=HeaderConstraints(applications=["dns", "http", "https"]),
            action="deny",
        ).answer().frame()
        
        # Check for unintended denies
        violations = []
        for _, row in acl_results.iterrows():
            if row.get("Flow") and "critical" in str(row.get("Flow", "")):
                violations.append(f"Critical traffic blocked by {row.get('Filter', 'unknown')}")
        
        return {
            "loop_free": not has_loops,
            "policy_compliant": len(violations) == 0,
            "loop_path": str(loop_results.iloc[0]) if has_loops else None,
            "violations": violations if violations else None,
        }

    def _topology_to_configs(self, topology: dict, flows: list[dict]) -> dict:
        """Convert abstract topology to vendor-neutral configs for Batfish."""
        # Generate Cisco-style or Juniper-style configs from the topology
        # Batfish supports multi-vendor parsing
        configs = {}
        for sw in topology.get("switches", []):
            configs[f"{sw['id']}.cfg"] = self._generate_switch_config(sw, topology, flows)
        return configs
```

---

## 5. Feature 4 — Intent-Based Management Interface (IBN)

### 5.1 Backend: Natural Language Policy Engine

```python
# services/api-gateway/app/routers/policies.py

from fastapi import APIRouter, WebSocket, Depends
from pydantic import BaseModel
import re
from typing import Optional

router = APIRouter(prefix="/api/v1/policies", tags=["IBN"])

class IntentRequest(BaseModel):
    intent: str  # Natural language, e.g. "Prioritize VoIP over guest WiFi"

class PolicyRule(BaseModel):
    name: str
    traffic_class: str
    priority: int
    bandwidth_guarantee_mbps: Optional[float]
    latency_max_ms: Optional[float]
    action: str  # "prioritize", "throttle", "block", "redirect"
    target_links: list[str]

class IntentParser:
    """
    Rule-based + pattern matching NLP parser for network intents.
    
    For an academic project, a rule-based approach is more appropriate than
    a full LLM integration because:
    1. Deterministic and auditable (critical for network safety)
    2. No external API dependency
    3. Easier to test and validate exhaustively
    4. Can be extended incrementally
    
    Supported intent patterns:
    - "Prioritize {traffic} over {traffic}"
    - "Block {traffic} on {link}"
    - "Guarantee {bandwidth} for {traffic}"
    - "Limit {traffic} to {bandwidth}"
    - "Redirect {traffic} to {link}"
    - "Set maximum latency for {traffic} to {value}ms"
    """

    TRAFFIC_PATTERNS = {
        r"voip|voice|sip|phone\s*call": "voip",
        r"video|zoom|teams|conferencing|webex": "video",
        r"medical\s*imaging|dicom|pacs|surgical": "medical_imaging",
        r"financial|trading|transaction": "financial",
        r"guest\s*wi-?fi|guest\s*network": "guest_wifi",
        r"backup|sync|replication": "backup",
        r"web|browsing|http": "web_browsing",
        r"streaming|netflix|youtube": "streaming",
    }
    
    INTENT_PATTERNS = [
        (r"prioritize\s+(.+?)\s+over\s+(.+)", "prioritize"),
        (r"block\s+(.+?)\s+on\s+(.+)", "block"),
        (r"guarantee\s+(\d+)\s*(?:mbps|mb)\s+(?:for|to)\s+(.+)", "guarantee_bw"),
        (r"limit\s+(.+?)\s+to\s+(\d+)\s*(?:mbps|mb)", "limit_bw"),
        (r"redirect\s+(.+?)\s+to\s+(.+)", "redirect"),
        (r"(?:set|max)\s+latency\s+(?:for\s+)?(.+?)\s+(?:to\s+)?(\d+)\s*ms", "max_latency"),
    ]

    def parse(self, intent_text: str) -> list[PolicyRule]:
        """Parse natural language intent into structured policy rules."""
        text = intent_text.lower().strip()
        rules = []
        
        for pattern, action_type in self.INTENT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                if action_type == "prioritize":
                    high = self._resolve_traffic_class(match.group(1))
                    low = self._resolve_traffic_class(match.group(2))
                    rules.append(PolicyRule(
                        name=f"prioritize-{high}-over-{low}",
                        traffic_class=high,
                        priority=200,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=None,
                        action="prioritize",
                        target_links=["all"],
                    ))
                    rules.append(PolicyRule(
                        name=f"deprioritize-{low}",
                        traffic_class=low,
                        priority=50,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=None,
                        action="throttle",
                        target_links=["all"],
                    ))
                
                elif action_type == "guarantee_bw":
                    bw = float(match.group(1))
                    tc = self._resolve_traffic_class(match.group(2))
                    rules.append(PolicyRule(
                        name=f"guarantee-bw-{tc}",
                        traffic_class=tc,
                        priority=150,
                        bandwidth_guarantee_mbps=bw,
                        latency_max_ms=None,
                        action="prioritize",
                        target_links=["all"],
                    ))
                
                # ... handle other action types similarly
                break
        
        if not rules:
            raise ValueError(
                f"Could not parse intent: '{intent_text}'. "
                f"Try formats like: 'Prioritize VoIP over guest WiFi', "
                f"'Guarantee 50Mbps for video conferencing'"
            )
        
        return rules

    def _resolve_traffic_class(self, text: str) -> str:
        """Map natural language traffic description to canonical class."""
        text = text.strip()
        for pattern, class_name in self.TRAFFIC_PATTERNS.items():
            if re.search(pattern, text):
                return class_name
        return "custom"  # Unknown traffic class


# API Endpoints
intent_parser = IntentParser()

@router.post("/intent")
async def apply_intent(request: IntentRequest):
    """
    Parse a natural language network policy intent and apply it.
    
    Example: POST /api/v1/policies/intent
    Body: {"intent": "Prioritize medical imaging traffic over guest WiFi"}
    """
    rules = intent_parser.parse(request.intent)
    
    # Validate in sandbox before applying
    validation_results = []
    for rule in rules:
        # Convert rule to flow entries and validate
        # ... (calls Digital Twin Sandbox)
        validation_results.append({"rule": rule.name, "validated": True})
    
    return {
        "status": "applied",
        "intent": request.intent,
        "rules_generated": [r.dict() for r in rules],
        "validation": validation_results,
    }

@router.get("/active")
async def list_active_policies():
    """List all currently active network policies."""
    ...

@router.delete("/{policy_name}")
async def remove_policy(policy_name: str):
    """Remove an active policy and revert associated flow rules."""
    ...
```

---

## 6. Feature 5 — Multi-Link Health Scoreboard

### 6.1 Backend: WebSocket Real-Time Feed

```python
# services/api-gateway/app/websocket/scoreboard.py

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis

class ScoreboardManager:
    """
    Pushes real-time health scores to connected dashboard clients
    via WebSocket at 1Hz update rate.
    
    Data per link:
    - Current health score (0-100)
    - Predicted score in 30s / 60s
    - Confidence level
    - Raw metrics (latency, jitter, loss)
    - Active steering decisions
    - Trend direction (improving/stable/degrading)
    """

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)

    async def broadcast_loop(self):
        """Continuously fetch predictions and broadcast to all clients."""
        while True:
            try:
                link_ids = await self.redis.smembers("active_links")
                scoreboard_data = {}
                
                for link_id_bytes in link_ids:
                    link_id = link_id_bytes.decode()
                    pred = await self.redis.hgetall(f"prediction:{link_id}")
                    raw = await self.redis.xrevrange(f"telemetry:raw", count=1)
                    
                    if pred:
                        scoreboard_data[link_id] = {
                            "health_score": float(pred.get(b"health_score", 0)),
                            "confidence": float(pred.get(b"confidence", 0)),
                            "latency_current": self._get_latest_metric(raw, "latency_ms"),
                            "jitter_current": self._get_latest_metric(raw, "jitter_ms"),
                            "packet_loss_current": self._get_latest_metric(raw, "packet_loss_pct"),
                            "latency_forecast": json.loads(pred.get(b"latency_forecast", b"[]")),
                            "trend": self._compute_trend(pred),
                        }
                
                message = json.dumps({
                    "type": "scoreboard_update",
                    "data": scoreboard_data,
                    "timestamp": asyncio.get_event_loop().time(),
                })
                
                # Broadcast to all connected clients
                disconnected = []
                for ws in self.active_connections:
                    try:
                        await ws.send_text(message)
                    except WebSocketDisconnect:
                        disconnected.append(ws)
                
                for ws in disconnected:
                    self.active_connections.remove(ws)
            
            except Exception as e:
                print(f"Broadcast error: {e}")
            
            await asyncio.sleep(1.0)
```

### 6.2 Frontend: React Dashboard

```tsx
// frontend/src/components/HealthScoreboard/HealthScoreboard.tsx

import React, { useState, useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface LinkHealth {
  health_score: number;
  confidence: number;
  latency_current: number;
  jitter_current: number;
  packet_loss_current: number;
  latency_forecast: number[];
  trend: 'improving' | 'stable' | 'degrading';
}

interface ScoreboardData {
  [linkId: string]: LinkHealth;
}

const HealthScoreboard: React.FC = () => {
  const [data, setData] = useState<ScoreboardData>({});
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/ws/scoreboard`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'scoreboard_update') {
        setData(msg.data);
      }
    };

    return () => ws.close();
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-6">
      {Object.entries(data).map(([linkId, health]) => (
        <LinkCard key={linkId} linkId={linkId} health={health} />
      ))}
    </div>
  );
};

const LinkCard: React.FC<{ linkId: string; health: LinkHealth }> = ({ linkId, health }) => {
  const scoreColor = health.health_score >= 70
    ? '#22c55e'
    : health.health_score >= 40
    ? '#eab308'
    : '#ef4444';

  const trendIcon = {
    improving: '↑',
    stable: '→',
    degrading: '↓',
  };

  return (
    <div className="bg-white rounded-xl shadow-md p-5 border-l-4"
         style={{ borderLeftColor: scoreColor }}>
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-semibold text-gray-600 uppercase">{linkId}</h3>
        <span className="text-xs text-gray-400">
          {(health.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      {/* Health Score (large) */}
      <div className="text-center mb-4">
        <span className="text-5xl font-bold" style={{ color: scoreColor }}>
          {health.health_score.toFixed(0)}
        </span>
        <span className="text-lg ml-1" style={{ color: scoreColor }}>
          {trendIcon[health.trend]}
        </span>
        <p className="text-xs text-gray-400 mt-1">Health Score</p>
      </div>

      {/* Current Metrics */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <MetricBadge label="Latency" value={`${health.latency_current.toFixed(1)}ms`} />
        <MetricBadge label="Jitter" value={`${health.jitter_current.toFixed(1)}ms`} />
        <MetricBadge label="Loss" value={`${health.packet_loss_current.toFixed(2)}%`} />
      </div>

      {/* Forecast Sparkline */}
      <div className="mt-4">
        <ForecastSparkline data={health.latency_forecast} color={scoreColor} />
      </div>
    </div>
  );
};

const MetricBadge: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="bg-gray-50 rounded-md py-1 px-2">
    <div className="font-medium text-gray-700">{value}</div>
    <div className="text-gray-400">{label}</div>
  </div>
);

const ForecastSparkline: React.FC<{ data: number[]; color: string }> = ({ data, color }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || data.length === 0) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = 200, height = 40;
    const x = d3.scaleLinear().domain([0, data.length - 1]).range([0, width]);
    const y = d3.scaleLinear()
      .domain([d3.min(data)! * 0.9, d3.max(data)! * 1.1])
      .range([height, 0]);

    const line = d3.line<number>()
      .x((_, i) => x(i))
      .y((d) => y(d))
      .curve(d3.curveBasis);

    svg.append('path')
      .datum(data)
      .attr('d', line)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 1.5);
  }, [data, color]);

  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-gray-400">30s forecast</span>
      <svg ref={svgRef} width={200} height={40} />
    </div>
  );
};

export default HealthScoreboard;
```

---

## 7. API Gateway — Complete Route Map

```python
# services/api-gateway/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import telemetry, predictions, steering, sandbox, policies
from app.websocket.scoreboard import ScoreboardManager

scoreboard = ScoreboardManager(redis_url="redis://redis:6379")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    task = asyncio.create_task(scoreboard.broadcast_loop())
    yield
    task.cancel()

app = FastAPI(
    title="PathWise AI API",
    version="1.0.0",
    description="AI-Powered SD-WAN Management Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(telemetry.router)     # GET /api/v1/telemetry/{link_id}
app.include_router(predictions.router)    # GET /api/v1/predictions/{link_id}
app.include_router(steering.router)       # POST /api/v1/steering/execute
app.include_router(sandbox.router)        # POST /api/v1/sandbox/validate
app.include_router(policies.router)       # POST /api/v1/policies/intent

# WebSocket
@app.websocket("/ws/scoreboard")
async def scoreboard_ws(ws):
    await scoreboard.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep connection alive
    except:
        await scoreboard.disconnect(ws)
```

### REST API Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/telemetry/{link_id}?window=60s` | Raw telemetry for a link |
| `GET` | `/api/v1/telemetry/links` | List all active links |
| `GET` | `/api/v1/predictions/{link_id}` | Latest prediction + health score |
| `GET` | `/api/v1/predictions/all` | All link predictions (dashboard) |
| `POST` | `/api/v1/steering/execute` | Manually trigger a steering action |
| `GET` | `/api/v1/steering/history` | Audit log of past steering decisions |
| `POST` | `/api/v1/sandbox/validate` | Run sandbox validation for proposed change |
| `GET` | `/api/v1/sandbox/reports/{id}` | Retrieve sandbox validation report |
| `POST` | `/api/v1/policies/intent` | Submit natural language policy |
| `GET` | `/api/v1/policies/active` | List active policies |
| `DELETE` | `/api/v1/policies/{name}` | Remove a policy |
| `WS` | `/ws/scoreboard` | Real-time health score stream |

---

## 8. Docker Compose — Full Stack

```yaml
# docker-compose.yml

version: "3.9"

services:
  # --- Data Layer ---
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: pathwise
      POSTGRES_USER: pathwise
      POSTGRES_PASSWORD: pathwise_dev
    ports:
      - "5432:5432"
    volumes:
      - timescale_data:/var/lib/postgresql/data
      - ./infra/db/init.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  # --- SDN Controllers ---
  opendaylight:
    image: opendaylight/odl:latest
    ports:
      - "6633:6633"   # OpenFlow
      - "8181:8181"   # RESTCONF
    environment:
      FEATURES: odl-restconf,odl-l2switch-switch,odl-openflowplugin-flow-services

  # --- Network Emulation ---
  mininet:
    build: ./infra/mininet
    privileged: true
    network_mode: host
    depends_on:
      - opendaylight

  batfish:
    image: batfish/allinone:latest
    ports:
      - "9997:9997"   # Batfish API
      - "9996:9996"   # Batfish coordinator

  # --- Application Services ---
  api-gateway:
    build: ./services/api-gateway
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - timescaledb
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://pathwise:pathwise_dev@timescaledb:5432/pathwise

  telemetry-ingestion:
    build: ./services/telemetry-ingestion
    depends_on:
      - redis
      - timescaledb
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://pathwise:pathwise_dev@timescaledb:5432/pathwise

  prediction-engine:
    build: ./services/prediction-engine
    depends_on:
      - redis
    environment:
      REDIS_URL: redis://redis:6379
      MODEL_PATH: /models/best_model.pt
    volumes:
      - ./ml/checkpoints:/models

  traffic-steering:
    build: ./services/traffic-steering
    depends_on:
      - redis
      - opendaylight
    environment:
      REDIS_URL: redis://redis:6379
      ODL_URL: http://opendaylight:8181

  digital-twin:
    build: ./services/digital-twin
    privileged: true
    depends_on:
      - mininet
      - batfish
    environment:
      BATFISH_HOST: batfish

  # --- Frontend ---
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api-gateway
    environment:
      REACT_APP_API_URL: http://localhost:8000

volumes:
  timescale_data:
```

---

## 9. Testing Strategy

### 9.1 Test Pyramid

| Level | Target | Tools | Coverage Goal |
|-------|--------|-------|---------------|
| Unit | Individual functions, LSTM layers, parsers | pytest, PyTorch test utils | 80%+ |
| Integration | Service-to-service (API→Redis→Prediction) | pytest + docker-compose | All API endpoints |
| ML Validation | Model accuracy, regression detection | Custom eval scripts | ≥90% MSE target |
| Sandbox E2E | Full validation pipeline | Mininet + Batfish in CI | All failure modes |
| System E2E | Complete flow: telemetry→prediction→steering | Cypress + docker-compose | Critical user paths |

### 9.2 Key Test Cases

```python
# tests/unit/test_intent_parser.py

import pytest
from services.api_gateway.app.routers.policies import IntentParser

parser = IntentParser()

class TestIntentParser:
    def test_prioritize_voip_over_guest(self):
        rules = parser.parse("Prioritize VoIP over guest WiFi")
        assert len(rules) == 2
        assert rules[0].traffic_class == "voip"
        assert rules[0].priority > rules[1].priority
        assert rules[1].traffic_class == "guest_wifi"

    def test_guarantee_bandwidth(self):
        rules = parser.parse("Guarantee 50 Mbps for video conferencing")
        assert rules[0].bandwidth_guarantee_mbps == 50.0
        assert rules[0].traffic_class == "video"

    def test_invalid_intent_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parser.parse("Make the network go brrr")

    def test_case_insensitive(self):
        rules = parser.parse("PRIORITIZE MEDICAL IMAGING OVER GUEST WIFI")
        assert rules[0].traffic_class == "medical_imaging"


# tests/unit/test_health_score.py

class TestHealthScore:
    def test_perfect_health(self):
        """Low latency, jitter, loss → score near 100."""
        ...

    def test_degraded_health(self):
        """High latency → score below 50."""
        ...

    def test_confidence_scaling(self):
        """Low confidence should reduce the score."""
        ...


# tests/integration/test_steering_pipeline.py

class TestSteeringPipeline:
    """
    Integration test: publish degradation alert → steering engine
    picks it up → validates in sandbox → executes handoff.
    """
    
    async def test_preemptive_shift_flow(self):
        # 1. Publish low health score to Redis
        # 2. Wait for steering engine to evaluate
        # 3. Verify sandbox validation was triggered
        # 4. Verify new flow rules were installed
        # 5. Verify old flow rules were removed
        # 6. Verify audit log entry
        ...

    async def test_sandbox_blocks_bad_change(self):
        # 1. Configure Batfish to detect a loop
        # 2. Trigger steering decision
        # 3. Verify decision was blocked
        # 4. Verify no production flows changed
        ...
```

### 9.3 ML Model Evaluation

```python
# ml/scripts/evaluate.py

def evaluate_model(model, test_loader, scaler):
    """
    Evaluation metrics for PVD compliance:
    
    1. MSE ≤ threshold (PVD: ≥90% accuracy measured by MSE)
    2. Per-metric MAE (latency, jitter, packet_loss)
    3. Brownout detection rate (recall for degradation events)
    4. False positive rate (unnecessary steering triggers)
    5. Prediction horizon analysis (accuracy at 10s, 30s, 60s)
    """
    metrics = {
        "mse_latency": [],
        "mse_jitter": [],
        "mse_packet_loss": [],
        "brownout_recall": [],
        "false_positive_rate": [],
    }
    
    model.eval()
    with torch.no_grad():
        for X, y in test_loader:
            preds, confidence = model(X)
            
            # Per-metric MSE
            for i, key in enumerate(["latency", "jitter", "packet_loss"]):
                mse = ((preds[key] - y[:, :, i]) ** 2).mean().item()
                metrics[f"mse_{key}"].append(mse)
            
            # Brownout detection: did we predict score < 50 when actual < 50?
            actual_health = compute_health_from_targets(y)
            predicted_health = compute_health_from_preds(preds)
            
            true_brownouts = actual_health < 50
            predicted_brownouts = predicted_health < 50
            
            if true_brownouts.any():
                recall = (predicted_brownouts & true_brownouts).sum() / true_brownouts.sum()
                metrics["brownout_recall"].append(recall.item())
            
            false_positives = (predicted_brownouts & ~true_brownouts).sum()
            total_non_brownouts = (~true_brownouts).sum()
            if total_non_brownouts > 0:
                fpr = false_positives / total_non_brownouts
                metrics["false_positive_rate"].append(fpr.item())
    
    return {k: np.mean(v) for k, v in metrics.items()}
```

---

## 10. Implementation Timeline (Semester Plan)

| Week | Sprint | Deliverable | Dependencies |
|------|--------|-------------|-------------|
| 1-2 | Sprint 0 | Repo setup, Docker Compose, CI pipeline, DB schema | None |
| 3-4 | Sprint 1 | Synthetic data generator, Feature engineering, LSTM v1 trained | Sprint 0 |
| 5-6 | Sprint 2 | Telemetry ingestion service, Redis pub/sub, Prediction serving | Sprint 1 |
| 7-8 | Sprint 3 | SDN controller integration (OpenDaylight), Steering engine, Make-before-break handoff | Sprint 2 |
| 9-10 | Sprint 4 | Mininet topology builder, Batfish validator, Sandbox pipeline | Sprint 3 |
| 11-12 | Sprint 5 | IBN parser, Policy API, React dashboard (Scoreboard + IBN console) | Sprint 4 |
| 13-14 | Sprint 6 | E2E integration testing, ML evaluation, Performance tuning | All |
| 15 | Release | Final demo, documentation, project presentation | All |

### Critical Path

```
Synthetic Data → LSTM Training → Prediction Service → Steering Engine → Sandbox Validation
                                                                         ↓
                                                           IBN Interface (parallel)
                                                           Health Scoreboard (parallel)
```

The LSTM model and prediction service are on the critical path. Frontend and IBN can be developed in parallel by different team members once the API contracts are defined.

---

## 11. Team Work Distribution

| Member | Primary Responsibility | Key Deliverables |
|--------|----------------------|------------------|
| **Vineeth (PM)** | Project coordination, API Gateway, Integration | FastAPI gateway, Docker orchestration, CI/CD, final integration |
| **Meghana (Requirements)** | ML Pipeline, Data Engineering | Synthetic data gen, feature engineering, LSTM training, model evaluation |
| **Bharadwaj (Design/Test)** | Frontend, Testing | React dashboard, Health Scoreboard, IBN console, test suite |
| **Sricharitha (Config/Tech)** | Infrastructure, SDN Integration | Mininet/Batfish setup, SDN controller integration, steering engine, Digital Twin |

---

## 12. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LSTM accuracy < 90% target | High | Use ensemble of smaller models; increase training data via augmentation; fallback to simpler ARIMA baseline |
| Mininet/Batfish < 5s validation | Medium | Pre-warm sandbox topology; cache unchanged portions; parallelize Batfish + reachability tests |
| OpenDaylight API breaking changes | Medium | Abstract SDN client behind interface; maintain ONOS as backup; pin controller version |
| Insufficient real telemetry data | High | Synthetic data generator with configurable brownout patterns; transfer learning from synthetic → real |
| Team member unavailability | Medium | Cross-training on adjacent components; documented API contracts enable independent work |

---

## 13. Key Design Decisions & Rationale

**Why PyTorch over TensorFlow?** PyTorch provides more intuitive debugging for custom LSTM architectures, better support for dynamic computation graphs (useful for variable-length sequences), and a more active research community for time-series models.

**Why TimescaleDB over InfluxDB?** TimescaleDB is PostgreSQL-based, so the team can use familiar SQL for complex queries, joins, and aggregations. Continuous aggregates handle the rollup pipeline natively. InfluxDB would require learning Flux query language.

**Why FastAPI over Flask/Django?** Native async support is critical for the WebSocket-heavy scoreboard and the Redis pub/sub consumers. Auto-generated OpenAPI docs accelerate frontend-backend contract alignment. Type safety via Pydantic catches schema errors at dev time.

**Why Redis Streams over Kafka?** For an academic project with a 4-person team, Kafka's operational complexity (ZooKeeper, broker management) is unjustified. Redis Streams provides the same pub/sub semantics with consumer groups, at a fraction of the infrastructure cost.

**Why rule-based IBN over LLM?** Determinism is essential for network safety. A rule-based parser produces identical output for identical input, is fully unit-testable, and has zero external dependencies. An LLM-based approach would introduce non-determinism, latency, and cost that are inappropriate for a production network management system.
