#!/usr/bin/env python3
"""
Philips Hue Bluetooth CLI

Usage:
    python cli.py scan                  # Find nearby Hue bulbs
    python cli.py on                    # Turn bulb on
    python cli.py off                   # Turn bulb off
    python cli.py brightness <1-100>    # Set brightness
    python cli.py status                # Show current state
    python cli.py daemon start          # Start background daemon (fast mode)
    python cli.py daemon stop           # Stop daemon
"""

import argparse
import asyncio
import sys

from hue_ble import HueBulb, scan_for_bulbs, load_config


async def try_daemon_command(cmd: dict) -> dict | None:
    """Try to send command to daemon. Returns None if daemon not running."""
    try:
        from daemon import send_command, is_daemon_running
        if is_daemon_running():
            return await send_command(cmd)
    except ImportError:
        pass
    return None


async def cmd_scan(args) -> int:
    bulbs = await scan_for_bulbs(timeout=args.timeout)

    if not bulbs:
        print("No Hue bulbs found.")
        return 1

    print(f"\nFound {len(bulbs)} bulb(s):\n")
    for bulb in bulbs:
        print(f"  {bulb['name']}")
        print(f"    Address: {bulb['address']}")
        print()

    print("To use a bulb:")
    print(f"  python cli.py --address {bulbs[0]['address']} on")
    return 0


async def cmd_on(args) -> int:
    address = get_address(args)
    if not address:
        return 1

    # Try daemon first
    result = await try_daemon_command({"cmd": "connect", "address": address})
    if result and result.get("ok"):
        result = await try_daemon_command({"cmd": "on"})
        if result and result.get("ok"):
            print("Bulb turned ON (via daemon)")
            return 0

    # Fallback to direct connection
    print(f"Connecting to {address}...")
    async with HueBulb(address) as bulb:
        if await bulb.turn_on():
            print("Bulb turned ON")
            return 0
        print("Failed to turn on bulb")
        return 1


async def cmd_off(args) -> int:
    address = get_address(args)
    if not address:
        return 1

    result = await try_daemon_command({"cmd": "connect", "address": address})
    if result and result.get("ok"):
        result = await try_daemon_command({"cmd": "off"})
        if result and result.get("ok"):
            print("Bulb turned OFF (via daemon)")
            return 0

    print(f"Connecting to {address}...")
    async with HueBulb(address) as bulb:
        if await bulb.turn_off():
            print("Bulb turned OFF")
            return 0
        print("Failed to turn off bulb")
        return 1


async def cmd_brightness(args) -> int:
    address = get_address(args)
    if not address:
        return 1

    level = args.level
    if level < 1 or level > 100:
        print("Brightness must be between 1 and 100")
        return 1

    result = await try_daemon_command({"cmd": "connect", "address": address})
    if result and result.get("ok"):
        result = await try_daemon_command({"cmd": "brightness", "level": level})
        if result and result.get("ok"):
            print(f"Brightness set to {level}% (via daemon)")
            return 0

    print(f"Connecting to {address}...")
    async with HueBulb(address) as bulb:
        if await bulb.set_brightness(level):
            print(f"Brightness set to {level}%")
            return 0
        print("Failed to set brightness")
        return 1


async def cmd_status(args) -> int:
    address = get_address(args)
    if not address:
        return 1

    result = await try_daemon_command({"cmd": "connect", "address": address})
    if result and result.get("ok"):
        result = await try_daemon_command({"cmd": "status"})
        if result and result.get("ok"):
            print(f"\nBulb Status (via daemon):")
            print(f"  Power:      {result['power'].upper()}")
            print(f"  Brightness: {result['brightness']}%")
            return 0

    print(f"Connecting to {address}...")
    async with HueBulb(address) as bulb:
        state = await bulb.get_state()
        if state:
            print(f"\nBulb Status:")
            print(f"  Power:      {state['power'].upper()}")
            print(f"  Brightness: {state['brightness']}%")
            return 0
        print("Failed to read bulb status")
        return 1


async def cmd_daemon(args) -> int:
    """Manage the daemon."""
    from daemon import HueDaemon, send_command, is_daemon_running

    if args.daemon_cmd == "start":
        if is_daemon_running():
            print("Daemon already running")
            return 0
        print("Starting daemon...")
        daemon = HueDaemon()
        try:
            await daemon.start()
        except KeyboardInterrupt:
            await daemon.stop()
        return 0

    elif args.daemon_cmd == "stop":
        result = await send_command({"cmd": "shutdown"})
        if result.get("ok"):
            print("Daemon stopped")
            return 0
        print(f"Error: {result.get('error', 'Daemon not running')}")
        return 1

    elif args.daemon_cmd == "status":
        if is_daemon_running():
            result = await send_command({"cmd": "ping"})
            if result.get("connected"):
                print("Daemon: running, bulb: connected")
            else:
                print("Daemon: running, bulb: not connected")
        else:
            print("Daemon: not running")
        return 0

    return 1


def get_address(args) -> str | None:
    if args.address:
        return args.address
    config = load_config()
    if "last_address" in config:
        return config["last_address"]
    print("No bulb address. Run 'python cli.py scan' first.")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Control Philips Hue bulbs over Bluetooth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py scan                Find nearby bulbs
  python cli.py on                  Turn on
  python cli.py off                 Turn off
  python cli.py brightness 50       Set to 50%
  python cli.py daemon start        Start daemon for fast commands

Tip: Start the daemon for instant commands (no reconnection delay).
        """
    )

    parser.add_argument("--address", "-a", help="Bluetooth address of the bulb")

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Scan
    scan_parser = subparsers.add_parser("scan", help="Scan for Hue bulbs")
    scan_parser.add_argument("--timeout", "-t", type=float, default=5.0)

    # On/Off/Status
    subparsers.add_parser("on", help="Turn bulb on")
    subparsers.add_parser("off", help="Turn bulb off")
    subparsers.add_parser("status", help="Get bulb status")

    # Brightness
    brightness_parser = subparsers.add_parser("brightness", help="Set brightness")
    brightness_parser.add_argument("level", type=int, help="1-100")

    # Daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage daemon")
    daemon_parser.add_argument("daemon_cmd", choices=["start", "stop", "status"])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "scan": cmd_scan,
        "on": cmd_on,
        "off": cmd_off,
        "brightness": cmd_brightness,
        "status": cmd_status,
        "daemon": cmd_daemon,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return asyncio.run(cmd_func(args))
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
