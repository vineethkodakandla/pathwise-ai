# services/prediction-engine/model/trainer.py

import torch
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
import logging

from .lstm_network import PathWiseLoss

logger = logging.getLogger(__name__)

class LSTMTrainer:
    """
    Training configuration optimized for network telemetry:
    - AdamW optimizer (better weight decay for time-series)
    - ReduceLROnPlateau scheduler (adapts to loss plateaus)
    - Early stopping with patience=10
    - Model checkpointing (best val loss)
    """

    def __init__(
        self,
        model: "PathWiseLSTM",
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        batch_size: int = 256,
        max_epochs: int = 100,
        patience: int = 10,
        checkpoint_dir: str = "./checkpoints",
    ):
        self.model = model
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=lr, weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5
        )
        self.criterion = PathWiseLoss()

    def train(self, X_train, y_train, X_val, y_val) -> dict:
        train_ds = TensorDataset(
            torch.tensor(X_train), torch.tensor(y_train)
        )
        val_ds = TensorDataset(
            torch.tensor(X_val), torch.tensor(y_val)
        )
        train_loader = DataLoader(
            train_ds, batch_size=self.batch_size, shuffle=True, drop_last=True
        )
        val_loader = DataLoader(
            val_ds, batch_size=self.batch_size, shuffle=False
        )
        
        best_val_loss = float("inf")
        epochs_no_improve = 0
        history = {"train_loss": [], "val_loss": []}
        
        for epoch in range(self.max_epochs):
            # --- Training ---
            self.model.train()
            train_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                self.optimizer.zero_grad()
                preds, confidence = self.model(X_batch)
                loss = self.criterion(preds, y_batch, confidence=confidence)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            
            # --- Validation ---
            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)
                    preds, conf = self.model(X_batch)
                    loss = self.criterion(preds, y_batch, confidence=conf)
                    val_loss += loss.item()
            val_loss /= len(val_loader)
            
            self.scheduler.step(val_loss)
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            
            logger.info(
                f"Epoch {epoch+1}/{self.max_epochs} | "
                f"Train: {train_loss:.6f} | Val: {val_loss:.6f} | "
                f"LR: {self.optimizer.param_groups[0]['lr']:.2e}"
            )
            
            # Checkpoint best model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                epochs_no_improve = 0
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": self.model.state_dict(),
                    "optimizer_state_dict": self.optimizer.state_dict(),
                    "val_loss": val_loss,
                }, self.checkpoint_dir / "best_model.pt")
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= self.patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break
        
        return history
