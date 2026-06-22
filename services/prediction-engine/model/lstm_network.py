# services/prediction-engine/model/lstm_network.py

import torch
import torch.nn as nn

class PathWiseLSTM(nn.Module):
    """
    Multi-output LSTM for network telemetry forecasting.
    
    Architecture rationale:
    - 2-layer stacked LSTM: captures both short-term jitter patterns
      and longer-term degradation trends without excessive depth.
    - Dropout between layers: regularization critical for small datasets
      (initial 30 days ~ 2.6M points per link, but correlated).
    - Attention mechanism: lets the model focus on critical moments
      (e.g., sudden latency spikes) within the 60-step window.
    - Separate prediction heads for latency, jitter, and packet_loss
      to allow different optimization dynamics per metric.
    """
    
    def __init__(
        self,
        input_size: int = 13,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2,
        horizon: int = 30,
        num_targets: int = 3,
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.horizon = horizon
        
        # Core LSTM encoder
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        
        # Temporal attention over LSTM outputs
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )
        
        # Prediction heads — one per target metric
        self.latency_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )
        self.jitter_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )
        self.packet_loss_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )
        
        # Confidence estimation head (used by Health Scoreboard)
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),  # Output in [0, 1]
        )

    def forward(self, x: torch.Tensor):
        """
        Args:
            x: (batch, seq_len=60, features=13)
        Returns:
            predictions: dict with keys 'latency', 'jitter', 'packet_loss'
                         each of shape (batch, horizon)
            confidence:  (batch, 1)  — model's self-assessed prediction quality
        """
        # LSTM encoding
        lstm_out, (h_n, _) = self.lstm(x)  # lstm_out: (batch, 60, 128)
        
        # Attention: weighted sum of all timestep outputs
        attn_weights = self.attention(lstm_out)          # (batch, 60, 1)
        attn_weights = torch.softmax(attn_weights, dim=1)
        context = (lstm_out * attn_weights).sum(dim=1)   # (batch, 128)
        
        # Predictions
        predictions = {
            "latency": self.latency_head(context),       # (batch, 30)
            "jitter": self.jitter_head(context),
            "packet_loss": self.packet_loss_head(context),
        }
        confidence = self.confidence_head(context)        # (batch, 1)
        
        return predictions, confidence


class PathWiseLoss(nn.Module):
    """
    Composite loss function:
    - Weighted MSE for each target (packet_loss weighted higher because
      even small prediction errors there have outsized business impact)
    - Penalty term for underestimating degradation (asymmetric loss):
      missing a real brownout is much worse than a false positive.
    """

    def __init__(
        self,
        weights: dict = None,
        underestimate_penalty: float = 2.0,
        confidence_weight: float = 0.5,
    ):
        super().__init__()
        self.weights = weights or {"latency": 1.0, "jitter": 1.0, "packet_loss": 2.0}
        self.penalty = underestimate_penalty
        self.confidence_weight = confidence_weight

    def forward(self, preds: dict, targets: torch.Tensor,
                confidence: torch.Tensor | None = None):
        """
        targets: (batch, horizon, 3) — latency, jitter, packet_loss
        confidence: (batch, 1) — optional, model's self-assessed prediction quality.
            When provided, a supervised confidence loss is added so the
            confidence head actually trains (otherwise its sigmoid output is
            unlearned noise — Req-Func-Sw-14 would be meaningless).
        """
        total_loss = 0.0
        target_map = {
            "latency": targets[:, :, 0],
            "jitter": targets[:, :, 1],
            "packet_loss": targets[:, :, 2],
        }

        per_sample_errors = []
        for key, weight in self.weights.items():
            pred = preds[key]
            target = target_map[key]
            error = pred - target

            # Asymmetric MSE: penalize underestimates more
            mse = error ** 2
            underestimate_mask = (error < 0).float()  # pred < actual = missed degradation
            asymmetric_mse = mse * (1 + underestimate_mask * (self.penalty - 1))

            total_loss += weight * asymmetric_mse.mean()
            per_sample_errors.append(mse.mean(dim=-1))  # (batch,)

        if confidence is not None:
            # Target confidence = exp(-mean_error). Low error → high confidence,
            # high error → low confidence. Stop gradient on the target so the
            # confidence head learns to predict quality, rather than the
            # predictor degrading itself to be predictable.
            mean_err = torch.stack(per_sample_errors, dim=-1).mean(dim=-1)  # (batch,)
            target_conf = torch.exp(-mean_err).detach().unsqueeze(-1)       # (batch, 1)
            conf_loss = ((confidence - target_conf) ** 2).mean()
            total_loss = total_loss + self.confidence_weight * conf_loss

        return total_loss
