"""Tests for server.app_qos.bandwidth_enforcer — allocation and enforcement."""

import os

# Force simulate mode before any imports touch the module
os.environ["ENFORCER_MODE"] = "simulate"
os.environ["TOTAL_LINK_MBPS"] = "100"

import pytest
from server.app_qos.bandwidth_enforcer import BandwidthEnforcer
from server.app_qos.signatures import predict_quality


class TestAllocation:
    def setup_method(self):
        self.enforcer = BandwidthEnforcer()

    def test_zoom_high_youtube_low(self):
        result = self.enforcer.apply_priorities(
            {"zoom": "HIGH", "youtube": "LOW"}, total_mbps=100,
        )
        assert result["zoom"]["allocated_mbps"] >= 50
        assert result["youtube"]["allocated_mbps"] <= 10

    def test_youtube_quality_drops_when_throttled(self):
        result = self.enforcer.apply_priorities(
            {"youtube": "LOW"}, total_mbps=100,
        )
        yt = result["youtube"]
        quality = yt["quality"]
        # LOW = 5% of 100 = 5 Mbps => 720p at best
        assert quality["score"] <= 80  # not 4K quality

    def test_blocked_gets_zero(self):
        result = self.enforcer.apply_priorities(
            {"steam": "BLOCKED"}, total_mbps=100,
        )
        assert result["steam"]["allocated_mbps"] == 0.0
        assert result["steam"]["quality"]["score"] == 0 or "Below" in result["steam"]["quality"]["label"]

    def test_critical_gets_90_plus_percent(self):
        result = self.enforcer.apply_priorities(
            {"zoom": "CRITICAL"}, total_mbps=100,
        )
        assert result["zoom"]["allocated_mbps"] >= 90.0

    def test_clear_rules(self):
        self.enforcer.apply_priorities({"zoom": "HIGH"}, total_mbps=100)
        cleared = self.enforcer.clear_all_rules()
        assert cleared["status"] == "cleared"
        assert self.enforcer.get_active_allocations() == {}

    def test_multi_app_does_not_exceed_total(self):
        result = self.enforcer.apply_priorities(
            {
                "zoom": "HIGH",
                "youtube": "NORMAL",
                "netflix": "NORMAL",
                "steam": "LOW",
            },
            total_mbps=100,
        )
        total = sum(a["allocated_mbps"] for a in result.values())
        assert total <= 100.0 + 0.01  # float rounding tolerance
