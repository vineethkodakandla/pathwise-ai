"""
LSTM prediction engine — runs inference every second on the latest telemetry.

Uses the same PathWiseLSTM architecture from the original project.
If no trained checkpoint exists, creates a model with random weights
that still produces plausible-looking predictions for the demo.
"""

from __future__ import annotations
import asyncio
import math
import random
import time
from pathlib import Path

import numpy as np

from server.state import state, LinkPrediction, TelemetryPoint

try:
    import torch
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "services" / "prediction-engine"))
    from model.lstm_network import PathWiseLSTM

    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False


class PredictionEngine:
    def __init__(self):
        self.model = None
        self.feat_means: np.ndarray | None = None
        self.feat_stds: np.ndarray | None = None
        self._load_model()

    def _load_model(self):
        if not TORCH_AVAILABLE:
            return
        self.model = PathWiseLSTM(input_size=13, hidden_size=128, num_layers=2)
        ckpt = Path("ml/checkpoints/best_model.pt")
        if ckpt.exists():
            try:
                data = torch.load(ckpt, map_location="cpu", weights_only=False)
                self.model.load_state_dict(data["model_state_dict"])
                if "means" in data and "stds" in data:
                    self.feat_means = np.array(data["means"], dtype=np.float32)
                    self.feat_stds = np.array(data["stds"], dtype=np.float32)
                print(f"[lstm] Trained model loaded (epoch {data.get('epoch')}, val_loss {data.get('val_loss', '?'):.4f})")
            except Exception as e:
                print(f"[lstm] Failed to load checkpoint: {e}")
        else:
            print("[lstm] No checkpoint found, using random weights")
        self.model.eval()

    def predict_link(self, link_id: str) -> LinkPrediction | None:
        points = state.get_latest_telemetry(link_id, 60)
        if len(points) < 30:
            return None

        if self.model is not None and TORCH_AVAILABLE:
            return self._predict_with_model(link_id, points)
        return self._predict_heuristic(link_id, points)

    def _predict_with_model(self, link_id: str, points: list[TelemetryPoint]) -> LinkPrediction:
        import torch

        features = self._build_features(points)
        if features is None:
            return self._predict_heuristic(link_id, points)

        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            preds, confidence = self.model(x)

        lat_fc = preds["latency"][0].numpy().tolist()
        jit_fc = preds["jitter"][0].numpy().tolist()
        pkt_fc = preds["packet_loss"][0].numpy().tolist()
        conf = float(confidence[0].item())
        health = self._compute_health(lat_fc, jit_fc, pkt_fc, conf)

        reasoning = self._generate_reasoning(health, conf, lat_fc, jit_fc, pkt_fc)
        return LinkPrediction(
            link_id=link_id,
            health_score=health,
            confidence=conf,
            latency_forecast=lat_fc,
            jitter_forecast=jit_fc,
            packet_loss_forecast=pkt_fc,
            timestamp=time.time(),
            reasoning=reasoning,
        )

    def _predict_heuristic(self, link_id: str, points: list[TelemetryPoint]) -> LinkPrediction:
        """Heuristic-based prediction when no trained model is available."""
        recent = points[-20:]
        lat_vals = [p.latency_ms for p in recent]
        jit_vals = [p.jitter_ms for p in recent]
        pkt_vals = [p.packet_loss_pct for p in recent]

        lat_mean = sum(lat_vals) / len(lat_vals)
        jit_mean = sum(jit_vals) / len(jit_vals)
        pkt_mean = sum(pkt_vals) / len(pkt_vals)

        lat_trend = (lat_vals[-1] - lat_vals[0]) / max(len(lat_vals), 1)
        jit_trend = (jit_vals[-1] - jit_vals[0]) / max(len(jit_vals), 1)
        pkt_trend = (pkt_vals[-1] - pkt_vals[0]) / max(len(pkt_vals), 1)

        lat_fc, jit_fc, pkt_fc = [], [], []
        for i in range(30):
            lat_fc.append(max(1, lat_mean + lat_trend * i + random.gauss(0, 1)))
            jit_fc.append(max(0, jit_mean + jit_trend * i + random.gauss(0, 0.3)))
            pkt_fc.append(max(0, pkt_mean + pkt_trend * i + random.gauss(0, 0.01)))

        confidence = max(0.3, min(0.95, 1.0 - abs(lat_trend) / 10))
        health = self._compute_health(lat_fc, jit_fc, pkt_fc, confidence)

        reasoning = self._generate_reasoning(health, confidence, lat_fc, jit_fc, pkt_fc)
        return LinkPrediction(
            link_id=link_id,
            health_score=health,
            confidence=confidence,
            latency_forecast=lat_fc,
            jitter_forecast=jit_fc,
            packet_loss_forecast=pkt_fc,
            timestamp=time.time(),
            reasoning=reasoning,
        )

    def _build_features(self, points: list[TelemetryPoint]) -> np.ndarray | None:
        if len(points) < 60:
            return None

        pts = points[-60:]
        raw = np.array(
            [[p.latency_ms, p.jitter_ms, p.packet_loss_pct, p.bandwidth_util_pct, p.rtt_ms] for p in pts],
            dtype=np.float32,
        )

        lat = raw[:, 0]
        jit = raw[:, 1]
        pkt = raw[:, 2]

        def rolling_mean(arr, w=30):
            out = np.empty_like(arr)
            for i in range(len(arr)):
                start = max(0, i - w + 1)
                out[i] = arr[start : i + 1].mean()
            return out

        def rolling_std(arr, w=30):
            out = np.empty_like(arr)
            for i in range(len(arr)):
                start = max(0, i - w + 1)
                out[i] = arr[start : i + 1].std() if i > 0 else 0
            return out

        def ema(arr, alpha=0.3):
            out = np.empty_like(arr)
            out[0] = arr[0]
            for i in range(1, len(arr)):
                out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
            return out

        mean_lat = rolling_mean(lat)
        std_lat = rolling_std(lat)
        mean_jit = rolling_mean(jit)
        ema_lat = ema(lat)
        ema_pkt = ema(pkt)
        d_lat = np.diff(lat, prepend=lat[0])
        d_jit = np.diff(jit, prepend=jit[0])
        d_pkt = np.diff(pkt, prepend=pkt[0])

        features = np.column_stack([
            raw, mean_lat, std_lat, mean_jit, ema_lat, ema_pkt, d_lat, d_jit, d_pkt
        ])

        if self.feat_means is not None and self.feat_stds is not None:
            features = (features - self.feat_means) / self.feat_stds

        return features

    @staticmethod
    def _compute_health(lat_fc, jit_fc, pkt_fc, confidence):
        lat = sum(lat_fc) / len(lat_fc)
        jit = sum(jit_fc) / len(jit_fc)
        pkt = sum(pkt_fc) / len(pkt_fc)

        lat_s = max(0, min(100, 100 * (1 - (lat - 30) / 170)))
        jit_s = max(0, min(100, 100 * (1 - (jit - 5) / 45)))
        pkt_s = max(0, min(100, 100 * (1 - (pkt - 0.1) / 4.9)))

        raw_score = 0.4 * lat_s + 0.3 * jit_s + 0.3 * pkt_s
        return round(raw_score * (0.5 + 0.5 * confidence), 1)

    @staticmethod
    def _generate_reasoning(health_score, confidence, lat_fc, jit_fc, pkt_fc,
                            lat_trend=None) -> str:
        """
        Generate a human-readable explanation for the prediction.
        Satisfies Req-Func-Sw-14: display reasoning for every automated path switch.
        """
        parts = []
        avg_lat = sum(lat_fc) / max(len(lat_fc), 1)
        avg_jit = sum(jit_fc) / max(len(jit_fc), 1)
        avg_pkt = sum(pkt_fc) / max(len(pkt_fc), 1)

        # Health assessment
        if health_score >= 80:
            parts.append("Link is healthy")
        elif health_score >= 50:
            parts.append("Link is degrading")
        else:
            parts.append("Link is critically degraded")

        # Confidence explanation
        if confidence >= 0.85:
            parts.append("with high prediction confidence")
        elif confidence >= 0.6:
            parts.append("with moderate confidence")
        else:
            parts.append("with low confidence (unstable pattern)")

        # Dominant factor
        factors = []
        if avg_lat > 80:
            factors.append(f"high latency ({avg_lat:.0f}ms)")
        if avg_jit > 15:
            factors.append(f"elevated jitter ({avg_jit:.1f}ms)")
        if avg_pkt > 1.0:
            factors.append(f"packet loss ({avg_pkt:.2f}%)")

        if factors:
            parts.append("due to " + ", ".join(factors))
        else:
            parts.append("with stable metrics across all indicators")

        # Trend
        if lat_fc and len(lat_fc) >= 3:
            delta = lat_fc[-1] - lat_fc[0]
            if delta > 10:
                parts.append("— latency trending upward")
            elif delta < -10:
                parts.append("— latency improving")

        return ". ".join(parts) + "."


engine = PredictionEngine()


async def prediction_loop():
    """Background loop: run predictions at 1 Hz for all active links."""
    while True:
        try:
            for link_id in state.active_links:
                pred = engine.predict_link(link_id)
                if pred:
                    state.predictions[link_id] = pred
        except Exception as e:
            print(f"[prediction] error: {e}")

        await asyncio.sleep(1.0)
