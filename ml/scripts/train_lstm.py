"""
Train the PathWiseLSTM model on synthetic telemetry data.

Reads parquet files, engineers 13 features, creates sliding windows
(60-step input → 30-step forecast target), trains, and saves checkpoint.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "prediction-engine"))

from model.lstm_network import PathWiseLSTM, PathWiseLoss


# ── Feature Engineering ──────────────────────────────────────

def rolling_mean(arr: np.ndarray, w: int = 30) -> np.ndarray:
    s = pd.Series(arr)
    return s.rolling(w, min_periods=1).mean().values.astype(np.float32)


def rolling_std(arr: np.ndarray, w: int = 30) -> np.ndarray:
    s = pd.Series(arr)
    return s.rolling(w, min_periods=1).std().fillna(0).values.astype(np.float32)


def ema(arr: np.ndarray, alpha: float = 0.3) -> np.ndarray:
    s = pd.Series(arr)
    return s.ewm(alpha=alpha, adjust=False).mean().values.astype(np.float32)


def build_features(df: pd.DataFrame) -> np.ndarray:
    """Build 13 features from raw 5-column telemetry DataFrame."""
    lat = df["latency_ms"].values.astype(np.float32)
    jit = df["jitter_ms"].values.astype(np.float32)
    pkt = df["packet_loss_pct"].values.astype(np.float32)
    bw = df["bandwidth_util_pct"].values.astype(np.float32)
    rtt = df["rtt_ms"].values.astype(np.float32)

    features = np.column_stack([
        lat, jit, pkt, bw, rtt,                         # 1-5: raw
        rolling_mean(lat), rolling_std(lat),             # 6-7: latency stats
        rolling_mean(jit),                               # 8: jitter smoothed
        ema(lat), ema(pkt),                              # 9-10: EMAs
        np.diff(lat, prepend=lat[0]),                    # 11: delta latency
        np.diff(jit, prepend=jit[0]),                    # 12: delta jitter
        np.diff(pkt, prepend=pkt[0]),                    # 13: delta loss
    ])
    return features


# ── Dataset ──────────────────────────────────────────────────

class TelemetryDataset(Dataset):
    """Sliding window dataset: 60 input steps → 30 target steps, with stride."""

    def __init__(self, features: np.ndarray, input_len: int = 60, horizon: int = 30, stride: int = 30):
        self.features = torch.tensor(features, dtype=torch.float32)
        self.input_len = input_len
        self.horizon = horizon
        max_start = len(features) - input_len - horizon
        self.indices = list(range(0, max_start, stride))

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        i = self.indices[idx]
        x = self.features[i: i + self.input_len]
        y = self.features[i + self.input_len: i + self.input_len + self.horizon, :3]
        return x, y


# ── Training ─────────────────────────────────────────────────

def train():
    data_dir = PROJECT_ROOT / "ml" / "data" / "synthetic"
    ckpt_dir = PROJECT_ROOT / "ml" / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(data_dir.glob("*.parquet"))
    if not parquet_files:
        print("ERROR: No parquet files found. Run generate_synthetic_data.py first.")
        return

    # Load and combine all links
    print(f"Loading data from {len(parquet_files)} files...")
    all_features = []
    for f in parquet_files:
        df = pd.read_parquet(f)
        print(f"  {f.stem}: {len(df):,} rows ... ", end="", flush=True)
        t = time.time()
        feats = build_features(df)
        print(f"features built in {time.time()-t:.1f}s")
        all_features.append(feats)

    # Normalize features per-column across all data
    combined = np.vstack(all_features)
    means = combined.mean(axis=0)
    stds = combined.std(axis=0) + 1e-8
    print(f"Total data points: {len(combined):,}")

    # Create datasets per link, then combine
    datasets = []
    for feats in all_features:
        normed = (feats - means) / stds
        ds = TelemetryDataset(normed)
        datasets.append(ds)
    full_dataset = torch.utils.data.ConcatDataset(datasets)

    # Train/validation split (90/10)
    n_total = len(full_dataset)
    n_val = max(1000, n_total // 10)
    n_train = n_total - n_val
    train_ds, val_ds = torch.utils.data.random_split(full_dataset, [n_train, n_val])
    print(f"Train samples: {n_train:,} | Validation samples: {n_val:,}")

    train_loader = DataLoader(train_ds, batch_size=512, shuffle=True, num_workers=0, pin_memory=False)
    val_loader = DataLoader(val_ds, batch_size=512, shuffle=False, num_workers=0)

    # Model
    model = PathWiseLSTM(input_size=13, hidden_size=128, num_layers=2, dropout=0.2, horizon=30)
    criterion = PathWiseLoss(weights={"latency": 1.0, "jitter": 1.0, "packet_loss": 2.0}, underestimate_penalty=2.0)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {n_params:,}")
    print(f"Training on CPU...")
    print("-" * 60)

    best_val_loss = float("inf")
    epochs = 10

    for epoch in range(1, epochs + 1):
        t0 = time.time()

        # Train
        model.train()
        train_loss = 0.0
        n_batches = 0
        for x_batch, y_batch in train_loader:
            optimizer.zero_grad()
            preds, confidence = model(x_batch)
            loss = criterion(preds, y_batch, confidence=confidence)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()
            n_batches += 1

        avg_train = train_loss / max(n_batches, 1)

        # Validate
        model.eval()
        val_loss = 0.0
        n_val_batches = 0
        with torch.no_grad():
            for x_batch, y_batch in val_loader:
                preds, confidence = model(x_batch)
                loss = criterion(preds, y_batch, confidence=confidence)
                val_loss += loss.item()
                n_val_batches += 1

        avg_val = val_loss / max(n_val_batches, 1)
        scheduler.step(avg_val)

        elapsed = time.time() - t0
        lr = optimizer.param_groups[0]["lr"]
        marker = ""

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            marker = " * BEST"
            torch.save({
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "epoch": epoch,
                "val_loss": avg_val,
                "means": means.tolist(),
                "stds": stds.tolist(),
            }, ckpt_dir / "best_model.pt")

        print(f"Epoch {epoch:2d}/{epochs} | "
              f"Train: {avg_train:.4f} | Val: {avg_val:.4f} | "
              f"LR: {lr:.1e} | {elapsed:.1f}s{marker}")

    print("-" * 60)
    print(f"Training complete. Best val loss: {best_val_loss:.4f}")
    print(f"Checkpoint saved to: {ckpt_dir / 'best_model.pt'}")


if __name__ == "__main__":
    train()
