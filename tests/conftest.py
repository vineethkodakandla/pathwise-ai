# tests/conftest.py

import sys
import os
from pathlib import Path
import pytest

# Add project root and service directories to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "prediction-engine"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "traffic-steering"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "digital-twin"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "telemetry-ingestion"))


@pytest.fixture
def redis_url():
    """Redis URL from environment or localhost default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest.fixture
def database_url():
    """Database URL from environment or localhost default."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://pathwise:pathwise_dev@localhost:5432/pathwise",
    )


@pytest.fixture
def sample_topology():
    """Reference SD-WAN topology for testing."""
    return {
        "switches": [
            {"id": "s1", "dpid": "0000000000000001"},
            {"id": "s2", "dpid": "0000000000000002"},
        ],
        "hosts": [
            {"id": "h1", "ip": "10.0.1.1/24"},
            {"id": "h2", "ip": "10.0.2.1/24"},
        ],
        "links": [
            {"src": "h1", "dst": "s1", "bw": 1000, "delay": "1ms", "loss": 0,
             "link_id": "host-link-1"},
            {"src": "h2", "dst": "s2", "bw": 1000, "delay": "1ms", "loss": 0,
             "link_id": "host-link-2"},
            {"src": "s1", "dst": "s2", "bw": 1000, "delay": "5ms", "loss": 0.01,
             "link_id": "fiber-primary"},
            {"src": "s1", "dst": "s2", "bw": 100, "delay": "15ms", "loss": 0.1,
             "link_id": "broadband-secondary"},
            {"src": "s1", "dst": "s2", "bw": 10, "delay": "300ms", "loss": 0.5,
             "link_id": "satellite-backup"},
            {"src": "s1", "dst": "s2", "bw": 200, "delay": "20ms", "loss": 0.2,
             "link_id": "5g-mobile"},
        ],
    }


@pytest.fixture
def sample_telemetry_df():
    """Generate a small DataFrame of telemetry data for testing."""
    import numpy as np
    import pandas as pd

    n = 200
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="1s"),
        "link_id": "test-link",
        "latency_ms": np.random.uniform(10, 50, n),
        "jitter_ms": np.random.uniform(1, 10, n),
        "packet_loss_pct": np.random.uniform(0, 2, n),
        "bandwidth_util_pct": np.random.uniform(20, 80, n),
        "rtt_ms": np.random.uniform(20, 100, n),
    })
