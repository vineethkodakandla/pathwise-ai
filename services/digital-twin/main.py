#!/usr/bin/env python3
"""
Digital Twin Service — Entry Point

Listens for sandbox validation requests on Redis Streams,
runs them through the Mininet + Batfish validation pipeline,
and publishes results back.
"""

import asyncio
import os
import json
import logging
import redis.asyncio as redis

from twin_manager import DigitalTwinManager

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("digital-twin")


# Reference production topology for sandbox
DEFAULT_TOPOLOGY = {
    "switches": [
        {"id": "s1", "dpid": "0000000000000001"},
        {"id": "s2", "dpid": "0000000000000002"},
    ],
    "hosts": [
        {"id": "h1", "ip": "10.0.1.1/24"},
        {"id": "h2", "ip": "10.0.2.1/24"},
    ],
    "links": [
        {"src": "h1", "dst": "s1", "bw": 1000, "delay": "1ms", "loss": 0,
         "link_id": "host-link-1"},
        {"src": "h2", "dst": "s2", "bw": 1000, "delay": "1ms", "loss": 0,
         "link_id": "host-link-2"},
        {"src": "s1", "dst": "s2", "bw": 1000, "delay": "5ms", "loss": 0.01,
         "link_id": "fiber-primary"},
        {"src": "s1", "dst": "s2", "bw": 100, "delay": "15ms", "loss": 0.1,
         "link_id": "broadband-secondary"},
        {"src": "s1", "dst": "s2", "bw": 10, "delay": "300ms", "loss": 0.5,
         "link_id": "satellite-backup"},
        {"src": "s1", "dst": "s2", "bw": 200, "delay": "20ms", "loss": 0.2,
         "link_id": "5g-mobile"},
    ],
}


async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = redis.from_url(redis_url)
    twin = DigitalTwinManager()
    last_id = "0-0"

    logger.info("Digital Twin service started, listening for validation requests...")

    while True:
        try:
            entries = await r.xread(
                {"sandbox:requests": last_id}, count=5, block=1000
            )

            for stream, messages in entries:
                for msg_id, fields in messages:
                    last_id = msg_id
                    decoded = {k.decode(): v.decode() for k, v in fields.items()}
                    report_id = decoded.get("report_id", msg_id.decode())

                    logger.info(f"Validating request {report_id}: "
                                f"{decoded.get('source_link')} -> {decoded.get('target_link')}")

                    # Build a mock steering decision for the validator
                    class MockDecision:
                        source_link = decoded.get("source_link", "")
                        target_link = decoded.get("target_link", "")
                        traffic_classes = json.loads(decoded.get("traffic_classes", "[]"))
                        action = decoded.get("action", "shift")

                    topology_override = json.loads(decoded.get("topology_override", "{}"))
                    topology = topology_override if topology_override else DEFAULT_TOPOLOGY

                    try:
                        report = await twin.validate_steering_decision(
                            decision=MockDecision(),
                            current_topology=topology,
                            current_flows=[],
                        )

                        await r.hset(f"sandbox:report:{report_id}", mapping={
                            "result": report.result.value,
                            "details": report.details,
                            "loop_free": str(report.loop_free).lower(),
                            "policy_compliant": str(report.policy_compliant).lower(),
                            "reachability_verified": str(report.reachability_verified).lower(),
                            "execution_time_ms": str(report.execution_time_ms),
                        })
                        logger.info(f"Validation {report_id}: {report.result.value} "
                                    f"({report.execution_time_ms:.1f}ms)")
                    except Exception as e:
                        logger.error(f"Validation {report_id} failed: {e}")
                        await r.hset(f"sandbox:report:{report_id}", mapping={
                            "result": "error",
                            "details": str(e),
                            "loop_free": "false",
                            "policy_compliant": "false",
                            "reachability_verified": "false",
                            "execution_time_ms": "0",
                        })

        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
