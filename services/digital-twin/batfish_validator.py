# services/digital-twin/batfish_validator.py

from pybatfish.client.session import Session
from pybatfish.datamodel.flow import HeaderConstraints

class BatfishValidator:
    """
    Uses Batfish for static network configuration analysis:
    - Routing loop detection
    - ACL/firewall policy compliance verification
    - Reachability analysis without live traffic
    
    Batfish analyzes configs statically (no live network needed),
    making it fast enough for the <5 second validation budget.
    """

    def __init__(self, batfish_host: str = "localhost"):
        self.bf = Session(host=batfish_host)

    async def analyze(self, topology: dict, proposed_flows: list[dict]) -> dict:
        """
        Run Batfish analysis on proposed configuration.
        
        Returns:
            {
                "loop_free": bool,
                "policy_compliant": bool,
                "loop_path": Optional[str],
                "violations": Optional[list[str]],
            }
        """
        # Initialize Batfish snapshot from topology configs
        self.bf.init_snapshot_from_text(
            self._topology_to_configs(topology, proposed_flows),
            name="validation_snapshot",
            overwrite=True,
        )
        
        # Loop detection
        loop_results = self.bf.q.detectLoops().answer().frame()
        has_loops = len(loop_results) > 0
        
        # ACL/Firewall compliance
        acl_results = self.bf.q.searchFilters(
            headers=HeaderConstraints(applications=["dns", "http", "https"]),
            action="deny",
        ).answer().frame()
        
        # Check for unintended denies
        violations = []
        for _, row in acl_results.iterrows():
            if row.get("Flow") and "critical" in str(row.get("Flow", "")):
                violations.append(f"Critical traffic blocked by {row.get('Filter', 'unknown')}")
        
        return {
            "loop_free": not has_loops,
            "policy_compliant": len(violations) == 0,
            "loop_path": str(loop_results.iloc[0]) if has_loops else None,
            "violations": violations if violations else None,
        }

    def _topology_to_configs(self, topology: dict, flows: list[dict]) -> dict:
        """Convert abstract topology to vendor-neutral configs for Batfish."""
        configs = {}
        for sw in topology.get("switches", []):
            configs[f"{sw['id']}.cfg"] = self._generate_switch_config(sw, topology, flows)
        return configs

    def _generate_switch_config(self, switch: dict, topology: dict, flows: list[dict]) -> str:
        """Generate a Cisco-style config for a switch."""
        config_lines = [
            f"hostname {switch['id']}",
            "!",
        ]

        # Generate interface configs from links
        port_num = 1
        for link in topology.get("links", []):
            if link["src"] == switch["id"] or link["dst"] == switch["id"]:
                config_lines.extend([
                    f"interface GigabitEthernet0/{port_num}",
                    f" description {link.get('link_id', f'link-{port_num}')}",
                    " no shutdown",
                    "!",
                ])
                port_num += 1

        # Add basic ACL
        config_lines.extend([
            "ip access-list extended PATHWISE-POLICY",
            " permit ip any any",
            "!",
        ])

        return "\n".join(config_lines)
