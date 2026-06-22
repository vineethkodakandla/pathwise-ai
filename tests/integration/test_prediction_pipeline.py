# tests/integration/test_prediction_pipeline.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "prediction-engine"))

import pytest
import numpy as np
import torch
from model.lstm_network import PathWiseLSTM
from model.feature_engineering import FeatureEngineer
from model.inference import InferenceEngine


class TestPredictionPipeline:
    """
    Integration tests for the full prediction pipeline:
    raw data -> feature engineering -> LSTM inference -> health score.
    """

    def test_full_inference_pipeline(self, sample_telemetry_df):
        """End-to-end: raw data -> features -> model -> predictions."""
        fe = FeatureEngineer()
        df = fe.compute_features(sample_telemetry_df)
        X, y = fe.create_sequences(df)
        assert len(X) > 0

        X_norm = fe.normalize(X, "test-link", fit=True)

        model = PathWiseLSTM()
        model.eval()

        with torch.no_grad():
            x_tensor = torch.tensor(X_norm[:1])
            preds, confidence = model(x_tensor)

        assert "latency" in preds
        assert "jitter" in preds
        assert "packet_loss" in preds
        assert preds["latency"].shape == (1, 30)
        assert 0 <= confidence[0].item() <= 1

    def test_inference_engine_without_checkpoint(self):
        """InferenceEngine should handle missing checkpoint gracefully."""
        engine = InferenceEngine(model_path="nonexistent/path.pt")
        loaded = engine.load_model()
        assert loaded is False

        result = engine.predict(np.random.randn(60, 13).astype(np.float32))
        assert result is None

    def test_inference_engine_batch(self, sample_telemetry_df):
        """Batch inference should produce results for each sample."""
        fe = FeatureEngineer()
        df = fe.compute_features(sample_telemetry_df)
        X, _ = fe.create_sequences(df)
        X_norm = fe.normalize(X, "test-link", fit=True)

        engine = InferenceEngine()
        engine.model = PathWiseLSTM()
        engine.model.eval()

        results = engine.predict_batch(X_norm[:5])
        assert len(results) == 5
        for r in results:
            assert "latency" in r
            assert "health_score" in r
            assert 0 <= r["health_score"] <= 100

    def test_health_score_consistency(self, sample_telemetry_df):
        """Health scores should be consistent across inference methods."""
        fe = FeatureEngineer()
        df = fe.compute_features(sample_telemetry_df)
        X, _ = fe.create_sequences(df)
        X_norm = fe.normalize(X, "test-link", fit=True)

        engine = InferenceEngine()
        engine.model = PathWiseLSTM()
        engine.model.eval()

        single = engine.predict(X_norm[0])
        batch = engine.predict_batch(X_norm[:1])

        assert single is not None
        assert len(batch) == 1
        # Scores should be close (not exact due to dropout in eval mode)
        assert abs(single["health_score"] - batch[0]["health_score"]) < 1.0
