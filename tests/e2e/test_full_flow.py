# tests/e2e/test_full_flow.py

"""
End-to-end test: Full PathWise pipeline

Simulates the critical path:
  Synthetic Data -> Feature Engineering -> LSTM Prediction ->
  Health Score -> Steering Decision

This test validates that all components work together correctly
without external dependencies (Redis, SDN controllers, etc.).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "prediction-engine"))

import pytest
import numpy as np
import pandas as pd
import torch

from model.lstm_network import PathWiseLSTM, PathWiseLoss
from model.feature_engineering import FeatureEngineer
from model.inference import InferenceEngine


class TestFullFlow:
    """End-to-end pipeline test without external services."""

    def test_synthetic_data_to_prediction(self):
        """
        Full pipeline: generate synthetic data -> engineer features ->
        create sequences -> run LSTM inference -> compute health score.
        """
        # Step 1: Generate synthetic data inline
        n = 200
        df = pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=n, freq="1s"),
            "link_id": "e2e-test-link",
            "latency_ms": 15 + 5 * np.sin(np.linspace(0, 4 * np.pi, n)) + np.random.normal(0, 1, n),
            "jitter_ms": 2 + np.random.normal(0, 0.3, n),
            "packet_loss_pct": np.clip(0.05 + np.random.normal(0, 0.01, n), 0, 100),
            "bandwidth_util_pct": 50 + 10 * np.sin(np.linspace(0, 2 * np.pi, n)) + np.random.normal(0, 3, n),
            "rtt_ms": 30 + 10 * np.sin(np.linspace(0, 4 * np.pi, n)) + np.random.normal(0, 1, n),
        })

        # Step 2: Feature engineering
        fe = FeatureEngineer()
        df = fe.compute_features(df)
        assert len(df.columns) > 7  # Original 7 + engineered features

        # Step 3: Create sequences
        X, y = fe.create_sequences(df)
        assert X.shape[1] == 60   # Window size
        assert X.shape[2] == 13   # Num features
        assert y.shape[1] == 30   # Horizon
        assert y.shape[2] == 3    # Target metrics

        # Step 4: Normalize
        X_norm = fe.normalize(X, "e2e-test-link", fit=True)
        assert X_norm.min() >= -0.01
        assert X_norm.max() <= 1.01

        # Step 5: LSTM inference
        model = PathWiseLSTM()
        model.eval()

        with torch.no_grad():
            x = torch.tensor(X_norm[:1])
            preds, confidence = model(x)

        assert preds["latency"].shape == (1, 30)
        assert preds["jitter"].shape == (1, 30)
        assert preds["packet_loss"].shape == (1, 30)
        assert 0 <= confidence[0].item() <= 1

        # Step 6: Health score
        engine = InferenceEngine()
        score = engine.compute_health_score(preds, confidence)
        assert 0 <= score <= 100

    def test_training_loop_smoke(self):
        """Smoke test: model can be trained for 1 epoch without errors."""
        n = 200
        df = pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=n, freq="1s"),
            "link_id": "train-test",
            "latency_ms": np.random.uniform(10, 50, n),
            "jitter_ms": np.random.uniform(1, 10, n),
            "packet_loss_pct": np.random.uniform(0, 2, n),
            "bandwidth_util_pct": np.random.uniform(20, 80, n),
            "rtt_ms": np.random.uniform(20, 100, n),
        })

        fe = FeatureEngineer()
        df = fe.compute_features(df)
        X, y = fe.create_sequences(df)
        X = fe.normalize(X, "train-test", fit=True)

        model = PathWiseLSTM()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        criterion = PathWiseLoss()

        # Single training step
        model.train()
        x_batch = torch.tensor(X[:8])
        y_batch = torch.tensor(y[:8])

        optimizer.zero_grad()
        preds, confidence = model(x_batch)
        loss = criterion(preds, y_batch, confidence=confidence)
        loss.backward()
        optimizer.step()

        assert loss.item() > 0
        assert not torch.isnan(loss)

    def test_model_save_and_load(self, tmp_path):
        """Model should be saveable and loadable without data loss."""
        model = PathWiseLSTM()

        # Save
        checkpoint_path = tmp_path / "test_model.pt"
        torch.save({
            "epoch": 1,
            "model_state_dict": model.state_dict(),
            "val_loss": 0.5,
        }, checkpoint_path)

        # Load
        loaded_model = PathWiseLSTM()
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        loaded_model.load_state_dict(checkpoint["model_state_dict"])

        # Verify identical outputs
        model.eval()
        loaded_model.eval()

        test_input = torch.randn(1, 60, 13)
        with torch.no_grad():
            p1, c1 = model(test_input)
            p2, c2 = loaded_model(test_input)

        torch.testing.assert_close(p1["latency"], p2["latency"])
        torch.testing.assert_close(c1, c2)
