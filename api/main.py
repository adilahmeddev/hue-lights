"""
FastAPI HTTP wrapper for the Hue BLE daemon.

Run with: uvicorn api.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 19847


async def send_to_daemon(cmd: dict, timeout: float = 30.0) -> dict:
    """Send a command to the daemon and get response."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(DAEMON_HOST, DAEMON_PORT),
            timeout=2.0
        )
        writer.write((json.dumps(cmd) + "\n").encode())
        await writer.drain()

        data = await asyncio.wait_for(reader.readline(), timeout=timeout)
        writer.close()
        await writer.wait_closed()

        return json.loads(data.decode().strip())
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Daemon timeout")
    except ConnectionRefusedError:
        raise HTTPException(status_code=503, detail="Daemon not running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure daemon connection on startup
    try:
        result = await send_to_daemon({"cmd": "ping"})
        if result.get("ok"):
            print("Connected to daemon")
    except:
        print("Warning: Daemon not available at startup")
    yield


app = FastAPI(
    title="Hue Light Control API",
    description="HTTP API for controlling Philips Hue bulbs via Bluetooth",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for web app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BrightnessRequest(BaseModel):
    level: int


class StatusResponse(BaseModel):
    ok: bool
    power: str | None = None
    brightness: int | None = None
    connected: bool = False
    error: str | None = None


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get current bulb status (power and brightness)."""
    # First check if connected
    ping = await send_to_daemon({"cmd": "ping"})
    if not ping.get("connected"):
        # Try to connect
        await send_to_daemon({"cmd": "connect"})

    result = await send_to_daemon({"cmd": "status"})
    return StatusResponse(
        ok=result.get("ok", False),
        power=result.get("power"),
        brightness=result.get("brightness"),
        connected=result.get("ok", False),
        error=result.get("error")
    )


@app.post("/on")
async def turn_on():
    """Turn the bulb on."""
    # Ensure connected
    ping = await send_to_daemon({"cmd": "ping"})
    if not ping.get("connected"):
        connect = await send_to_daemon({"cmd": "connect"})
        if not connect.get("ok"):
            raise HTTPException(status_code=503, detail="Failed to connect to bulb")

    result = await send_to_daemon({"cmd": "on"})
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed"))
    return {"ok": True}


@app.post("/off")
async def turn_off():
    """Turn the bulb off."""
    ping = await send_to_daemon({"cmd": "ping"})
    if not ping.get("connected"):
        connect = await send_to_daemon({"cmd": "connect"})
        if not connect.get("ok"):
            raise HTTPException(status_code=503, detail="Failed to connect to bulb")

    result = await send_to_daemon({"cmd": "off"})
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed"))
    return {"ok": True}


@app.post("/toggle")
async def toggle():
    """Toggle the bulb on/off."""
    ping = await send_to_daemon({"cmd": "ping"})
    if not ping.get("connected"):
        connect = await send_to_daemon({"cmd": "connect"})
        if not connect.get("ok"):
            raise HTTPException(status_code=503, detail="Failed to connect to bulb")

    status = await send_to_daemon({"cmd": "status"})
    if not status.get("ok"):
        raise HTTPException(status_code=500, detail="Failed to get status")

    if status.get("power") == "on":
        result = await send_to_daemon({"cmd": "off"})
    else:
        result = await send_to_daemon({"cmd": "on"})

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed"))
    return {"ok": True, "power": "off" if status.get("power") == "on" else "on"}


@app.post("/brightness")
async def set_brightness(req: BrightnessRequest):
    """Set bulb brightness (1-100)."""
    if req.level < 1 or req.level > 100:
        raise HTTPException(status_code=400, detail="Brightness must be 1-100")

    ping = await send_to_daemon({"cmd": "ping"})
    if not ping.get("connected"):
        connect = await send_to_daemon({"cmd": "connect"})
        if not connect.get("ok"):
            raise HTTPException(status_code=503, detail="Failed to connect to bulb")

    result = await send_to_daemon({"cmd": "brightness", "level": req.level})
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed"))
    return {"ok": True, "brightness": req.level}
