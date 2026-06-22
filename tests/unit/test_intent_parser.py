# tests/unit/test_intent_parser.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api-gateway"))

import pytest
from app.routers.policies import IntentParser

parser = IntentParser()

class TestIntentParser:
    def test_prioritize_voip_over_guest(self):
        rules = parser.parse("Prioritize VoIP over guest WiFi")
        assert len(rules) == 2
        assert rules[0].traffic_class == "voip"
        assert rules[0].priority > rules[1].priority
        assert rules[1].traffic_class == "guest_wifi"

    def test_guarantee_bandwidth(self):
        rules = parser.parse("Guarantee 50 Mbps for video conferencing")
        assert rules[0].bandwidth_guarantee_mbps == 50.0
        assert rules[0].traffic_class == "video"

    def test_invalid_intent_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parser.parse("Make the network go brrr")

    def test_case_insensitive(self):
        rules = parser.parse("PRIORITIZE MEDICAL IMAGING OVER GUEST WIFI")
        assert rules[0].traffic_class == "medical_imaging"

    def test_block_intent(self):
        rules = parser.parse("Block streaming on satellite-backup")
        assert len(rules) == 1
        assert rules[0].action == "block"
        assert rules[0].traffic_class == "streaming"
        assert "satellite-backup" in rules[0].target_links

    def test_redirect_intent(self):
        rules = parser.parse("Redirect backup traffic to broadband-secondary")
        assert len(rules) == 1
        assert rules[0].action == "redirect"
        assert rules[0].traffic_class == "backup"

    def test_max_latency_intent(self):
        rules = parser.parse("Set max latency for VoIP to 20ms")
        assert len(rules) == 1
        assert rules[0].latency_max_ms == 20.0
        assert rules[0].traffic_class == "voip"

    def test_limit_bandwidth_intent(self):
        rules = parser.parse("Limit guest wifi to 10 Mbps")
        assert len(rules) == 1
        assert rules[0].traffic_class == "guest_wifi"
        assert rules[0].action == "throttle"
