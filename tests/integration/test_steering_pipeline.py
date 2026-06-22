# tests/integration/test_steering_pipeline.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "traffic-steering"))

import pytest
import asyncio
import json


class TestSteeringPipeline:
    """
    Integration test: publish degradation alert -> steering engine
    picks it up -> validates in sandbox -> executes handoff.
    
    These tests require Redis to be running.
    Set REDIS_URL environment variable or default to localhost.
    """

    @pytest.fixture
    def redis_url(self):
        import os
        return os.getenv("REDIS_URL", "redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_steering_engine_evaluation(self, redis_url):
        """Test that the steering engine evaluates link scores correctly."""
        import redis.asyncio as redis

        r = redis.from_url(redis_url)
        try:
            # Setup: Register active links with mock predictions
            await r.sadd("active_links", "link-a", "link-b")
            await r.hset("prediction:link-a", mapping={
                "health_score": "25",  # Critical
                "confidence": "0.9",
                "latency_forecast": "[]",
            })
            await r.hset("prediction:link-b", mapping={
                "health_score": "85",  # Healthy
                "confidence": "0.95",
                "latency_forecast": "[]",
            })

            from steering_engine import SteeringEngine
            engine = SteeringEngine(redis_url)
            decisions = await engine.evaluate()

            # Should recommend failover from link-a to link-b
            assert len(decisions) >= 1
            failover = decisions[0]
            assert failover.source_link == "link-a"
            assert failover.target_link == "link-b"
        finally:
            # Cleanup
            await r.delete("active_links", "prediction:link-a", "prediction:link-b")
            await r.close()

    @pytest.mark.asyncio
    async def test_preemptive_shift_requires_validation(self, redis_url):
        """Preemptive shifts should require sandbox validation."""
        import redis.asyncio as redis

        r = redis.from_url(redis_url)
        try:
            await r.sadd("active_links", "link-a", "link-b")
            await r.hset("prediction:link-a", mapping={
                "health_score": "45",  # Warning (between 30 and 50)
                "confidence": "0.85",
                "latency_forecast": "[]",
            })
            await r.hset("prediction:link-b", mapping={
                "health_score": "90",
                "confidence": "0.95",
                "latency_forecast": "[]",
            })

            from steering_engine import SteeringEngine
            engine = SteeringEngine(redis_url)
            decisions = await engine.evaluate()

            preemptive = [d for d in decisions if d.action.value == "shift"]
            assert len(preemptive) >= 1
            assert preemptive[0].requires_sandbox_validation is True
        finally:
            await r.delete("active_links", "prediction:link-a", "prediction:link-b")
            await r.close()

    @pytest.mark.asyncio
    async def test_hold_when_all_healthy(self, redis_url):
        """No steering decisions when all links are healthy."""
        import redis.asyncio as redis

        r = redis.from_url(redis_url)
        try:
            await r.sadd("active_links", "link-a", "link-b")
            await r.hset("prediction:link-a", mapping={
                "health_score": "85",
                "confidence": "0.9",
                "latency_forecast": "[]",
            })
            await r.hset("prediction:link-b", mapping={
                "health_score": "90",
                "confidence": "0.95",
                "latency_forecast": "[]",
            })

            from steering_engine import SteeringEngine
            engine = SteeringEngine(redis_url)
            decisions = await engine.evaluate()

            assert len(decisions) == 0, "No decisions expected when all links healthy"
        finally:
            await r.delete("active_links", "prediction:link-a", "prediction:link-b")
            await r.close()
