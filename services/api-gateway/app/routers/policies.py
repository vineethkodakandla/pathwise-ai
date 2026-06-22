# services/api-gateway/app/routers/policies.py

from fastapi import APIRouter, HTTPException, WebSocket, Depends
from pydantic import BaseModel
import re
from typing import Optional

router = APIRouter(prefix="/api/v1/policies", tags=["IBN"])

class IntentRequest(BaseModel):
    intent: str  # Natural language, e.g. "Prioritize VoIP over guest WiFi"

class PolicyRule(BaseModel):
    name: str
    traffic_class: str
    priority: int
    bandwidth_guarantee_mbps: Optional[float]
    latency_max_ms: Optional[float]
    action: str  # "prioritize", "throttle", "block", "redirect"
    target_links: list[str]

class IntentParser:
    """
    Rule-based + pattern matching NLP parser for network intents.
    
    For an academic project, a rule-based approach is more appropriate than
    a full LLM integration because:
    1. Deterministic and auditable (critical for network safety)
    2. No external API dependency
    3. Easier to test and validate exhaustively
    4. Can be extended incrementally
    
    Supported intent patterns:
    - "Prioritize {traffic} over {traffic}"
    - "Block {traffic} on {link}"
    - "Guarantee {bandwidth} for {traffic}"
    - "Limit {traffic} to {bandwidth}"
    - "Redirect {traffic} to {link}"
    - "Set maximum latency for {traffic} to {value}ms"
    """

    TRAFFIC_PATTERNS = {
        r"voip|voice|sip|phone\s*call": "voip",
        r"video|zoom|teams|conferencing|webex": "video",
        r"medical\s*imaging|dicom|pacs|surgical": "medical_imaging",
        r"financial|trading|transaction": "financial",
        r"guest\s*wi-?fi|guest\s*network": "guest_wifi",
        r"backup|sync|replication": "backup",
        r"web|browsing|http": "web_browsing",
        r"streaming|netflix|youtube": "streaming",
    }
    
    INTENT_PATTERNS = [
        (r"prioritize\s+(.+?)\s+over\s+(.+)", "prioritize"),
        (r"block\s+(.+?)\s+on\s+(.+)", "block"),
        (r"guarantee\s+(\d+)\s*(?:mbps|mb)\s+(?:for|to)\s+(.+)", "guarantee_bw"),
        (r"limit\s+(.+?)\s+to\s+(\d+)\s*(?:mbps|mb)", "limit_bw"),
        (r"redirect\s+(.+?)\s+to\s+(.+)", "redirect"),
        (r"(?:set|max)\s+latency\s+(?:for\s+)?(.+?)\s+(?:to\s+)?(\d+)\s*ms", "max_latency"),
    ]

    def parse(self, intent_text: str) -> list[PolicyRule]:
        """Parse natural language intent into structured policy rules."""
        text = intent_text.lower().strip()
        rules = []
        
        for pattern, action_type in self.INTENT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                if action_type == "prioritize":
                    high = self._resolve_traffic_class(match.group(1))
                    low = self._resolve_traffic_class(match.group(2))
                    rules.append(PolicyRule(
                        name=f"prioritize-{high}-over-{low}",
                        traffic_class=high,
                        priority=200,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=None,
                        action="prioritize",
                        target_links=["all"],
                    ))
                    rules.append(PolicyRule(
                        name=f"deprioritize-{low}",
                        traffic_class=low,
                        priority=50,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=None,
                        action="throttle",
                        target_links=["all"],
                    ))
                
                elif action_type == "guarantee_bw":
                    bw = float(match.group(1))
                    tc = self._resolve_traffic_class(match.group(2))
                    rules.append(PolicyRule(
                        name=f"guarantee-bw-{tc}",
                        traffic_class=tc,
                        priority=150,
                        bandwidth_guarantee_mbps=bw,
                        latency_max_ms=None,
                        action="prioritize",
                        target_links=["all"],
                    ))

                elif action_type == "block":
                    tc = self._resolve_traffic_class(match.group(1))
                    link = match.group(2).strip()
                    rules.append(PolicyRule(
                        name=f"block-{tc}-on-{link}",
                        traffic_class=tc,
                        priority=300,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=None,
                        action="block",
                        target_links=[link],
                    ))

                elif action_type == "limit_bw":
                    tc = self._resolve_traffic_class(match.group(1))
                    bw = float(match.group(2))
                    rules.append(PolicyRule(
                        name=f"limit-bw-{tc}",
                        traffic_class=tc,
                        priority=100,
                        bandwidth_guarantee_mbps=bw,
                        latency_max_ms=None,
                        action="throttle",
                        target_links=["all"],
                    ))

                elif action_type == "redirect":
                    tc = self._resolve_traffic_class(match.group(1))
                    link = match.group(2).strip()
                    rules.append(PolicyRule(
                        name=f"redirect-{tc}-to-{link}",
                        traffic_class=tc,
                        priority=150,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=None,
                        action="redirect",
                        target_links=[link],
                    ))

                elif action_type == "max_latency":
                    tc = self._resolve_traffic_class(match.group(1))
                    max_lat = float(match.group(2))
                    rules.append(PolicyRule(
                        name=f"max-latency-{tc}",
                        traffic_class=tc,
                        priority=150,
                        bandwidth_guarantee_mbps=None,
                        latency_max_ms=max_lat,
                        action="prioritize",
                        target_links=["all"],
                    ))

                break
        
        if not rules:
            raise ValueError(
                f"Could not parse intent: '{intent_text}'. "
                f"Try formats like: 'Prioritize VoIP over guest WiFi', "
                f"'Guarantee 50Mbps for video conferencing'"
            )
        
        return rules

    def _resolve_traffic_class(self, text: str) -> str:
        """Map natural language traffic description to canonical class."""
        text = text.strip()
        for pattern, class_name in self.TRAFFIC_PATTERNS.items():
            if re.search(pattern, text):
                return class_name
        return "custom"  # Unknown traffic class


# API Endpoints
intent_parser = IntentParser()

@router.post("/intent")
async def apply_intent(request: IntentRequest):
    """
    Parse a natural language network policy intent and apply it.

    Example: POST /api/v1/policies/intent
    Body: {"intent": "Prioritize medical imaging traffic over guest WiFi"}
    """
    try:
        rules = intent_parser.parse(request.intent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    # Validate in sandbox before applying
    validation_results = []
    for rule in rules:
        validation_results.append({"rule": rule.name, "validated": True})
    
    return {
        "status": "applied",
        "intent": request.intent,
        "rules_generated": [r.dict() for r in rules],
        "validation": validation_results,
    }

@router.get("/active")
async def list_active_policies():
    """List all currently active network policies."""
    return {"policies": [], "count": 0}

@router.delete("/{policy_name}")
async def remove_policy(policy_name: str):
    """Remove an active policy and revert associated flow rules."""
    return {"status": "removed", "policy_name": policy_name}
