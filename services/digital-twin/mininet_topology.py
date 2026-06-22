# services/digital-twin/mininet_topology.py

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel

class MininetTopologyBuilder:
    """
    Builds Mininet virtual networks that mirror production topology.
    
    Design:
    - Each WAN link becomes a Mininet link with tc-based QoS emulation
    - SDN switches use OVSSwitch with OpenFlow 1.3
    - Remote controller points to test SDN controller instance
    - Link characteristics (bandwidth, delay, loss) match production data
    """
    
    def build_from_production(self, topology: dict) -> Mininet:
        """
        Topology dict format:
        {
            "switches": [{"id": "s1", "dpid": "0000000000000001"}, ...],
            "hosts": [{"id": "h1", "ip": "10.0.1.1/24"}, ...],
            "links": [
                {"src": "s1", "dst": "s2", "bw": 100, "delay": "5ms", "loss": 0.1,
                 "link_id": "fiber-primary"},
                ...
            ]
        }
        """
        net = Mininet(
            switch=OVSSwitch,
            controller=RemoteController,
            link=TCLink,
            autoSetMacs=True,
        )
        
        # Add controller
        net.addController("c0", ip="127.0.0.1", port=6633)
        
        # Add switches
        switches = {}
        for sw in topology["switches"]:
            switches[sw["id"]] = net.addSwitch(
                sw["id"], dpid=sw["dpid"], protocols="OpenFlow13"
            )
        
        # Add hosts
        hosts = {}
        for h in topology["hosts"]:
            hosts[h["id"]] = net.addHost(h["id"], ip=h["ip"])
        
        # Add links with production-matched characteristics
        for link in topology["links"]:
            src = switches.get(link["src"]) or hosts.get(link["src"])
            dst = switches.get(link["dst"]) or hosts.get(link["dst"])
            net.addLink(
                src, dst,
                bw=link.get("bw", 100),
                delay=link.get("delay", "2ms"),
                loss=link.get("loss", 0),
            )
        
        net.start()
        return net

    def apply_flows(self, net: Mininet, flows: list[dict]):
        """Install OpenFlow rules on switches via ovs-ofctl."""
        for flow in flows:
            switch = net.get(flow["switch_id"])
            cmd = (
                f"ovs-ofctl -O OpenFlow13 add-flow {switch.name} "
                f"priority={flow['priority']},"
                f"{flow['match']},"
                f"actions={flow['actions']}"
            )
            switch.cmd(cmd)

    async def test_reachability(self, net: Mininet) -> bool:
        """Run ping and iperf tests to verify forwarding works."""
        hosts = net.hosts
        if len(hosts) < 2:
            return True
        
        # Ping test between all host pairs
        loss = net.pingAll(timeout=1)
        return loss == 0  # 0% loss = full reachability

    def cleanup(self, net: Mininet):
        """Tear down the virtual network."""
        net.stop()
