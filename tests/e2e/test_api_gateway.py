# tests/e2e/test_api_gateway.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api-gateway"))

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


class TestAPIGateway:
    """End-to-end tests for the API Gateway endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_policy_intent_endpoint(self, client):
        """Test the IBN intent parsing endpoint."""
        async with client as ac:
            response = await ac.post("/api/v1/policies/intent", json={
                "intent": "Prioritize VoIP over guest WiFi"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "applied"
            assert len(data["rules_generated"]) == 2

    @pytest.mark.asyncio
    async def test_policy_intent_invalid(self, client):
        """Test that invalid intents return proper error."""
        async with client as ac:
            response = await ac.post("/api/v1/policies/intent", json={
                "intent": "do something random"
            })
            assert response.status_code in (400, 422, 500)

    @pytest.mark.asyncio
    async def test_active_policies_endpoint(self, client):
        """Test listing active policies."""
        async with client as ac:
            response = await ac.get("/api/v1/policies/active")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_steering_history_endpoint(self, client):
        """Test steering audit log endpoint."""
        async with client as ac:
            response = await ac.get("/api/v1/steering/history")
            assert response.status_code == 200
