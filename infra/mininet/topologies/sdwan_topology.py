"""
SD-WAN reference topology for PathWise AI testing.

Topology:
  h1 --- s1 ---[fiber-primary]--- s2 --- h2
              |                    |
              +--[broadband-sec]---+
              |                    |
              +--[satellite-bkp]---+
              |                    |
              +--[5g-mobile]-------+

Each link emulates different WAN characteristics.
"""

from mininet.topo import Topo
from mininet.link import TCLink


class SDWanTopology(Topo):
    """Multi-link SD-WAN topology with differentiated link characteristics."""

    def build(self):
        # Core switches
        s1 = self.addSwitch("s1", dpid="0000000000000001", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", dpid="0000000000000002", protocols="OpenFlow13")

        # Edge hosts
        h1 = self.addHost("h1", ip="10.0.1.1/24")
        h2 = self.addHost("h2", ip="10.0.2.1/24")

        # Host-to-switch links
        self.addLink(h1, s1, bw=1000, delay="1ms", loss=0)
        self.addLink(h2, s2, bw=1000, delay="1ms", loss=0)

        # WAN links with differentiated characteristics
        # Fiber primary: high bandwidth, low latency
        self.addLink(s1, s2, bw=1000, delay="5ms", loss=0.01,
                     params1={"name": "fiber-primary"})

        # Broadband secondary: moderate bandwidth, moderate latency
        self.addLink(s1, s2, bw=100, delay="15ms", loss=0.1,
                     params1={"name": "broadband-secondary"})

        # Satellite backup: low bandwidth, high latency
        self.addLink(s1, s2, bw=10, delay="300ms", loss=0.5,
                     params1={"name": "satellite-backup"})

        # 5G mobile: moderate bandwidth, variable latency
        self.addLink(s1, s2, bw=200, delay="20ms", loss=0.2,
                     params1={"name": "5g-mobile"})


topos = {"sdwan": SDWanTopology}
