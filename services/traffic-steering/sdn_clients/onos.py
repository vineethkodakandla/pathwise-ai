# services/traffic-steering/sdn_clients/onos.py

import httpx
from typing import Optional


class ONOSClient:
    """
    Integration with ONOS SDN Controller via REST API.

    ONOS API endpoints:
    - GET /onos/v1/flows/{deviceId}
    - POST /onos/v1/flows/{deviceId}
    - DELETE /onos/v1/flows/{deviceId}/{flowId}
    - GET /onos/v1/topology
    - GET /onos/v1/devices
    - GET /onos/v1/links

    ONOS serves as a backup SDN controller if OpenDaylight is unavailable.
    """

    def __init__(self, base_url: str, username: str = "onos", password: str = "rocks"):
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
        Install flow rules via ONOS REST API using make-before-break strategy.
        """
        device_id = "of:0000000000000001"

        async with httpx.AsyncClient(auth=self.auth) as client:
            # Step 1: Install new flows on target with higher priority
            for tc in traffic_classes:
                flow = self._build_onos_flow(
                    device_id=device_id,
                    traffic_class=tc,
                    output_port=self._link_to_port(target_link),
                    priority=40200,  # Higher than existing
                )
                resp = await client.post(
                    f"{self.base_url}/onos/v1/flows/{device_id}",
                    json=flow,
                    headers=self.headers,
                )
                if resp.status_code not in (200, 201):
                    return False

            # Step 2: Verify new flows are active
            await self._wait_for_flows(client, device_id, target_link, traffic_classes)

            # Step 3: Remove old flows
            for tc in traffic_classes:
                flow_id = f"pathwise-{tc}-{source_link}"
                await client.delete(
                    f"{self.base_url}/onos/v1/flows/{device_id}/{flow_id}",
                    headers=self.headers,
                )

            return True

    async def get_topology(self) -> dict:
        """Fetch current network topology from ONOS."""
        async with httpx.AsyncClient(auth=self.auth) as client:
            resp = await client.get(
                f"{self.base_url}/onos/v1/topology",
                headers=self.headers,
            )
            if resp.status_code == 200:
                return resp.json()
            return {}

    async def get_devices(self) -> list[dict]:
        """List all network devices known to ONOS."""
        async with httpx.AsyncClient(auth=self.auth) as client:
            resp = await client.get(
                f"{self.base_url}/onos/v1/devices",
                headers=self.headers,
            )
            if resp.status_code == 200:
                return resp.json().get("devices", [])
            return []

    async def _wait_for_flows(
        self, client: httpx.AsyncClient, device_id: str,
        target_link: str, traffic_classes: list[str], timeout: float = 5.0
    ):
        """Poll until new flows are installed and have packet counts."""
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            resp = await client.get(
                f"{self.base_url}/onos/v1/flows/{device_id}",
                headers=self.headers,
            )
            if resp.status_code == 200:
                flows = resp.json().get("flows", [])
                installed = sum(
                    1 for f in flows
                    if f.get("state") == "ADDED"
                    and any(tc in f.get("id", "") for tc in traffic_classes)
                )
                if installed >= len(traffic_classes):
                    return True
            await asyncio.sleep(0.5)
        return False

    def _build_onos_flow(
        self, device_id: str, traffic_class: str, output_port: int, priority: int
    ) -> dict:
        """Build an ONOS-compatible flow rule JSON body."""
        selector = self._traffic_class_selector(traffic_class)
        return {
            "priority": priority,
            "timeout": 0,
            "isPermanent": True,
            "deviceId": device_id,
            "treatment": {
                "instructions": [
                    {"type": "OUTPUT", "port": str(output_port)}
                ]
            },
            "selector": {
                "criteria": selector
            },
        }

    def _traffic_class_selector(self, traffic_class: str) -> list[dict]:
        """Map traffic class to ONOS match criteria."""
        selectors = {
            "voip": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IP_PROTO", "protocol": 17},
            ],
            "video": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IP_DSCP", "ipDscp": 34},
            ],
            "critical": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
                {"type": "IP_DSCP", "ipDscp": 46},
            ],
            "bulk": [
                {"type": "ETH_TYPE", "ethType": "0x0800"},
            ],
        }
        return selectors.get(traffic_class, [{"type": "ETH_TYPE", "ethType": "0x0800"}])

    def _link_to_port(self, link_id: str) -> int:
        """Map link ID to ONOS output port number."""
        port_map = {
            "fiber-primary": 1,
            "broadband-secondary": 2,
            "satellite-backup": 3,
            "5g-mobile": 4,
        }
        return port_map.get(link_id, 1)
