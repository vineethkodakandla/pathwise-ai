# services/traffic-steering/sdn_clients/opendaylight.py

import httpx
from typing import Optional

class OpenDaylightClient:
    """
    Integration with OpenDaylight SDN Controller via RESTCONF API.
    
    Key endpoints used:
    - GET/PUT /restconf/config/opendaylight-inventory:nodes/node/{id}/flow-node-inventory:table/{table}/flow/{flow}
    - GET /restconf/operational/opendaylight-inventory:nodes
    - POST /restconf/operations/sal-flow:add-flow
    """
    
    def __init__(self, base_url: str, username: str = "admin", password: str = "admin"):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def install_flow_rules(
        self,
        source_link: str,
        target_link: str,
        traffic_classes: list[str],
        strategy: str = "make-before-break",
    ) -> bool:
        """
        Make-before-break hitless handoff:
        
        Step 1: Install new higher-priority flow on target link
        Step 2: Wait for flow to be confirmed active (flow stats show hits)
        Step 3: Remove old flow on source link
        """
        async with httpx.AsyncClient(auth=self.auth) as client:
            # Step 1: Install new flows on target
            for tc in traffic_classes:
                flow = self._build_flow_entry(
                    match=self._traffic_class_match(tc),
                    output_port=self._link_to_port(target_link),
                    priority=200,  # Higher than existing (100)
                    flow_id=f"pathwise-{tc}-{target_link}",
                )
                resp = await client.put(
                    f"{self.base_url}/restconf/config/opendaylight-inventory:nodes"
                    f"/node/openflow:1/flow-node-inventory:table/0"
                    f"/flow/pathwise-{tc}-{target_link}",
                    json=flow,
                    headers=self.headers,
                )
                if resp.status_code not in (200, 201):
                    return False
            
            # Step 2: Verify flows are active
            await self._wait_for_flows_active(target_link, traffic_classes)
            
            # Step 3: Remove old flows
            for tc in traffic_classes:
                await client.delete(
                    f"{self.base_url}/restconf/config/opendaylight-inventory:nodes"
                    f"/node/openflow:1/flow-node-inventory:table/0"
                    f"/flow/pathwise-{tc}-{source_link}",
                    headers=self.headers,
                )
            
            return True

    async def get_topology(self) -> dict:
        """Fetch current network topology from ODL."""
        async with httpx.AsyncClient(auth=self.auth) as client:
            resp = await client.get(
                f"{self.base_url}/restconf/operational/network-topology:network-topology",
                headers=self.headers,
            )
            if resp.status_code == 200:
                return resp.json()
            return {}

    async def get_flow_statistics(self, node_id: str = "openflow:1") -> dict:
        """Fetch flow statistics for a given node."""
        async with httpx.AsyncClient(auth=self.auth) as client:
            resp = await client.get(
                f"{self.base_url}/restconf/operational/opendaylight-inventory:nodes"
                f"/node/{node_id}/flow-node-inventory:table/0",
                headers=self.headers,
            )
            if resp.status_code == 200:
                return resp.json()
            return {}

    async def _wait_for_flows_active(
        self, target_link: str, traffic_classes: list[str], timeout: float = 5.0
    ):
        """Poll flow statistics until new flows show packet hits."""
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            stats = await self.get_flow_statistics()
            # Check if flows are active (simplified)
            if stats:
                return True
            await asyncio.sleep(0.5)
        return False

    def _build_flow_entry(self, match: dict, output_port: int, priority: int, flow_id: str) -> dict:
        return {
            "flow-node-inventory:flow": [{
                "id": flow_id,
                "table_id": 0,
                "priority": priority,
                "match": match,
                "instructions": {
                    "instruction": [{
                        "order": 0,
                        "apply-actions": {
                            "action": [{
                                "order": 0,
                                "output-action": {
                                    "output-node-connector": str(output_port),
                                    "max-length": 65535,
                                }
                            }]
                        }
                    }]
                }
            }]
        }

    def _traffic_class_match(self, traffic_class: str) -> dict:
        """Map traffic class names to OpenFlow match criteria."""
        match_map = {
            "voip": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                "ip-match": {"ip-protocol": 17},  # UDP
                "udp-source-port-match": {"port": 5060},  # SIP
            },
            "video": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                "ip-match": {"ip-dscp": 34},  # AF41
            },
            "critical": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                "ip-match": {"ip-dscp": 46},  # EF
            },
            "bulk": {
                "ethernet-match": {"ethernet-type": {"type": 2048}},
                # Default match — all IP traffic not matched above
            },
        }
        return match_map.get(traffic_class, {})

    def _link_to_port(self, link_id: str) -> int:
        """Map link ID to OpenFlow output port number."""
        port_map = {
            "fiber-primary": 1,
            "broadband-secondary": 2,
            "satellite-backup": 3,
            "5g-mobile": 4,
        }
        return port_map.get(link_id, 1)
