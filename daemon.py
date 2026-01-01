"""
Hue Bulb Daemon - Keeps a persistent BLE connection for fast commands.

Run this in the background:
    python daemon.py start

Then use the CLI normally - it will connect to the daemon for instant commands.
"""

import asyncio
import json
import sys
from pathlib import Path

from hue_ble import HueBulbConnection, load_config, scan_for_bulbs

SOCKET_PORT = 19847
PID_FILE = Path.home() / ".hue_ble_daemon.pid"


class HueDaemon:
    def __init__(self):
        self.connection: HueBulbConnection | None = None
        self.server: asyncio.Server | None = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming command from CLI."""
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not data:
                return

            request = json.loads(data.decode().strip())
            cmd = request.get("cmd")
            response = {"ok": False, "error": "Unknown command"}

            if cmd == "ping":
                response = {"ok": True, "connected": self.connection and self.connection.is_connected}

            elif cmd == "connect":
                address = request.get("address")
                if not address:
                    config = load_config()
                    address = config.get("last_address")

                if not address:
                    response = {"ok": False, "error": "No address specified"}
                else:
                    if self.connection and self.connection.is_connected:
                        if self.connection.address == address:
                            response = {"ok": True, "message": "Already connected"}
                        else:
                            await self.connection.disconnect()
                            self.connection = None

                    if not self.connection or not self.connection.is_connected:
                        self.connection = HueBulbConnection(address)
                        print(f"Connecting to {address}...")
                        success = await self.connection.connect()
                        if success:
                            response = {"ok": True, "message": f"Connected to {address}"}
                        else:
                            response = {"ok": False, "error": "Connection failed"}

            elif cmd == "disconnect":
                if self.connection:
                    await self.connection.disconnect()
                    self.connection = None
                response = {"ok": True}

            elif cmd == "on":
                if self.connection and self.connection.is_connected:
                    success = await self.connection.turn_on()
                    response = {"ok": success}
                else:
                    response = {"ok": False, "error": "Not connected"}

            elif cmd == "off":
                if self.connection and self.connection.is_connected:
                    success = await self.connection.turn_off()
                    response = {"ok": success}
                else:
                    response = {"ok": False, "error": "Not connected"}

            elif cmd == "brightness":
                level = request.get("level", 50)
                if self.connection and self.connection.is_connected:
                    success = await self.connection.set_brightness(level)
                    response = {"ok": success}
                else:
                    response = {"ok": False, "error": "Not connected"}

            elif cmd == "status":
                if self.connection and self.connection.is_connected:
                    state = await self.connection.get_state()
                    if state:
                        response = {"ok": True, **state}
                    else:
                        response = {"ok": False, "error": "Failed to read state"}
                else:
                    response = {"ok": False, "error": "Not connected"}

            elif cmd == "shutdown":
                response = {"ok": True, "message": "Shutting down"}
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
                writer.close()
                await self.stop()
                return

            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            try:
                writer.write((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
                await writer.drain()
            except:
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def start(self):
        """Start the daemon server."""
        self.server = await asyncio.start_server(
            self.handle_client,
            "127.0.0.1",
            SOCKET_PORT
        )

        # Write PID file
        PID_FILE.write_text(str(asyncio.current_task().get_name()))

        print(f"Hue daemon listening on port {SOCKET_PORT}")

        # Auto-connect to last known bulb
        config = load_config()
        if "last_address" in config:
            address = config["last_address"]
            print(f"Auto-connecting to {address}...")
            self.connection = HueBulbConnection(address)
            if await self.connection.connect():
                print("Connected!")
            else:
                print("Auto-connect failed. Use CLI to connect manually.")
                self.connection = None

        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """Stop the daemon."""
        if self.connection:
            await self.connection.disconnect()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if PID_FILE.exists():
            PID_FILE.unlink()
        print("Daemon stopped.")


async def send_command(cmd: dict) -> dict:
    """Send a command to the daemon."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", SOCKET_PORT),
            timeout=2.0
        )
        writer.write((json.dumps(cmd) + "\n").encode())
        await writer.drain()

        data = await asyncio.wait_for(reader.readline(), timeout=30.0)
        writer.close()
        await writer.wait_closed()

        return json.loads(data.decode().strip())
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Timeout"}
    except ConnectionRefusedError:
        return {"ok": False, "error": "Daemon not running"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def is_daemon_running() -> bool:
    """Check if daemon is running."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        sock.connect(("127.0.0.1", SOCKET_PORT))
        sock.close()
        return True
    except:
        return False


async def main():
    if len(sys.argv) < 2:
        print("Usage: python daemon.py [start|stop|status]")
        return

    cmd = sys.argv[1]

    if cmd == "start":
        if is_daemon_running():
            print("Daemon already running")
            return
        daemon = HueDaemon()
        try:
            await daemon.start()
        except KeyboardInterrupt:
            await daemon.stop()

    elif cmd == "stop":
        result = await send_command({"cmd": "shutdown"})
        if result.get("ok"):
            print("Daemon stopped")
        else:
            print(f"Error: {result.get('error', 'Unknown')}")

    elif cmd == "status":
        if is_daemon_running():
            result = await send_command({"cmd": "ping"})
            if result.get("connected"):
                print("Daemon running, bulb connected")
            else:
                print("Daemon running, bulb not connected")
        else:
            print("Daemon not running")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())
