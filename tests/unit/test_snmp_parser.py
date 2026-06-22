# tests/unit/test_snmp_parser.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "telemetry-ingestion"))

import pytest
from parsers.snmp_parser import SNMPParser


class TestSNMPParser:
    def test_first_poll_returns_none(self):
        """First poll has no previous counters, so returns None."""
        parser = SNMPParser()
        result = parser.parse_counters("device1", 1, {
            "ifInOctets": 1000,
            "ifOutOctets": 2000,
            "ifInErrors": 0,
            "ifInDiscards": 0,
            "ifSpeed": 1_000_000_000,
        })
        assert result is None

    def test_second_poll_returns_metrics(self):
        """Second poll should compute rate-based metrics."""
        parser = SNMPParser()
        # First poll
        parser.parse_counters("device1", 1, {
            "ifInOctets": 1000,
            "ifOutOctets": 2000,
            "ifInErrors": 0,
            "ifInDiscards": 0,
            "ifSpeed": 1_000_000_000,
        })

        import time
        time.sleep(0.01)  # Small delay for timestamp difference

        # Second poll with increased counters
        result = parser.parse_counters("device1", 1, {
            "ifInOctets": 2000,
            "ifOutOctets": 3000,
            "ifInErrors": 0,
            "ifInDiscards": 0,
            "ifSpeed": 1_000_000_000,
        })

        assert result is not None
        assert "bandwidth_util_pct" in result
        assert "packet_loss_pct" in result
        assert result["bandwidth_util_pct"] >= 0
        assert result["packet_loss_pct"] >= 0

    def test_counter_wrap_handling(self):
        """32-bit counter wraps should be handled correctly."""
        parser = SNMPParser()
        parser.parse_counters("device1", 1, {
            "ifInOctets": 2**32 - 1000,
            "ifOutOctets": 0,
            "ifInErrors": 0,
            "ifInDiscards": 0,
            "ifSpeed": 1_000_000_000,
        })

        import time
        time.sleep(0.01)

        result = parser.parse_counters("device1", 1, {
            "ifInOctets": 1000,  # Wrapped around
            "ifOutOctets": 0,
            "ifInErrors": 0,
            "ifInDiscards": 0,
            "ifSpeed": 1_000_000_000,
        })

        assert result is not None
        assert result["bandwidth_util_pct"] >= 0

    def test_packet_loss_from_errors(self):
        """Packet loss should increase when errors increase."""
        parser = SNMPParser()
        parser.parse_counters("device1", 1, {
            "ifInOctets": 100000,
            "ifOutOctets": 100000,
            "ifInErrors": 0,
            "ifInDiscards": 0,
            "ifSpeed": 1_000_000_000,
        })

        import time
        time.sleep(0.01)

        result = parser.parse_counters("device1", 1, {
            "ifInOctets": 200000,
            "ifOutOctets": 200000,
            "ifInErrors": 100,
            "ifInDiscards": 50,
            "ifSpeed": 1_000_000_000,
        })

        assert result is not None
        assert result["packet_loss_pct"] > 0
