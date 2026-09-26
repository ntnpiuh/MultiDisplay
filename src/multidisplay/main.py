"""Command-line entry point for MultiDisplay."""

import argparse
import sys

from display.display_manager import DisplayManager
from multidisplay.web_app import run_dashboard


def run_sender(host: str = "0.0.0.0", port: int = 51820) -> None:
    """Run the control dashboard, virtual display backend, and phone stream."""
    run_dashboard(receiver_host=host, receiver_port=port)


def main() -> None:
    """Main entry point for MultiDisplay."""
    parser = argparse.ArgumentParser(description="MultiDisplay - Screen sharing tool")
    subparsers = parser.add_subparsers(dest="command")

    sender_parser = subparsers.add_parser("send", help="Capture and stream your display")
    sender_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    sender_parser.add_argument("--port", type=int, default=51820, help="Port to listen on (default: 51820)")

    dashboard_parser = subparsers.add_parser("dashboard", help="Open the local control dashboard")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Dashboard bind host (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=8765, help="Dashboard port (default: 8765)")
    dashboard_parser.add_argument("--receiver-host", default="0.0.0.0", help="Phone receiver bind host (default: 0.0.0.0)")
    dashboard_parser.add_argument("--receiver-port", type=int, default=51820, help="Phone receiver port (default: 51820)")
    dashboard_parser.add_argument("--browser", action="store_true", help="Serve the dashboard without opening a native window")

    subparsers.add_parser("list", help="List all available displays")

    args = parser.parse_args()
    if args.command == "send":
        run_sender(host=args.host, port=args.port)
    elif args.command == "dashboard":
        run_dashboard(host=args.host, port=args.port, receiver_host=args.receiver_host, receiver_port=args.receiver_port, native=not args.browser)
    elif args.command == "list":
        monitors = DisplayManager().list_displays()
        print(f"Found {len(monitors)} displays:")
        for i, monitor in enumerate(monitors):
            print(f"  [{i}] {monitor.width}x{monitor.height} @ {monitor.refresh_rate.value} Hz")
    else:
        run_dashboard(native=sys.platform == "darwin")
