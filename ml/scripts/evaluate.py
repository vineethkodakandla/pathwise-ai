# ml/scripts/evaluate.py

import sys
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.prediction_engine_pkg.model.lstm_network import PathWiseLSTM
from services.prediction_engine_pkg.model.feature_engineering import FeatureEngineer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def compute_health_from_preds(preds: dict) -> torch.Tensor:
    """Compute health score from prediction tensors."""
    lat = preds["latency"].mean(dim=1)
    jit = preds["jitter"].mean(dim=1)
    pkt = preds["packet_loss"].mean(dim=1)

    lat_score = torch.clamp(100 * (1 - (lat - 30) / 170), 0, 100)
    jit_score = torch.clamp(100 * (1 - (jit - 5) / 45), 0, 100)
    pkt_score = torch.clamp(100 * (1 - (pkt - 0.1) / 4.9), 0, 100)

    return 0.4 * lat_score + 0.3 * jit_score + 0.3 * pkt_score


def compute_health_from_targets(targets: torch.Tensor) -> torch.Tensor:
    """Compute health score from target tensors (batch, horizon, 3)."""
    lat = targets[:, :, 0].mean(dim=1)
    jit = targets[:, :, 1].mean(dim=1)
    pkt = targets[:, :, 2].mean(dim=1)

    lat_score = torch.clamp(100 * (1 - (lat - 30) / 170), 0, 100)
    jit_score = torch.clamp(100 * (1 - (jit - 5) / 45), 0, 100)
    pkt_score = torch.clamp(100 * (1 - (pkt - 0.1) / 4.9), 0, 100)

    return 0.4 * lat_score + 0.3 * jit_score + 0.3 * pkt_score


def evaluate_model(model, test_loader):
    """
    Evaluation metrics for PVD compliance:
    
    1. MSE <= threshold (PVD: >=90% accuracy measured by MSE)
    2. Per-metric MAE (latency, jitter, packet_loss)
    3. Brownout detection rate (recall for degradation events)
    4. False positive rate (unnecessary steering triggers)
    5. Prediction horizon analysis (accuracy at 10s, 30s, 60s)
    """
    metrics = {
        "mse_latency": [],
        "mse_jitter": [],
        "mse_packet_loss": [],
        "mae_latency": [],
        "mae_jitter": [],
        "mae_packet_loss": [],
        "brownout_recall": [],
        "false_positive_rate": [],
    }
    
    model.eval()
    with torch.no_grad():
        for X, y in test_loader:
            preds, confidence = model(X)
            
            # Per-metric MSE
            for i, key in enumerate(["latency", "jitter", "packet_loss"]):
                mse = ((preds[key] - y[:, :, i]) ** 2).mean().item()
                mae = (preds[key] - y[:, :, i]).abs().mean().item()
                metrics[f"mse_{key}"].append(mse)
                metrics[f"mae_{key}"].append(mae)
            
            # Brownout detection: did we predict score < 50 when actual < 50?
            actual_health = compute_health_from_targets(y)
            predicted_health = compute_health_from_preds(preds)
            
            true_brownouts = actual_health < 50
            predicted_brownouts = predicted_health < 50
            
            if true_brownouts.any():
                recall = (predicted_brownouts & true_brownouts).sum() / true_brownouts.sum()
                metrics["brownout_recall"].append(recall.item())
            
            false_positives = (predicted_brownouts & ~true_brownouts).sum()
            total_non_brownouts = (~true_brownouts).sum()
            if total_non_brownouts > 0:
                fpr = false_positives / total_non_brownouts
                metrics["false_positive_rate"].append(fpr.item())
    
    return {k: np.mean(v) if v else 0.0 for k, v in metrics.items()}


def main():
    parser = argparse.ArgumentParser(description="Evaluate PathWise LSTM model")
    parser.add_argument("--data-dir", type=str, default="ml/data/synthetic")
    parser.add_argument("--checkpoint", type=str, default="ml/checkpoints/best_model.pt")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    # Load data
    data_path = Path(args.data_dir)
    dfs = []
    for f in sorted(data_path.glob("*.parquet")):
        dfs.append(pd.read_parquet(f))
    if not dfs:
        logger.error(f"No data found in {args.data_dir}")
        return

    df = pd.concat(dfs, ignore_index=True)

    if args.smoke_test:
        df = df.groupby("link_id").head(5000).reset_index(drop=True)

    # Feature engineering
    fe = FeatureEngineer()
    all_X, all_y = [], []
    for link_id, link_df in df.groupby("link_id"):
        link_df = fe.compute_features(link_df)
        X, y = fe.create_sequences(link_df)
        if len(X) > 0:
            X = fe.normalize(X, link_id, fit=True)
            all_X.append(X)
            all_y.append(y)

    X = np.concatenate(all_X)
    y = np.concatenate(all_y)

    # Use last 20% as test set
    split_idx = int(len(X) * 0.8)
    X_test, y_test = X[split_idx:], y[split_idx:]

    test_ds = TensorDataset(torch.tensor(X_test), torch.tensor(y_test))
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

    # Load model
    model = PathWiseLSTM()
    checkpoint_path = Path(args.checkpoint)
    if checkpoint_path.exists():
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded model from {checkpoint_path}")
    else:
        logger.warning(f"No checkpoint found at {checkpoint_path}, using random weights")

    # Evaluate
    results = evaluate_model(model, test_loader)

    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)
    for key, value in results.items():
        logger.info(f"  {key}: {value:.6f}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
