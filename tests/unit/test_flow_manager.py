# tests/unit/test_flow_manager.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "traffic-steering"))

import pytest
from sdn_clients.opendaylight import OpenDaylightClient
from sdn_clients.onos import ONOSClient
from sdn_clients.base import SDNClientBase


class TestSDNClientBase:
    def test_base_class_is_abstract(self):
        """SDNClientBase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SDNClientBase()

    def test_link_to_port_mapping(self):
        """Verify link-to-port mapping works correctly."""
        # Test via a concrete subclass
        client = OpenDaylightClient("http://localhost:8181")
        assert client._link_to_port("fiber-primary") == 1
        assert client._link_to_port("broadband-secondary") == 2
        assert client._link_to_port("satellite-backup") == 3
        assert client._link_to_port("5g-mobile") == 4
        assert client._link_to_port("unknown") == 1  # Default


class TestOpenDaylightClient:
    def test_traffic_class_match_voip(self):
        """VoIP traffic should match on UDP + SIP port."""
        client = OpenDaylightClient("http://localhost:8181")
        match = client._traffic_class_match("voip")
        assert "ip-match" in match
        assert match["ip-match"]["ip-protocol"] == 17  # UDP

    def test_traffic_class_match_video(self):
        """Video traffic should match on DSCP AF41."""
        client = OpenDaylightClient("http://localhost:8181")
        match = client._traffic_class_match("video")
        assert match["ip-match"]["ip-dscp"] == 34

    def test_traffic_class_match_critical(self):
        """Critical traffic should match on DSCP EF."""
        client = OpenDaylightClient("http://localhost:8181")
        match = client._traffic_class_match("critical")
        assert match["ip-match"]["ip-dscp"] == 46

    def test_build_flow_entry_structure(self):
        """Flow entry should have correct OpenDaylight RESTCONF structure."""
        client = OpenDaylightClient("http://localhost:8181")
        flow = client._build_flow_entry(
            match={"ethernet-match": {"ethernet-type": {"type": 2048}}},
            output_port=1,
            priority=200,
            flow_id="test-flow",
        )
        assert "flow-node-inventory:flow" in flow
        assert flow["flow-node-inventory:flow"][0]["id"] == "test-flow"
        assert flow["flow-node-inventory:flow"][0]["priority"] == 200


class TestONOSClient:
    def test_traffic_class_selector_voip(self):
        """VoIP selector should include ETH_TYPE and IP_PROTO."""
        client = ONOSClient("http://localhost:8181")
        selector = client._traffic_class_selector("voip")
        types = [c["type"] for c in selector]
        assert "ETH_TYPE" in types
        assert "IP_PROTO" in types

    def test_build_onos_flow_structure(self):
        """ONOS flow should have required fields."""
        client = ONOSClient("http://localhost:8181")
        flow = client._build_onos_flow(
            device_id="of:0000000000000001",
            traffic_class="bulk",
            output_port=1,
            priority=100,
        )
        assert flow["deviceId"] == "of:0000000000000001"
        assert flow["priority"] == 100
        assert flow["isPermanent"] is True
        assert "treatment" in flow
        assert "selector" in flow
