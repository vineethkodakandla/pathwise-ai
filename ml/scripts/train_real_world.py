"""
PathWise AI — LSTM Training on Real-World Calibrated Data.

Complete training pipeline:
  1. Load real-world calibrated parquet data
  2. Engineer 13 features per timestep
  3. Create sliding-window dataset (60 in → 30 out)
  4. Train PathWiseLSTM with asymmetric loss
  5. Evaluate on held-out test set
  6. Save best checkpoint for inference
"""

from __future__ import annotations
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

# Add project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "services" / "prediction-engine"))
from model.lstm_network import PathWiseLSTM, PathWiseLoss

DATA_DIR = PROJECT_ROOT / "ml" / "data" / "real_world"
CHECKPOINT_DIR = PROJECT_ROOT / "ml" / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# ── Hyperparameters ────────────────────────────────────────────

WINDOW_SIZE = 60       # 60-second lookback
HORIZON = 30           # 30-second forecast
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
MAX_EPOCHS = 50
EARLY_STOP_PATIENCE = 10
LR_PATIENCE = 5
GRADIENT_CLIP = 1.0
TRAIN_RATIO = 0.7
VAL_RATIO = 0.15
# TEST_RATIO = 0.15 (remainder)


# ── Feature Engineering ────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> np.ndarray:
    """
    Build the 13-feature matrix from raw 5-metric telemetry.

    Features:
      0: latency_ms (raw)
      1: jitter_ms (raw)
      2: packet_loss_pct (raw)
      3: bandwidth_util_pct (raw)
      4: rtt_ms (raw)
      5: mean_latency_30s (rolling)
      6: std_latency_30s (rolling)
      7: mean_jitter_30s (rolling)
      8: ema_latency (alpha=0.3)
      9: ema_packet_loss (alpha=0.3)
      10: d_latency (rate of change)
      11: d_jitter (rate of change)
      12: d_packet_loss (rate of change)
    """
    lat = df["latency_ms"].values.astype(np.float32)
    jit = df["jitter_ms"].values.astype(np.float32)
    pkt = df["packet_loss_pct"].values.astype(np.float32)
    bw = df["bandwidth_util_pct"].values.astype(np.float32)
    rtt = df["rtt_ms"].values.astype(np.float32)

    n = len(lat)

    # Rolling statistics (30-second window)
    mean_lat = pd.Series(lat).rolling(30, min_periods=1).mean().values.astype(np.float32)
    std_lat = pd.Series(lat).rolling(30, min_periods=1).std().fillna(0).values.astype(np.float32)
    mean_jit = pd.Series(jit).rolling(30, min_periods=1).mean().values.astype(np.float32)

    # Exponential moving averages
    ema_lat = pd.Series(lat).ewm(alpha=0.3, adjust=False).mean().values.astype(np.float32)
    ema_pkt = pd.Series(pkt).ewm(alpha=0.3, adjust=False).mean().values.astype(np.float32)

    # Rate of change
    d_lat = np.diff(lat, prepend=lat[0]).astype(np.float32)
    d_jit = np.diff(jit, prepend=jit[0]).astype(np.float32)
    d_pkt = np.diff(pkt, prepend=pkt[0]).astype(np.float32)

    features = np.column_stack([
        lat, jit, pkt, bw, rtt,
        mean_lat, std_lat, mean_jit,
        ema_lat, ema_pkt,
        d_lat, d_jit, d_pkt,
    ])
    return features


# ── Dataset ────────────────────────────────────────────────────

