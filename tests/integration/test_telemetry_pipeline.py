# tests/integration/test_telemetry_pipeline.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "telemetry-ingestion"))

import pytest
import asyncio
import os


class TestTelemetryPipeline:
    """
    Integration tests for the telemetry ingestion pipeline.
    Requires Redis to be running.
    """

    @pytest.fixture
    def redis_url(self):
        return os.getenv("REDIS_URL", "redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_publish_and_read_telemetry(self, redis_url):
        """Published telemetry should be readable from Redis Stream."""
        import redis.asyncio as redis
        from collector import TelemetryCollector, TelemetryPoint

        r = redis.from_url(redis_url)
        collector = TelemetryCollector(redis_url=redis_url, mode="synthetic")

        try:
            # Publish a telemetry point
            point = TelemetryPoint(
                timestamp=1706000000.0,
                link_id="test-link-integration",
                latency_ms=15.5,
                jitter_ms=2.3,
                packet_loss_pct=0.01,
                bandwidth_utilization_pct=45.0,
                rtt_ms=31.0,
            )
            await collector.publish(point)

            # Read it back from the stream
            entries = await r.xrevrange("telemetry:raw", count=1)
            assert len(entries) >= 1

            entry_id, fields = entries[0]
            assert fields[b"link_id"] == b"test-link-integration"
            assert float(fields[b"latency_ms"]) == 15.5
        finally:
            await r.close()
            await collector.redis.close()

    @pytest.mark.asyncio
    async def test_synthetic_collection_produces_valid_points(self, redis_url):
        """Synthetic collector should produce valid data points."""
        from collector import TelemetryCollector

        collector = TelemetryCollector(redis_url=redis_url, mode="synthetic")

        points = []
        for _ in range(10):
            point = collector._collect_synthetic("test-device")
            points.append(point)

        assert len(points) == 10
        for p in points:
            assert p.latency_ms >= 0
            assert p.jitter_ms >= 0
            assert 0 <= p.packet_loss_pct <= 100
            assert 0 <= p.bandwidth_utilization_pct <= 100

    @pytest.mark.asyncio
    async def test_active_links_registration(self, redis_url):
        """Active links should be registered in Redis set."""
        import redis.asyncio as redis

        r = redis.from_url(redis_url)
        try:
            # Register test links
            await r.sadd("active_links", "test-link-a", "test-link-b")

            members = await r.smembers("active_links")
            link_ids = {m.decode() for m in members}
            assert "test-link-a" in link_ids
            assert "test-link-b" in link_ids
        finally:
            await r.srem("active_links", "test-link-a", "test-link-b")
            await r.close()
