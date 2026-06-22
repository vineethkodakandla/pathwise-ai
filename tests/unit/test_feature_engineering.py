# tests/unit/test_feature_engineering.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "prediction-engine"))

import pytest
import numpy as np
import pandas as pd
from model.feature_engineering import FeatureEngineer


class TestFeatureEngineer:
    def setup_method(self):
        self.fe = FeatureEngineer()
        # Create sample telemetry data
        n = 200
        self.df = pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=n, freq="1s"),
            "link_id": "test-link",
            "latency_ms": np.random.uniform(10, 50, n),
            "jitter_ms": np.random.uniform(1, 10, n),
            "packet_loss_pct": np.random.uniform(0, 2, n),
            "bandwidth_util_pct": np.random.uniform(20, 80, n),
            "rtt_ms": np.random.uniform(20, 100, n),
        })

    def test_compute_features_adds_columns(self):
        """Feature engineering should add 8 new columns."""
        result = self.fe.compute_features(self.df)
        expected_new_cols = [
            "mean_latency_30s", "std_latency_30s", "mean_jitter_30s",
            "ema_latency", "ema_packet_loss",
            "d_latency", "d_jitter", "d_packet_loss",
        ]
        for col in expected_new_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_create_sequences_shapes(self):
        """Sequences should have correct shapes."""
        df = self.fe.compute_features(self.df)
        X, y = self.fe.create_sequences(df)

        expected_samples = len(df) - self.fe.WINDOW_SIZE - self.fe.HORIZON
        assert X.shape == (expected_samples, self.fe.WINDOW_SIZE, self.fe.NUM_FEATURES)
        assert y.shape == (expected_samples, self.fe.HORIZON, 3)

    def test_create_sequences_dtype(self):
        """Sequences should be float32."""
        df = self.fe.compute_features(self.df)
        X, y = self.fe.create_sequences(df)
        assert X.dtype == np.float32
        assert y.dtype == np.float32

    def test_normalize_range(self):
        """Normalized data should be in [0, 1]."""
        df = self.fe.compute_features(self.df)
        X, _ = self.fe.create_sequences(df)
        X_norm = self.fe.normalize(X, "test-link", fit=True)

        assert X_norm.min() >= -0.01, f"Min value {X_norm.min()} < 0"
        assert X_norm.max() <= 1.01, f"Max value {X_norm.max()} > 1"

    def test_normalize_inverse_consistency(self):
        """Normalizing with fit=False should use saved scalers."""
        df = self.fe.compute_features(self.df)
        X, _ = self.fe.create_sequences(df)

        X_norm1 = self.fe.normalize(X, "test-link", fit=True)
        X_norm2 = self.fe.normalize(X, "test-link", fit=False)

        np.testing.assert_array_almost_equal(X_norm1, X_norm2)

    def test_rolling_features_not_nan(self):
        """Rolling features should not contain NaN after computation."""
        df = self.fe.compute_features(self.df)
        assert not df["mean_latency_30s"].isna().any()
        assert not df["std_latency_30s"].isna().any()
        assert not df["d_latency"].isna().any()
