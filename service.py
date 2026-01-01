"""
Cross-platform service manager for the Hue daemon.

Windows: Runs as a Windows Service
Linux: Creates a systemd user service
"""

import asyncio
import sys
import platform
from pathlib import Path

SYSTEM = platform.system()


def get_python_path() -> str:
    return sys.executable


def get_daemon_path() -> str:
    return str(Path(__file__).parent / "daemon.py")


# ============== Windows Service ==============

HAS_WIN32 = False

if SYSTEM == "Windows":
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager
        HAS_WIN32 = True
    except ImportError:
        pass


if HAS_WIN32:
    class HueService(win32serviceutil.ServiceFramework):
        _svc_name_ = "HueBLEDaemon"
        _svc_display_name_ = "Philips Hue Bluetooth Daemon"
        _svc_description_ = "Maintains persistent BLE connection to Philips Hue bulbs"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.daemon = None
            self._loop = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            if self._loop and self.daemon:
                self._loop.call_soon_threadsafe(self._loop.stop)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            self.main()

        def main(self):
            # Import here to avoid issues at service registration time
            from daemon import HueDaemon

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self.daemon = HueDaemon()

            try:
                self._loop.run_until_complete(self.daemon.start())
            except Exception as e:
                servicemanager.LogErrorMsg(f"Daemon error: {e}")
            finally:
                self._loop.close()


def run_windows_service_command():
    """Use HandleCommandLine for all Windows service operations."""
    if not HAS_WIN32:
        print("Windows service support requires pywin32.")
        print("Install with: pip install pywin32")
        return

    # Map our simple commands to pywin32's expected args
    script_path = str(Path(__file__).resolve())
    if len(sys.argv) >= 2:
        cmd_map = {
            "install": [script_path, "install"],
            "uninstall": [script_path, "remove"],
            "start": [script_path, "start"],
            "stop": [script_path, "stop"],
            "restart": [script_path, "restart"],
            "debug": [script_path, "debug"],
        }
        cmd = sys.argv[1]
        if cmd in cmd_map:
            sys.argv = cmd_map[cmd]

    win32serviceutil.HandleCommandLine(HueService)


# ============== Linux Systemd Service ==============

SYSTEMD_UNIT = """[Unit]
Description=Philips Hue Bluetooth Daemon
After=bluetooth.target

[Service]
Type=simple
ExecStart={python} {daemon}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def get_systemd_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / "hue-ble.service"


def install_linux_service():
    """Install as systemd user service."""
    unit_path = get_systemd_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)

    content = SYSTEMD_UNIT.format(
        python=get_python_path(),
        daemon=get_daemon_path()
    )
    unit_path.write_text(content)

    print(f"Service installed to {unit_path}")
    print("Enable with: systemctl --user enable hue-ble")
    print("Start with:  systemctl --user start hue-ble")
    return True


def uninstall_linux_service():
    """Uninstall systemd user service."""
    unit_path = get_systemd_path()
    if unit_path.exists():
        unit_path.unlink()
        print("Service uninstalled.")
        print("Run: systemctl --user daemon-reload")
        return True
    print("Service not installed.")
    return False


# ============== Main ==============

def print_usage():
    print("""
Hue BLE Service Manager

Usage:
    python service.py install     Install as system service
    python service.py uninstall   Remove system service
    python service.py start       Start the service
    python service.py stop        Stop the service
    python service.py debug       Run in foreground (debug mode)

On Windows, this creates a Windows Service (requires Admin).
On Linux, this creates a systemd user service.
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    cmd = sys.argv[1]

    if SYSTEM == "Windows":
        if cmd in ("install", "uninstall", "start", "stop", "restart", "debug"):
            run_windows_service_command()
        else:
            print_usage()

    elif SYSTEM == "Linux":
        import subprocess
        if cmd == "install":
            install_linux_service()
        elif cmd == "uninstall":
            uninstall_linux_service()
        elif cmd == "start":
            subprocess.run(["systemctl", "--user", "start", "hue-ble"])
        elif cmd == "stop":
            subprocess.run(["systemctl", "--user", "stop", "hue-ble"])
        elif cmd == "debug":
            # Run daemon directly in foreground
            subprocess.run([get_python_path(), get_daemon_path(), "start"])
        else:
            print_usage()

    else:
        print(f"Unsupported platform: {SYSTEM}")
        print("Use 'python cli.py daemon start' to run manually.")


if __name__ == "__main__":
    main()
