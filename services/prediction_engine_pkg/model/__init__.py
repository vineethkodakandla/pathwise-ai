# Re-export from actual prediction-engine service
import sys
from pathlib import Path

_engine_path = str(Path(__file__).resolve().parents[2] / "prediction-engine")
if _engine_path not in sys.path:
    sys.path.insert(0, _engine_path)
