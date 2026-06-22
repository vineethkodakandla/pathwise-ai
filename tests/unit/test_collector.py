# tests/unit/test_collector.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "telemetry-ingestion"))

import pytest
from collector import TelemetryCollector, TelemetryPoint


class TestTelemetryPoint:
    def test_dataclass_fields(self):
        """TelemetryPoint should store all required fields."""
        point = TelemetryPoint(
            timestamp=1706000000.0,
            link_id="fiber-primary",
            latency_ms=15.5,
            jitter_ms=2.3,
            packet_loss_pct=0.01,
            bandwidth_utilization_pct=45.0,
            rtt_ms=31.0,
        )
        assert point.link_id == "fiber-primary"
        assert point.latency_ms == 15.5
        assert point.latency_rolling_mean_30s is None  # Optional

    def test_optional_fields_default_none(self):
        """Optional derived fields should default to None."""
        point = TelemetryPoint(
            timestamp=0, link_id="test", latency_ms=0,
            jitter_ms=0, packet_loss_pct=0,
            bandwidth_utilization_pct=0, rtt_ms=0,
        )
        assert point.latency_rolling_mean_30s is None
        assert point.jitter_ema_alpha05 is None
        assert point.packet_loss_rate_of_change is None


class TestTelemetryCollector:
    def test_synthetic_mode_returns_telemetry_point(self):
        """Synthetic collection should return a valid TelemetryPoint."""
        collector = TelemetryCollector(
            redis_url="redis://localhost:6379",
            mode="synthetic",
        )
        point = collector._collect_synthetic("10.0.1.1")
        assert isinstance(point, TelemetryPoint)
        assert point.link_id == "10.0.1.1"
        assert point.latency_ms >= 0
        assert point.jitter_ms >= 0
        assert 0 <= point.packet_loss_pct <= 100
        assert 0 <= point.bandwidth_utilization_pct <= 100

    def test_synthetic_mode_consistent_state(self):
        """Synthetic mode should maintain per-device state."""
        collector = TelemetryCollector(
            redis_url="redis://localhost:6379",
            mode="synthetic",
        )
        p1 = collector._collect_synthetic("device-a")
        p2 = collector._collect_synthetic("device-a")
        # Both should have the same link_id and reasonable values
        assert p1.link_id == p2.link_id == "device-a"
        assert abs(p1.latency_ms - p2.latency_ms) < 100  # Not wildly different

    def test_synthetic_mode_different_devices(self):
        """Different devices should have independent states."""
        collector = TelemetryCollector(
            redis_url="redis://localhost:6379",
            mode="synthetic",
        )
        p1 = collector._collect_synthetic("device-a")
        p2 = collector._collect_synthetic("device-b")
        assert p1.link_id != p2.link_id
