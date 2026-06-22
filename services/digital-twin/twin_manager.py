# services/digital-twin/twin_manager.py

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from mininet_topology import MininetTopologyBuilder
from batfish_validator import BatfishValidator

class ValidationResult(Enum):
    PASS = "pass"
    FAIL_LOOP_DETECTED = "fail_loop"
    FAIL_POLICY_VIOLATION = "fail_policy"
    FAIL_UNREACHABLE = "fail_unreachable"
    FAIL_TIMEOUT = "fail_timeout"

@dataclass
class SandboxReport:
    result: ValidationResult
    details: str
    loop_free: bool
    policy_compliant: bool
    reachability_verified: bool
    execution_time_ms: float
    topology_snapshot: Optional[dict] = None

class DigitalTwinManager:
    """
    Orchestrates the validation pipeline:
    
    1. Snapshot current production topology
    2. Replicate in Mininet virtual network
    3. Apply proposed routing change
    4. Run Batfish analysis (loop detection, policy compliance)
    5. Run Mininet traffic test (actual packet forwarding)
    6. Return pass/fail with detailed report
    
    Target: Complete validation in <5 seconds (PVD quality requirement).
    """

    def __init__(self):
        self.topology_builder = MininetTopologyBuilder()
        self.batfish = BatfishValidator()
        self._active_sandbox = None

    async def validate_steering_decision(
        self,
        decision: "SteeringDecision",
        current_topology: dict,
        current_flows: list[dict],
    ) -> SandboxReport:
        """Full validation pipeline for a proposed steering change."""
        import time
        start = time.monotonic()
        topo = None
        
        try:
            # Step 1: Build virtual topology matching production
            topo = self.topology_builder.build_from_production(current_topology)
            
            # Step 2: Apply current flow rules
            self.topology_builder.apply_flows(topo, current_flows)
            
            # Step 3: Apply proposed change
            proposed_flows = self._generate_proposed_flows(decision, current_flows)
            self.topology_builder.apply_flows(topo, proposed_flows)
            
            # Step 4: Batfish static analysis
            batfish_result = await self.batfish.analyze(
                topology=current_topology,
                proposed_flows=proposed_flows,
            )
            
            if not batfish_result["loop_free"]:
                return SandboxReport(
                    result=ValidationResult.FAIL_LOOP_DETECTED,
                    details=f"Routing loop detected: {batfish_result['loop_path']}",
                    loop_free=False,
                    policy_compliant=batfish_result.get("policy_compliant", False),
                    reachability_verified=False,
                    execution_time_ms=(time.monotonic() - start) * 1000,
                )
            
            if not batfish_result["policy_compliant"]:
                return SandboxReport(
                    result=ValidationResult.FAIL_POLICY_VIOLATION,
                    details=f"Policy violation: {batfish_result['violations']}",
                    loop_free=True,
                    policy_compliant=False,
                    reachability_verified=False,
                    execution_time_ms=(time.monotonic() - start) * 1000,
                )
            
            # Step 5: Mininet live traffic test
            reachability = await asyncio.wait_for(
                self.topology_builder.test_reachability(topo),
                timeout=3.0,  # 3 second timeout for traffic test
            )
            
            elapsed = (time.monotonic() - start) * 1000
            
            return SandboxReport(
                result=ValidationResult.PASS if reachability else ValidationResult.FAIL_UNREACHABLE,
                details="All validations passed" if reachability else "Reachability test failed",
                loop_free=True,
                policy_compliant=True,
                reachability_verified=reachability,
                execution_time_ms=elapsed,
                topology_snapshot=current_topology,
            )
        
        except asyncio.TimeoutError:
            return SandboxReport(
                result=ValidationResult.FAIL_TIMEOUT,
                details="Sandbox validation exceeded 5-second timeout",
                loop_free=False,
                policy_compliant=False,
                reachability_verified=False,
                execution_time_ms=5000,
            )
        finally:
            if topo:
                self.topology_builder.cleanup(topo)

    def _generate_proposed_flows(
        self, decision, current_flows: list[dict]
    ) -> list[dict]:
        """Generate proposed flow rules based on steering decision."""
        proposed = list(current_flows)

        for tc in decision.traffic_classes:
            proposed.append({
                "switch_id": "s1",
                "priority": 200,
                "match": f"ip,nw_proto=6",
                "actions": f"output:{self._link_to_port(decision.target_link)}",
            })

        return proposed

    def _link_to_port(self, link_id: str) -> int:
        """Map link ID to switch port number."""
        port_map = {
            "fiber-primary": 1,
            "broadband-secondary": 2,
            "satellite-backup": 3,
            "5g-mobile": 4,
        }
        return port_map.get(link_id, 1)
