# tests/unit/test_steering_engine.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "traffic-steering"))

import pytest
from steering_engine import SteeringAction, SteeringDecision, SteeringEngine


class TestSteeringDecision:
    def test_emergency_failover_fields(self):
        """Emergency failover decision should have correct structure."""
        decision = SteeringDecision(
            action=SteeringAction.EMERGENCY_FAILOVER,
            source_link="satellite-backup",
            target_link="fiber-primary",
            traffic_classes=["voip", "video", "critical", "bulk"],
            confidence=0.95,
            reason="Link health critical (25)",
            requires_sandbox_validation=False,
        )
        assert decision.action == SteeringAction.EMERGENCY_FAILOVER
        assert decision.requires_sandbox_validation is False
        assert len(decision.traffic_classes) == 4

    def test_preemptive_shift_requires_validation(self):
        """Preemptive shifts must require sandbox validation."""
        decision = SteeringDecision(
            action=SteeringAction.PREEMPTIVE_SHIFT,
            source_link="broadband-secondary",
            target_link="fiber-primary",
            traffic_classes=["voip", "video"],
            confidence=0.8,
            reason="Predicted degradation",
            requires_sandbox_validation=True,
        )
        assert decision.requires_sandbox_validation is True

    def test_steering_action_values(self):
        """Verify all steering action enum values."""
        assert SteeringAction.HOLD.value == "hold"
        assert SteeringAction.PREEMPTIVE_SHIFT.value == "shift"
        assert SteeringAction.EMERGENCY_FAILOVER.value == "failover"
        assert SteeringAction.REBALANCE.value == "rebalance"


class TestSteeringEngineThresholds:
    def test_critical_threshold(self):
        """Critical threshold should be 30."""
        assert SteeringEngine.CRITICAL_THRESHOLD == 30

    def test_warning_threshold(self):
        """Warning threshold should be 50."""
        assert SteeringEngine.WARNING_THRESHOLD == 50

    def test_confidence_threshold(self):
        """Confidence threshold should be 0.7."""
        assert SteeringEngine.CONFIDENCE_THRESHOLD == 0.7