class TelemetryDataset(Dataset):
    """Sliding window dataset: 60-step input → 30-step target (lat, jit, loss)."""

    def __init__(self, features: np.ndarray, raw_df: pd.DataFrame, stride: int = 1):
        self.features = features
        self.raw_lat = raw_df["latency_ms"].values.astype(np.float32)
        self.raw_jit = raw_df["jitter_ms"].values.astype(np.float32)
        self.raw_loss = raw_df["packet_loss_pct"].values.astype(np.float32)
        self.stride = stride

        self.n_samples = max(0, (len(features) - WINDOW_SIZE - HORIZON) // stride)

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        start = idx * self.stride
        end = start + WINDOW_SIZE
        target_end = end + HORIZON

        x = torch.tensor(self.features[start:end], dtype=torch.float32)

        # Target: raw values for next HORIZON steps
        target = torch.stack([
            torch.tensor(self.raw_lat[end:target_end], dtype=torch.float32),
            torch.tensor(self.raw_jit[end:target_end], dtype=torch.float32),
            torch.tensor(self.raw_loss[end:target_end], dtype=torch.float32),
        ], dim=-1)  # (HORIZON, 3)

        return x, target


# ── Training ───────────────────────────────────────────────────

def train_epoch(model, loader, criterion, optimizer, device, grad_clip):
    model.train()
    total_loss = 0
    n_batches = 0

    for x, target in loader:
        x, target = x.to(device), target.to(device)

        optimizer.zero_grad()
        preds, confidence = model(x)
        loss = criterion(preds, target, confidence=confidence)
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()

        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


def validate(model, loader, criterion, device):
    model.eval()
    total_loss = 0
    n_batches = 0
    all_preds = {"latency": [], "jitter": [], "packet_loss": []}
    all_targets = {"latency": [], "jitter": [], "packet_loss": []}

    with torch.no_grad():
        for x, target in loader:
            x, target = x.to(device), target.to(device)
            preds, confidence = model(x)
            loss = criterion(preds, target, confidence=confidence)
            total_loss += loss.item()
            n_batches += 1

            for key in all_preds:
                all_preds[key].append(preds[key].cpu())
            all_targets["latency"].append(target[:, :, 0].cpu())
            all_targets["jitter"].append(target[:, :, 1].cpu())
            all_targets["packet_loss"].append(target[:, :, 2].cpu())

    avg_loss = total_loss / max(n_batches, 1)

    # Compute per-metric MAE
    metrics = {}
    for key in all_preds:
        p = torch.cat(all_preds[key])
        t = torch.cat(all_targets[key])
        metrics[f"{key}_mae"] = (p - t).abs().mean().item()
        metrics[f"{key}_rmse"] = ((p - t) ** 2).mean().sqrt().item()

    return avg_loss, metrics


def main():
    print("=" * 70)
    print("PathWise AI — LSTM Training Pipeline (Real-World Data)")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"PyTorch: {torch.__version__}")

    # ── Load Data ──────────────────────────────────────────────
    print("\n[1/5] Loading real-world calibrated data...")
    link_ids = ["fiber-primary", "broadband-secondary", "satellite-backup", "5g-mobile"]
    all_features = []
    all_dfs = []

    for link_id in link_ids:
        path = DATA_DIR / f"{link_id}.parquet"
        if not path.exists():
            print(f"  [ERROR] Missing data: {path}")
            print("  Run 'python ml/scripts/fetch_real_data.py' first!")
            return

        df = pd.read_parquet(path)
        print(f"  {link_id}: {len(df):,} points loaded")

        features = engineer_features(df)
        all_features.append(features)
        all_dfs.append(df)

    # Concatenate all links
    combined_features = np.concatenate(all_features, axis=0)
    combined_df = pd.concat(all_dfs, ignore_index=True)
    print(f"\n  Combined: {len(combined_df):,} points, {combined_features.shape[1]} features")

    # ── Normalize ──────────────────────────────────────────────
    print("\n[2/5] Normalizing features...")
    feat_means = combined_features.mean(axis=0)
    feat_stds = combined_features.std(axis=0)
    feat_stds[feat_stds < 1e-8] = 1.0  # Prevent division by zero

    normalized = (combined_features - feat_means) / feat_stds
    print(f"  Feature means: {np.round(feat_means, 2)}")
    print(f"  Feature stds:  {np.round(feat_stds, 2)}")

    # ── Split per-link, then concatenate (to avoid cross-link windows) ──
    print("\n[3/5] Creating train/val/test datasets...")

    train_datasets = []
    val_datasets = []
    test_datasets = []
    offset = 0

    for i, link_id in enumerate(link_ids):
        n = len(all_dfs[i])
        link_features = normalized[offset:offset + n]
        link_df = all_dfs[i].reset_index(drop=True)

        train_end = int(n * TRAIN_RATIO)
        val_end = int(n * (TRAIN_RATIO + VAL_RATIO))

        train_datasets.append(TelemetryDataset(
            link_features[:train_end], link_df.iloc[:train_end], stride=15
        ))
        val_datasets.append(TelemetryDataset(
            link_features[train_end:val_end], link_df.iloc[train_end:val_end], stride=30
        ))
        test_datasets.append(TelemetryDataset(
            link_features[val_end:], link_df.iloc[val_end:].reset_index(drop=True), stride=30
        ))
        offset += n

    train_ds = torch.utils.data.ConcatDataset(train_datasets)
    val_ds = torch.utils.data.ConcatDataset(val_datasets)
    test_ds = torch.utils.data.ConcatDataset(test_datasets)

    print(f"  Train: {len(train_ds):,} windows")
    print(f"  Val:   {len(val_ds):,} windows")
    print(f"  Test:  {len(test_ds):,} windows")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=0, pin_memory=False, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False,
                            num_workers=0, pin_memory=False)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False,
                             num_workers=0, pin_memory=False)

    # ── Model ──────────────────────────────────────────────────
    print("\n[4/5] Initializing model...")
    model = PathWiseLSTM(
        input_size=13,
        hidden_size=128,
        num_layers=2,
        dropout=0.2,
        horizon=HORIZON,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Architecture: PathWiseLSTM (2-layer, 128 hidden, attention)")
    print(f"  Parameters: {total_params:,} total, {trainable_params:,} trainable")

    criterion = PathWiseLoss(
        weights={"latency": 1.0, "jitter": 1.0, "packet_loss": 2.0},
        underestimate_penalty=2.0,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=LR_PATIENCE
    )

    # ── Training Loop ──────────────────────────────────────────
    print(f"\n[5/5] Training for up to {MAX_EPOCHS} epochs...")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Learning rate: {LEARNING_RATE}")
    print(f"  Early stopping patience: {EARLY_STOP_PATIENCE}")
    print(f"  Gradient clip: {GRADIENT_CLIP}")
    print("-" * 70)

    best_val_loss = float("inf")
    epochs_no_improve = 0
    best_epoch = 0
    training_log = []

    for epoch in range(1, MAX_EPOCHS + 1):
        t0 = time.time()

        # Train
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device, GRADIENT_CLIP)

        # Validate
        val_loss, val_metrics = validate(model, val_loader, criterion, device)

        # Scheduler step
        scheduler.step(val_loss)

        elapsed = time.time() - t0
        lr = optimizer.param_groups[0]["lr"]

        log_entry = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "lr": lr,
            "elapsed": elapsed,
            **val_metrics,
        }
        training_log.append(log_entry)

        # Print progress
        lat_mae = val_metrics["latency_mae"]
        jit_mae = val_metrics["jitter_mae"]
        loss_mae = val_metrics["packet_loss_mae"]
        print(
            f"  Epoch {epoch:3d}/{MAX_EPOCHS} | "
            f"train={train_loss:.4f} val={val_loss:.4f} | "
            f"MAE lat={lat_mae:.2f}ms jit={jit_mae:.2f}ms loss={loss_mae:.4f}% | "
            f"lr={lr:.1e} | {elapsed:.1f}s"
        )

        # Save best
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            epochs_no_improve = 0

            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "val_metrics": val_metrics,
                "means": feat_means.tolist(),
                "stds": feat_stds.tolist(),
                "hyperparameters": {
                    "input_size": 13,
                    "hidden_size": 128,
                    "num_layers": 2,
                    "dropout": 0.2,
                    "horizon": HORIZON,
                    "window_size": WINDOW_SIZE,
                    "batch_size": BATCH_SIZE,
                    "learning_rate": LEARNING_RATE,
                },
                "training_data": "real_world_calibrated",
                "link_types": link_ids,
            }
            torch.save(checkpoint, CHECKPOINT_DIR / "best_model.pt")
            print(f"    * New best model saved (val_loss={val_loss:.4f})")
        else:
            epochs_no_improve += 1

        # Early stopping
        if epochs_no_improve >= EARLY_STOP_PATIENCE:
            print(f"\n  Early stopping at epoch {epoch} (no improvement for {EARLY_STOP_PATIENCE} epochs)")
            break

    # ── Test Evaluation ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Final Evaluation on Test Set")
    print("=" * 70)

    # Load best model
    best_ckpt = torch.load(CHECKPOINT_DIR / "best_model.pt", map_location=device, weights_only=False)
    model.load_state_dict(best_ckpt["model_state_dict"])
    print(f"  Loaded best model from epoch {best_ckpt['epoch']}")

    test_loss, test_metrics = validate(model, test_loader, criterion, device)
    print(f"\n  Test Loss: {test_loss:.4f}")
    print(f"  Latency  — MAE: {test_metrics['latency_mae']:.2f}ms,  RMSE: {test_metrics['latency_rmse']:.2f}ms")
    print(f"  Jitter   — MAE: {test_metrics['jitter_mae']:.2f}ms,  RMSE: {test_metrics['jitter_rmse']:.2f}ms")
    print(f"  Pkt Loss — MAE: {test_metrics['packet_loss_mae']:.4f}%, RMSE: {test_metrics['packet_loss_rmse']:.4f}%")

    # Health score quality check
    print("\n  Running health score inference check...")
    model.eval()
    health_scores = []
    with torch.no_grad():
        for x, target in test_loader:
            x = x.to(device)
            preds, confidence = model(x)
            for i in range(len(x)):
                lat_fc = preds["latency"][i].cpu().numpy()
                jit_fc = preds["jitter"][i].cpu().numpy()
                pkt_fc = preds["packet_loss"][i].cpu().numpy()
                conf = confidence[i].item()

                lat_avg = lat_fc.mean()
                jit_avg = jit_fc.mean()
                pkt_avg = pkt_fc.mean()

                lat_s = max(0, min(100, 100 * (1 - (lat_avg - 30) / 170)))
                jit_s = max(0, min(100, 100 * (1 - (jit_avg - 5) / 45)))
                pkt_s = max(0, min(100, 100 * (1 - (pkt_avg - 0.1) / 4.9)))
                raw = 0.4 * lat_s + 0.3 * jit_s + 0.3 * pkt_s
                health = raw * (0.5 + 0.5 * conf)
                health_scores.append(health)
            if len(health_scores) > 5000:
                break

    hs = np.array(health_scores)
    print(f"  Health Score Distribution (n={len(hs)}):")
    print(f"    Mean: {hs.mean():.1f}, Std: {hs.std():.1f}")
    print(f"    Min: {hs.min():.1f}, Max: {hs.max():.1f}")
    print(f"    <30 (critical): {(hs < 30).sum()} ({(hs < 30).mean()*100:.1f}%)")
    print(f"    30-70 (warning): {((hs >= 30) & (hs < 70)).sum()} ({((hs >= 30) & (hs < 70)).mean()*100:.1f}%)")
    print(f"    ≥70 (healthy): {(hs >= 70).sum()} ({(hs >= 70).mean()*100:.1f}%)")

    # Save training log
    log_path = CHECKPOINT_DIR / "training_log.json"
    with open(log_path, "w") as f:
        json.dump({
            "training_log": training_log,
            "best_epoch": best_epoch,
            "best_val_loss": best_val_loss,
            "test_loss": test_loss,
            "test_metrics": test_metrics,
            "health_score_stats": {
                "mean": float(hs.mean()),
                "std": float(hs.std()),
                "critical_pct": float((hs < 30).mean() * 100),
                "warning_pct": float(((hs >= 30) & (hs < 70)).mean() * 100),
                "healthy_pct": float((hs >= 70).mean() * 100),
            },
        }, f, indent=2)
    print(f"\n  Training log saved: {log_path}")

    print("\n" + "=" * 70)
    print(f"Training complete! Best model at epoch {best_epoch}:")
    print(f"  Checkpoint: {CHECKPOINT_DIR / 'best_model.pt'}")
    print(f"  Val Loss:   {best_val_loss:.4f}")
    print(f"  Test Loss:  {test_loss:.4f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
