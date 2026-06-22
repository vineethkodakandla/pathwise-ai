# services/traffic-steering/sdn_clients/base.py

from abc import ABC, abstractmethod
from typing import Optional


class SDNClientBase(ABC):
    """
    Abstract base class for SDN controller integrations.

    All SDN clients must implement:
    - install_flow_rules(): Make-before-break flow installation
    - get_topology(): Fetch current network topology
    - get_flow_statistics(): Retrieve flow stats from a node

    This abstraction allows PathWise to swap between OpenDaylight and ONOS
    without changing the steering engine logic.
    """

    @abstractmethod
    async def install_flow_rules(
        self,
        source_link: str,
        target_link: str,
        traffic_classes: list[str],
        strategy: str = "make-before-break",
    ) -> bool:
        """
        Install flow rules to steer traffic from source_link to target_link.

        The make-before-break strategy:
        1. Install new higher-priority flows on the target link
        2. Verify new flows are active (receiving packets)
        3. Remove old flows on the source link

        Returns True if all steps succeed.
        """
        ...

    @abstractmethod
    async def get_topology(self) -> dict:
        """Fetch the current network topology from the SDN controller."""
        ...

    @abstractmethod
    async def get_flow_statistics(self, node_id: str = "openflow:1") -> dict:
        """Retrieve flow statistics for a given switch/node."""
        ...

    def _link_to_port(self, link_id: str) -> int:
        """Map a logical link ID to a physical switch port number."""
        port_map = {
            "fiber-primary": 1,
            "broadband-secondary": 2,
            "satellite-backup": 3,
            "5g-mobile": 4,
        }
        return port_map.get(link_id, 1)
