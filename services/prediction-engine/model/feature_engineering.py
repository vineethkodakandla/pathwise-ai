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
