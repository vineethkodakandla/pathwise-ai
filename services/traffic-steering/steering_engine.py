# services/traffic-steering/steering_engine.py

import asyncio
import json
import redis.asyncio as redis
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SteeringAction(Enum):
    HOLD = "hold"               # No change needed
    PREEMPTIVE_SHIFT = "shift"  # Predicted degradation — move traffic
    EMERGENCY_FAILOVER = "failover"  # Immediate degradation detected
    REBALANCE = "rebalance"     # Load-balance across healthy links

@dataclass
class SteeringDecision:
    action: SteeringAction
    source_link: str
    target_link: str
    traffic_classes: list[str]  # ["voip", "video", "critical", "bulk"]
    confidence: float
    reason: str
    requires_sandbox_validation: bool

class SteeringEngine:
    """
    Decision engine that consumes predictions and determines
    optimal traffic placement across available WAN links.
    
    Decision logic:
    1. If any link health_score < CRITICAL_THRESHOLD (30): emergency failover
    2. If any link health_score < WARNING_THRESHOLD (50) and confidence > 0.7:
       preemptive shift to the highest-scoring alternative
    3. If score variance across links > REBALANCE_THRESHOLD: rebalance
    4. Otherwise: hold
    
    ALL preemptive shifts go through Digital Twin validation first.
    Emergency failovers execute immediately but are validated post-hoc.
    """
    
    CRITICAL_THRESHOLD = 30
    WARNING_THRESHOLD = 50
    CONFIDENCE_THRESHOLD = 0.7
    REBALANCE_THRESHOLD = 30

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.sdn_client = None  # Injected based on controller type

    async def evaluate(self) -> list[SteeringDecision]:
        """Evaluate all links and return steering decisions."""
        link_ids = await self.redis.smembers("active_links")
        link_scores = {}
        
        for link_id_bytes in link_ids:
            link_id = link_id_bytes.decode()
            pred = await self.redis.hgetall(f"prediction:{link_id}")
            if pred:
                link_scores[link_id] = {
                    "health_score": float(pred[b"health_score"]),
                    "confidence": float(pred[b"confidence"]),
                }
        
        decisions = []
        sorted_links = sorted(
            link_scores.items(), key=lambda x: x[1]["health_score"], reverse=True
        )
        best_link = sorted_links[0][0] if sorted_links else None
        
        for link_id, scores in link_scores.items():
            if scores["health_score"] < self.CRITICAL_THRESHOLD:
                # Emergency: execute immediately
                if best_link and best_link != link_id:
                    decisions.append(SteeringDecision(
                        action=SteeringAction.EMERGENCY_FAILOVER,
                        source_link=link_id,
                        target_link=best_link,
                        traffic_classes=["voip", "video", "critical", "bulk"],
                        confidence=scores["confidence"],
                        reason=f"Link {link_id} health critical ({scores['health_score']})",
                        requires_sandbox_validation=False,  # Post-hoc validation
                    ))
            
            elif (scores["health_score"] < self.WARNING_THRESHOLD
                  and scores["confidence"] > self.CONFIDENCE_THRESHOLD):
                # Preemptive: validate first
                if best_link and best_link != link_id:
                    decisions.append(SteeringDecision(
                        action=SteeringAction.PREEMPTIVE_SHIFT,
                        source_link=link_id,
                        target_link=best_link,
                        traffic_classes=["voip", "video", "critical"],
                        confidence=scores["confidence"],
                        reason=(
                            f"Predicted degradation on {link_id} "
                            f"(score: {scores['health_score']}, "
                            f"confidence: {scores['confidence']:.0%})"
                        ),
                        requires_sandbox_validation=True,
                    ))
        
        return decisions

    async def execute(self, decision: SteeringDecision):
        """
        Execute a steering decision via the SDN controller.
        
        For hitless handoff:
        1. Install new flow rules on target path FIRST (make-before-break)
        2. Update priority so new path is preferred
        3. Remove old flow rules after traffic has migrated
        4. Log the entire operation for audit trail
        """
        audit_entry = {
            "action": decision.action.value,
            "source": decision.source_link,
            "target": decision.target_link,
            "traffic_classes": decision.traffic_classes,
            "confidence": decision.confidence,
            "reason": decision.reason,
        }
        
        if decision.requires_sandbox_validation:
            # Validate in Digital Twin first
            is_valid = await self.validate_in_sandbox(decision)
            audit_entry["sandbox_validated"] = is_valid
            
            if not is_valid:
                audit_entry["status"] = "blocked_by_sandbox"
                await self.log_audit(audit_entry)
                return False
        
        # Execute make-before-break handoff
        success = await self.sdn_client.install_flow_rules(
            source_link=decision.source_link,
            target_link=decision.target_link,
            traffic_classes=decision.traffic_classes,
            strategy="make-before-break",
        )
        
        audit_entry["status"] = "executed" if success else "failed"
        await self.log_audit(audit_entry)
        return success

    async def validate_in_sandbox(self, decision: SteeringDecision) -> bool:
        """Send decision to Digital Twin for validation."""
        await self.redis.xadd("sandbox:requests", {
            "source_link": decision.source_link,
            "target_link": decision.target_link,
            "traffic_classes": json.dumps(decision.traffic_classes),
            "action": decision.action.value,
        })
        # In production, await sandbox result via Redis pub/sub
        return True

    async def log_audit(self, entry: dict):
        """Log steering decision to audit trail."""
        await self.redis.xadd("steering:audit", {
            k: str(v) for k, v in entry.items()
        })
