"""Quick verification that the trained checkpoint loads correctly."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "prediction-engine"))

import torch
import numpy as np
from model.lstm_network import PathWiseLSTM

ckpt_path = PROJECT_ROOT / "ml" / "checkpoints" / "best_model.pt"
print(f"Checkpoint: {ckpt_path}")
print(f"Exists: {ckpt_path.exists()}")

data = torch.load(ckpt_path, map_location="cpu", weights_only=False)
print(f"Keys: {list(data.keys())}")
print(f"Epoch: {data['epoch']}, Val loss: {data['val_loss']:.4f}")

model = PathWiseLSTM(input_size=13, hidden_size=128, num_layers=2)
model.load_state_dict(data["model_state_dict"])
model.eval()
print("Model loaded successfully!")

# Test inference with random input (batch=1, seq_len=60, features=13)
x = torch.randn(1, 60, 13)
with torch.no_grad():
    preds, confidence = model(x)

print(f"\nTest inference:")
print(f"  Latency forecast shape: {preds['latency'].shape}")
print(f"  Jitter forecast shape:  {preds['jitter'].shape}")
print(f"  Packet loss shape:      {preds['packet_loss'].shape}")
print(f"  Confidence: {confidence.item():.4f}")
print(f"  Latency[0:5]: {preds['latency'][0,:5].tolist()}")
print(f"  Jitter[0:5]:  {preds['jitter'][0,:5].tolist()}")

print("\nAll checks passed!")
