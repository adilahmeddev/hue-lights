"""
Philips Hue Bluetooth Low Energy Control Library

Controls Philips Hue White bulbs over Bluetooth using a persistent connection.
"""

import asyncio
import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, NamedTuple

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

try:
    from bleak.backends.winrt.client import WinRTClientArgs
    WINRT_ARGS = {"winrt": WinRTClientArgs(use_cached_services=True)}
except ImportError:
    WINRT_ARGS = {}

# Philips Hue BLE UUIDs
HUE_SERVICE_UUID = "932c32bd-0000-47a2-835a-a8d455b859dd"
POWER_CHAR_UUID = "932c32bd-0002-47a2-835a-a8d455b859dd"
BRIGHTNESS_CHAR_UUID = "932c32bd-0003-47a2-835a-a8d455b859dd"

CONFIG_FILE = Path.home() / ".hue_ble_config.json"


class EventType(Enum):
    CONNECTED = auto()
    DISCONNECTED = auto()
    STATE_CHANGED = auto()
    ERROR = auto()


class Event(NamedTuple):
    type: EventType
    payload: Any


class Observer:
    def on_next(self, event: Event) -> None:
        pass

    def on_complete(self) -> None:
        pass

    def on_error(self, exc: Exception) -> None:
        pass


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


async def scan_for_bulbs(timeout: float = 5.0) -> list[dict]:
    """Scan for Philips Hue Bluetooth bulbs."""
    print(f"Scanning for Hue bulbs ({timeout}s)...")
    found_bulbs = []

    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

    for device, adv_data in devices.values():
        service_uuids = adv_data.service_uuids or []
        if HUE_SERVICE_UUID.lower() in [u.lower() for u in service_uuids]:
            found_bulbs.append({"address": device.address, "name": device.name or "Unknown Hue Bulb"})
        elif device.name and "Hue" in device.name:
            found_bulbs.append({"address": device.address, "name": device.name})

    return found_bulbs


class HueBulbConnection:
    """Persistent connection manager for a Philips Hue bulb."""

    def __init__(self, address: str):
        self.address = address
        self._client: BleakClient | None = None
        self._disconnect_event = asyncio.Event()
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None and self._client.is_connected

    async def connect(self, timeout: float = 30.0) -> bool:
        """Connect and maintain connection until disconnect() is called."""
        if self.is_connected:
            return True

        try:
            self._client = BleakClient(
                self.address,
                timeout=timeout,
                disconnected_callback=self._on_disconnect,
                **WINRT_ARGS
            )
            await self._client.connect()

            if not self._client.is_connected:
                return False

            self._connected = True
            self._disconnect_event.clear()

            # Try pairing if needed
            try:
                await self._client.read_gatt_char(POWER_CHAR_UUID)
            except BleakError as e:
                if "Insufficient Encryption" in str(e) or "0x0F" in str(e):
                    print("Pairing required...")
                    await self._client.pair()

            self._save_working_address()
            return True

        except TimeoutError:
            print("Connection timed out")
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle unexpected disconnection."""
        self._connected = False
        self._disconnect_event.set()

    async def disconnect(self) -> None:
        """Disconnect from the bulb."""
        self._disconnect_event.set()
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
        self._connected = False

    async def wait_for_disconnect(self) -> None:
        """Wait until disconnection occurs."""
        await self._disconnect_event.wait()

    def _save_working_address(self):
        config = load_config()
        config["last_address"] = self.address
        save_config(config)

    async def turn_on(self) -> bool:
        if not self.is_connected:
            return False
        async with self._lock:
            try:
                await self._client.write_gatt_char(POWER_CHAR_UUID, bytes([0x01]))
                return True
            except BleakError as e:
                print(f"Error: {e}")
                return False

    async def turn_off(self) -> bool:
        if not self.is_connected:
            return False
        async with self._lock:
            try:
                await self._client.write_gatt_char(POWER_CHAR_UUID, bytes([0x00]))
                return True
            except BleakError as e:
                print(f"Error: {e}")
                return False

    async def set_brightness(self, percent: int) -> bool:
        if not self.is_connected:
            return False
        percent = max(1, min(100, percent))
        value = int((percent / 100) * 253) + 1
        async with self._lock:
            try:
                await self._client.write_gatt_char(BRIGHTNESS_CHAR_UUID, bytes([value]))
                return True
            except BleakError as e:
                print(f"Error: {e}")
                return False

    async def get_state(self) -> dict | None:
        if not self.is_connected:
            return None
        async with self._lock:
            try:
                power_data = await self._client.read_gatt_char(POWER_CHAR_UUID)
                brightness_data = await self._client.read_gatt_char(BRIGHTNESS_CHAR_UUID)

                power_on = power_data[0] == 0x01 if power_data else False
                brightness_raw = brightness_data[0] if brightness_data else 1
                brightness_percent = max(1, min(100, int(((brightness_raw - 1) / 253) * 100)))

                return {"power": "on" if power_on else "off", "brightness": brightness_percent}
            except BleakError as e:
                print(f"Error: {e}")
                return None


# Backwards-compatible wrapper
class HueBulb:
    """Simple wrapper for one-off commands (connects/disconnects each time)."""

    def __init__(self, address: str):
        self.address = address
        self._conn: HueBulbConnection | None = None

    async def connect(self, timeout: float = 30.0) -> bool:
        self._conn = HueBulbConnection(self.address)
        return await self._conn.connect(timeout)

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.disconnect()
            self._conn = None

    async def turn_on(self) -> bool:
        return await self._conn.turn_on() if self._conn else False

    async def turn_off(self) -> bool:
        return await self._conn.turn_off() if self._conn else False

    async def set_brightness(self, percent: int) -> bool:
        return await self._conn.set_brightness(percent) if self._conn else False

    async def get_state(self) -> dict | None:
        return await self._conn.get_state() if self._conn else None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
