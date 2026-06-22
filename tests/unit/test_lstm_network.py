# tests/unit/test_lstm_network.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "prediction-engine"))

import pytest
import torch
from model.lstm_network import PathWiseLSTM, PathWiseLoss


class TestPathWiseLSTM:
    def setup_method(self):
        self.model = PathWiseLSTM(
            input_size=13, hidden_size=128, num_layers=2,
            dropout=0.2, horizon=30, num_targets=3,
        )

    def test_output_shapes(self):
        """Model output shapes match expected dimensions."""
        batch_size = 4
        x = torch.randn(batch_size, 60, 13)
        preds, confidence = self.model(x)

        assert preds["latency"].shape == (batch_size, 30)
        assert preds["jitter"].shape == (batch_size, 30)
        assert preds["packet_loss"].shape == (batch_size, 30)
        assert confidence.shape == (batch_size, 1)

    def test_confidence_range(self):
        """Confidence should be in [0, 1] due to sigmoid."""
        x = torch.randn(8, 60, 13)
        _, confidence = self.model(x)

        assert (confidence >= 0).all(), "Confidence should be >= 0"
        assert (confidence <= 1).all(), "Confidence should be <= 1"

    def test_gradient_flow(self):
        """Gradients should flow through the entire model."""
        x = torch.randn(2, 60, 13)
        y = torch.randn(2, 30, 3)

        preds, confidence = self.model(x)
        loss_fn = PathWiseLoss()
        loss = loss_fn(preds, y, confidence=confidence)
        loss.backward()

        for name, param in self.model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"
                assert not torch.isnan(param.grad).any(), f"NaN gradient for {name}"

    def test_batch_size_invariant(self):
        """Same input should produce same output regardless of batch."""
        self.model.eval()
        single = torch.randn(1, 60, 13)
        batched = single.repeat(4, 1, 1)

        with torch.no_grad():
            p1, c1 = self.model(single)
            p4, c4 = self.model(batched)

        torch.testing.assert_close(p1["latency"].expand(4, -1), p4["latency"], atol=1e-5, rtol=1e-5)


class TestPathWiseLoss:
    def test_loss_positive(self):
        """Loss should always be positive."""
        loss_fn = PathWiseLoss()
        preds = {
            "latency": torch.randn(4, 30),
            "jitter": torch.randn(4, 30),
            "packet_loss": torch.randn(4, 30),
        }
        targets = torch.randn(4, 30, 3)
        loss = loss_fn(preds, targets)
        assert loss.item() > 0

    def test_asymmetric_penalty(self):
        """Underestimates should produce higher loss than overestimates."""
        loss_fn = PathWiseLoss(underestimate_penalty=3.0)
        targets = torch.ones(4, 30, 3) * 10

        # Overestimate: pred > target
        preds_over = {
            "latency": torch.ones(4, 30) * 15,
            "jitter": torch.ones(4, 30) * 15,
            "packet_loss": torch.ones(4, 30) * 15,
        }
        # Underestimate: pred < target (same magnitude)
        preds_under = {
            "latency": torch.ones(4, 30) * 5,
            "jitter": torch.ones(4, 30) * 5,
            "packet_loss": torch.ones(4, 30) * 5,
        }

        loss_over = loss_fn(preds_over, targets)
        loss_under = loss_fn(preds_under, targets)

        assert loss_under > loss_over, (
            f"Underestimate loss ({loss_under.item():.4f}) should be > "
            f"overestimate loss ({loss_over.item():.4f})"
        )
