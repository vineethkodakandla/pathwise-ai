# services/api-gateway/app/middleware/auth.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Simple RBAC middleware for PathWise API.

    Roles:
    - admin: Full access to all endpoints
    - operator: Can view telemetry, predictions; can execute steering
    - viewer: Read-only access to telemetry and predictions

    For academic use, authentication is token-based with static tokens.
    Production would use OAuth2/JWT.
    """

    ROLE_PERMISSIONS = {
        "admin": {"telemetry", "predictions", "steering", "sandbox", "policies"},
        "operator": {"telemetry", "predictions", "steering", "sandbox"},
        "viewer": {"telemetry", "predictions"},
    }

    # Static tokens for development
    TOKENS = {
        "pathwise-admin-token": "admin",
        "pathwise-operator-token": "operator",
        "pathwise-viewer-token": "viewer",
    }

    async def dispatch(self, request: Request, call_next):
        # Skip auth for docs and health check
        if request.url.path in ("/docs", "/openapi.json", "/redoc", "/health"):
            return await call_next(request)

        # Skip auth for WebSocket (handled separately)
        if request.url.path.startswith("/ws/"):
            return await call_next(request)

        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        role = self.TOKENS.get(token)

        if not role:
            # Allow unauthenticated access in development
            logger.warning(f"Unauthenticated request to {request.url.path}")
            return await call_next(request)

        # Check permission for the route category
        route_category = self._get_route_category(request.url.path)
        if route_category and route_category not in self.ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' does not have access to '{route_category}' endpoints",
            )

        request.state.role = role
        return await call_next(request)

    def _get_route_category(self, path: str) -> Optional[str]:
        """Extract the API category from the request path."""
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
            return parts[2]
        return None
