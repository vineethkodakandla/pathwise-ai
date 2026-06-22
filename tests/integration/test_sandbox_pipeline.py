# tests/integration/test_sandbox_pipeline.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "digital-twin"))

import pytest
from twin_manager import DigitalTwinManager, ValidationResult, SandboxReport


class TestSandboxPipeline:
    """
    Integration tests for the Digital Twin validation pipeline.

    Note: Full Mininet/Batfish tests require privileged Docker containers.
    These tests validate the orchestration logic and data flow.
    """

    def test_validation_result_enum(self):
        """All expected validation results should exist."""
        assert ValidationResult.PASS.value == "pass"
        assert ValidationResult.FAIL_LOOP_DETECTED.value == "fail_loop"
        assert ValidationResult.FAIL_POLICY_VIOLATION.value == "fail_policy"
        assert ValidationResult.FAIL_UNREACHABLE.value == "fail_unreachable"
        assert ValidationResult.FAIL_TIMEOUT.value == "fail_timeout"

    def test_sandbox_report_structure(self):
        """SandboxReport should store all validation fields."""
        report = SandboxReport(
            result=ValidationResult.PASS,
            details="All validations passed",
            loop_free=True,
            policy_compliant=True,
            reachability_verified=True,
            execution_time_ms=1234.5,
            topology_snapshot={"switches": []},
        )
        assert report.result == ValidationResult.PASS
        assert report.loop_free is True
        assert report.execution_time_ms == 1234.5
        assert report.topology_snapshot is not None

    def test_twin_manager_initialization(self):
        """DigitalTwinManager should initialize without errors."""
        # This may fail if mininet/batfish aren't importable,
        # which is expected in CI without those dependencies
        try:
            twin = DigitalTwinManager()
            assert twin.topology_builder is not None
            assert twin.batfish is not None
        except ImportError:
            pytest.skip("Mininet/Batfish not available in this environment")

    def test_generate_proposed_flows(self, sample_topology):
        """Proposed flow generation should add new flows."""
        try:
            twin = DigitalTwinManager()

            class MockDecision:
                source_link = "broadband-secondary"
                target_link = "fiber-primary"
                traffic_classes = ["voip", "video"]

            current_flows = [
                {"switch_id": "s1", "priority": 100,
                 "match": "ip", "actions": "output:2"},
            ]

            proposed = twin._generate_proposed_flows(MockDecision(), current_flows)
            assert len(proposed) > len(current_flows)
        except ImportError:
            pytest.skip("Mininet/Batfish not available in this environment")

    def test_link_to_port_mapping(self):
        """Port mapping should cover all standard link types."""
        try:
            twin = DigitalTwinManager()
            assert twin._link_to_port("fiber-primary") == 1
            assert twin._link_to_port("broadband-secondary") == 2
            assert twin._link_to_port("satellite-backup") == 3
            assert twin._link_to_port("5g-mobile") == 4
        except ImportError:
            pytest.skip("Mininet/Batfish not available in this environment")
