#!/usr/bin/env python3
"""
Telemetry Ingestion Service — Entry Point

Starts the telemetry collector that polls network devices via
SNMP/NetFlow/gNMI and publishes data to Redis Streams.
"""

import asyncio
import os
import logging
import json
from pathlib import Path

from collector import TelemetryCollector

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("telemetry-ingestion")

# Default device inventory for development
DEFAULT_DEVICES = [
    {"ip": "10.0.1.1", "community": "public", "link_id": "fiber-primary"},
    {"ip": "10.0.1.2", "community": "public", "link_id": "broadband-secondary"},
    {"ip": "10.0.1.3", "community": "public", "link_id": "satellite-backup"},
    {"ip": "10.0.1.4", "community": "public", "link_id": "5g-mobile"},
]


def load_device_inventory() -> list[dict]:
    """Load device inventory from file or environment."""
    inventory_path = os.getenv("DEVICE_INVENTORY", "devices.json")
    if Path(inventory_path).exists():
        with open(inventory_path) as f:
            return json.load(f)
    return DEFAULT_DEVICES


async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    poll_interval = float(os.getenv("POLL_INTERVAL", "1.0"))

    devices = load_device_inventory()
    logger.info(f"Loaded {len(devices)} devices for polling")

    collector = TelemetryCollector(redis_url=redis_url, poll_interval=poll_interval)

    # Register active links in Redis
    import redis.asyncio as redis
    r = redis.from_url(redis_url)
    for device in devices:
        await r.sadd("active_links", device.get("link_id", device["ip"]))
    await r.close()

    logger.info(f"Starting telemetry collection (interval: {poll_interval}s)")
    await collector.run(devices)


if __name__ == "__main__":
    asyncio.run(main())
