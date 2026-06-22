# ml/scripts/train.py

import sys
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.prediction_engine_pkg.model.lstm_network import PathWiseLSTM
from services.prediction_engine_pkg.model.feature_engineering import FeatureEngineer
from services.prediction_engine_pkg.model.trainer import LSTMTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_data(data_dir: str) -> pd.DataFrame:
    """Load all parquet files from the data directory."""
    data_path = Path(data_dir)
    dfs = []
    for f in sorted(data_path.glob("*.parquet")):
        df = pd.read_parquet(f)
        logger.info(f"Loaded {len(df):,} rows from {f.name}")
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError(f"No parquet files found in {data_dir}")
    return pd.concat(dfs, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Train PathWise LSTM model")
    parser.add_argument("--data-dir", type=str, default="ml/data/synthetic")
    parser.add_argument("--checkpoint-dir", type=str, default="ml/checkpoints")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--smoke-test", action="store_true",
                        help="Quick training with reduced data for CI")
    args = parser.parse_args()

    # Load data
    logger.info("Loading data...")
    df = load_data(args.data_dir)

    if args.smoke_test:
        # Use only first 5000 rows per link for smoke test
        df = df.groupby("link_id").head(5000).reset_index(drop=True)
        logger.info(f"Smoke test: reduced to {len(df):,} rows")

    # Feature engineering
    logger.info("Computing features...")
    fe = FeatureEngineer()
    all_X, all_y = [], []

    for link_id, link_df in df.groupby("link_id"):
        link_df = fe.compute_features(link_df)
        X, y = fe.create_sequences(link_df)
        if len(X) > 0:
            X = fe.normalize(X, link_id, fit=True)
            all_X.append(X)
            all_y.append(y)
            logger.info(f"  {link_id}: {len(X)} sequences")

    X = np.concatenate(all_X)
    y = np.concatenate(all_y)

    # Train/validation split (80/20, chronological)
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Validation set: {len(X_val)} samples")

    # Initialize model
    model = PathWiseLSTM(
        input_size=FeatureEngineer.NUM_FEATURES,
        hidden_size=128,
        num_layers=2,
        dropout=0.2,
        horizon=FeatureEngineer.HORIZON,
    )

    # Train
    trainer = LSTMTrainer(
        model=model,
        lr=args.lr,
        batch_size=args.batch_size,
        max_epochs=args.epochs,
        patience=10,
        checkpoint_dir=args.checkpoint_dir,
    )

    logger.info("Starting training...")
    history = trainer.train(X_train, y_train, X_val, y_val)

    logger.info(f"Training complete. Best val loss: {min(history['val_loss']):.6f}")
    logger.info(f"Model saved to {args.checkpoint_dir}/best_model.pt")


if __name__ == "__main__":
    main()
