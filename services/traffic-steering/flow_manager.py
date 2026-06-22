# services/traffic-steering/flow_manager.py

import asyncio
import json
import logging
from typing import Optional
import redis.asyncio as redis

from steering_engine import SteeringEngine, SteeringDecision
from sdn_clients.opendaylight import OpenDaylightClient
from sdn_clients.onos import ONOSClient

logger = logging.getLogger(__name__)


class FlowManager:
    """
    Orchestrates the steering pipeline:

    1. Listens for degradation alerts from the prediction engine
    2. Invokes the steering engine to compute decisions
    3. Executes decisions via the appropriate SDN controller
    4. Monitors execution and handles rollback on failure

    Runs as a long-lived async service.
    """

    def __init__(
        self,
        redis_url: str,
        sdn_type: str = "opendaylight",
        sdn_url: str = "http://opendaylight:8181",
    ):
        self.redis = redis.from_url(redis_url)
        self.steering = SteeringEngine(redis_url)

        if sdn_type == "opendaylight":
            self.sdn_client = OpenDaylightClient(sdn_url)
        elif sdn_type == "onos":
            self.sdn_client = ONOSClient(sdn_url)
        else:
            raise ValueError(f"Unsupported SDN controller type: {sdn_type}")

        self.steering.sdn_client = self.sdn_client

    async def run(self):
        """Main loop: evaluate and execute steering decisions."""
        logger.info("FlowManager started, listening for alerts...")

        while True:
            try:
                # Evaluate current state
                decisions = await self.steering.evaluate()

                for decision in decisions:
                    logger.info(
                        f"Steering decision: {decision.action.value} "
                        f"{decision.source_link} -> {decision.target_link} "
                        f"(confidence: {decision.confidence:.0%})"
                    )

                    success = await self.steering.execute(decision)
                    if success:
                        logger.info(f"Successfully executed: {decision.action.value}")
                        await self._notify_dashboard(decision)
                    else:
                        logger.warning(f"Failed to execute: {decision.action.value}")

            except Exception as e:
                logger.error(f"FlowManager error: {e}", exc_info=True)

            await asyncio.sleep(1.0)

    async def handle_manual_request(self, request: dict) -> bool:
        """Process a manual steering request from the API."""
        decision = SteeringDecision(
            action=SteeringEngine.SteeringAction.PREEMPTIVE_SHIFT
            if request.get("type") != "emergency"
            else SteeringEngine.SteeringAction.EMERGENCY_FAILOVER,
            source_link=request["source_link"],
            target_link=request["target_link"],
            traffic_classes=json.loads(request.get("traffic_classes", "[]")),
            confidence=1.0,
            reason=request.get("reason", "Manual request"),
            requires_sandbox_validation=True,
        )
        return await self.steering.execute(decision)

    async def _notify_dashboard(self, decision: SteeringDecision):
        """Push steering event to dashboard via Redis pub/sub."""
        await self.redis.xadd("steering:events", {
            "action": decision.action.value,
            "source": decision.source_link,
            "target": decision.target_link,
            "reason": decision.reason,
        })

    async def listen_for_requests(self):
        """Listen for manual steering requests from the API gateway."""
        last_id = "0-0"
        while True:
            try:
                entries = await self.redis.xread(
                    {"steering:requests": last_id}, count=10, block=1000
                )
                for stream, messages in entries:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        await self.handle_manual_request(
                            {k.decode(): v.decode() for k, v in fields.items()}
                        )
            except Exception as e:
                logger.error(f"Request listener error: {e}")
                await asyncio.sleep(1.0)


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    sdn_type = os.getenv("SDN_TYPE", "opendaylight")
    sdn_url = os.getenv("ODL_URL", "http://localhost:8181")

    manager = FlowManager(redis_url, sdn_type, sdn_url)

    async def main():
        await asyncio.gather(
            manager.run(),
            manager.listen_for_requests(),
        )

    asyncio.run(main())
