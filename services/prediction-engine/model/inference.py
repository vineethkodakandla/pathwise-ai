# services/prediction-engine/model/inference.py

import torch
import numpy as np
from typing import Optional
from pathlib import Path

from .lstm_network import PathWiseLSTM
from .feature_engineering import FeatureEngineer


class InferenceEngine:
    """
    Handles model loading and real-time inference for the prediction service.

    Responsibilities:
    - Load and cache the trained LSTM model
    - Accept raw telemetry windows and produce predictions
    - Compute health scores from predictions
    - Manage model versioning for hot-reload
    """

    def __init__(self, model_path: str = "checkpoints/best_model.pt"):
        self.model_path = Path(model_path)
        self.model: Optional[PathWiseLSTM] = None
        self.feature_eng = FeatureEngineer()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def load_model(self) -> bool:
        """Load the trained model from checkpoint."""
        if not self.model_path.exists():
            return False

        self.model = PathWiseLSTM()
        checkpoint = torch.load(self.model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()
        return True

    def predict(self, window: np.ndarray) -> Optional[dict]:
        """
        Run inference on a single feature window.

        Args:
            window: numpy array of shape (60, 13) — one link's feature window

        Returns:
            dict with keys: latency, jitter, packet_loss (each list[float]),
            confidence (float), health_score (float)
        """
        if self.model is None:
            return None

        with torch.no_grad():
            x = torch.tensor(window, dtype=torch.float32).unsqueeze(0).to(self.device)
            preds, confidence = self.model(x)

        result = {
            "latency": preds["latency"][0].cpu().numpy().tolist(),
            "jitter": preds["jitter"][0].cpu().numpy().tolist(),
            "packet_loss": preds["packet_loss"][0].cpu().numpy().tolist(),
            "confidence": float(confidence[0].cpu().item()),
        }
        result["health_score"] = self.compute_health_score(preds, confidence)
        return result

    def predict_batch(self, windows: np.ndarray) -> list[dict]:
        """
        Run batch inference on multiple feature windows.

        Args:
            windows: numpy array of shape (batch, 60, 13)

        Returns:
            list of prediction dicts
        """
        if self.model is None:
            return []

        with torch.no_grad():
            x = torch.tensor(windows, dtype=torch.float32).to(self.device)
            preds, confidence = self.model(x)

        results = []
        for i in range(len(windows)):
            result = {
                "latency": preds["latency"][i].cpu().numpy().tolist(),
                "jitter": preds["jitter"][i].cpu().numpy().tolist(),
                "packet_loss": preds["packet_loss"][i].cpu().numpy().tolist(),
                "confidence": float(confidence[i].cpu().item()),
            }
            result["health_score"] = self._compute_single_health(
                preds["latency"][i], preds["jitter"][i],
                preds["packet_loss"][i], confidence[i]
            )
            results.append(result)
        return results

    def compute_health_score(self, preds: dict, confidence: torch.Tensor) -> float:
        """
        Composite health score (0-100):
        - Latency: <30ms = 100, >200ms = 0  (weight: 0.4)
        - Jitter: <5ms = 100, >50ms = 0     (weight: 0.3)
        - Packet Loss: <0.1% = 100, >5% = 0 (weight: 0.3)
        """
        lat = preds["latency"][0].mean().item()
        jit = preds["jitter"][0].mean().item()
        pkt = preds["packet_loss"][0].mean().item()
        conf = confidence[0].item()

        lat_score = max(0, min(100, 100 * (1 - (lat - 30) / 170)))
        jit_score = max(0, min(100, 100 * (1 - (jit - 5) / 45)))
        pkt_score = max(0, min(100, 100 * (1 - (pkt - 0.1) / 4.9)))

        raw_score = 0.4 * lat_score + 0.3 * jit_score + 0.3 * pkt_score
        return round(raw_score * (0.5 + 0.5 * conf), 1)

    def _compute_single_health(
        self, lat_tensor, jit_tensor, pkt_tensor, conf_tensor
    ) -> float:
        """Compute health score for a single sample in a batch."""
        lat = lat_tensor.mean().item()
        jit = jit_tensor.mean().item()
        pkt = pkt_tensor.mean().item()
        conf = conf_tensor.item()

        lat_score = max(0, min(100, 100 * (1 - (lat - 30) / 170)))
        jit_score = max(0, min(100, 100 * (1 - (jit - 5) / 45)))
        pkt_score = max(0, min(100, 100 * (1 - (pkt - 0.1) / 4.9)))

        raw_score = 0.4 * lat_score + 0.3 * jit_score + 0.3 * pkt_score
        return round(raw_score * (0.5 + 0.5 * conf), 1)
