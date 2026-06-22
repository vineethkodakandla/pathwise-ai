# tests/unit/test_health_score.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "prediction-engine"))

import pytest
import torch
from model.inference import InferenceEngine


class TestHealthScore:
    def setup_method(self):
        self.engine = InferenceEngine()

    def test_perfect_health(self):
        """Low latency, jitter, loss -> score near 100."""
        preds = {
            "latency": torch.tensor([[10.0] * 30]),
            "jitter": torch.tensor([[1.0] * 30]),
            "packet_loss": torch.tensor([[0.01] * 30]),
        }
        confidence = torch.tensor([[0.95]])

        score = self.engine.compute_health_score(preds, confidence)
        assert score > 85, f"Perfect health should score >85, got {score}"

    def test_degraded_health(self):
        """High latency -> score below 50."""
        preds = {
            "latency": torch.tensor([[150.0] * 30]),
            "jitter": torch.tensor([[25.0] * 30]),
            "packet_loss": torch.tensor([[3.0] * 30]),
        }
        confidence = torch.tensor([[0.9]])

        score = self.engine.compute_health_score(preds, confidence)
        assert score < 50, f"Degraded health should score <50, got {score}"

    def test_confidence_scaling(self):
        """Low confidence should reduce the score."""
        preds = {
            "latency": torch.tensor([[20.0] * 30]),
            "jitter": torch.tensor([[2.0] * 30]),
            "packet_loss": torch.tensor([[0.05] * 30]),
        }

        high_conf = torch.tensor([[0.95]])
        low_conf = torch.tensor([[0.1]])

        score_high = self.engine.compute_health_score(preds, high_conf)
        score_low = self.engine.compute_health_score(preds, low_conf)

        assert score_high > score_low, (
            f"High confidence score ({score_high}) should be > "
            f"low confidence score ({score_low})"
        )

    def test_extreme_degradation(self):
        """Maximum degradation -> score near 0."""
        preds = {
            "latency": torch.tensor([[250.0] * 30]),
            "jitter": torch.tensor([[60.0] * 30]),
            "packet_loss": torch.tensor([[10.0] * 30]),
        }
        confidence = torch.tensor([[0.95]])

        score = self.engine.compute_health_score(preds, confidence)
        assert score < 10, f"Extreme degradation should score <10, got {score}"

    def test_score_bounds(self):
        """Score should always be in [0, 100]."""
        test_cases = [
            (0.0, 0.0, 0.0),      # Best possible
            (500.0, 100.0, 50.0),  # Worst possible
            (30.0, 5.0, 0.1),     # Threshold values
        ]
        for lat, jit, pkt in test_cases:
            preds = {
                "latency": torch.tensor([[lat] * 30]),
                "jitter": torch.tensor([[jit] * 30]),
                "packet_loss": torch.tensor([[pkt] * 30]),
            }
            confidence = torch.tensor([[0.8]])
            score = self.engine.compute_health_score(preds, confidence)
            assert 0 <= score <= 100, f"Score {score} out of bounds for ({lat}, {jit}, {pkt})"
