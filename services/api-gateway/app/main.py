# services/api-gateway/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import telemetry, predictions, steering, sandbox, policies
from app.websocket.scoreboard import ScoreboardManager

scoreboard = ScoreboardManager(redis_url="redis://redis:6379")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    task = asyncio.create_task(scoreboard.broadcast_loop())
    yield
    task.cancel()

app = FastAPI(
    title="PathWise AI API",
    version="1.0.0",
    description="AI-Powered SD-WAN Management Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(telemetry.router)     # GET /api/v1/telemetry/{link_id}
app.include_router(predictions.router)    # GET /api/v1/predictions/{link_id}
app.include_router(steering.router)       # POST /api/v1/steering/execute
app.include_router(sandbox.router)        # POST /api/v1/sandbox/validate
app.include_router(policies.router)       # POST /api/v1/policies/intent

# WebSocket
@app.websocket("/ws/scoreboard")
async def scoreboard_ws(ws):
    await scoreboard.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep connection alive
    except:
        await scoreboard.disconnect(ws)
