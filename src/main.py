"""MultiDisplay - Turn smartphones into virtual displays for macOS."""

import argparse
import time
from typing import Optional

try:
    from .protocol.frame_format import FrameType, CodecId
    from .display.display_manager import DisplayManager
    from .receiver.receiver_client import ReceiverClient
    from .multidisplay.web_app import run_dashboard
except ImportError:  # pragma: no cover - supports direct script execution
    from protocol.frame_format import FrameType, CodecId
    from display.display_manager import DisplayManager
    from receiver.receiver_client import ReceiverClient
    from multidisplay.web_app import run_dashboard


def run_sender(host: str = '0.0.0.0', port: int = 51820):
    """Run the screen sender (captures and streams your display)."""
    print(f"Starting MultiDisplay Sender on {host}:{port}")
    print("Press Ctrl+C to stop.")

    display_manager = DisplayManager()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nSender stopped.")


def run_receiver(host: str = '0.0.0.0', port: int = 51821):
    """Run the screen receiver (receives and renders frames)."""
    print(f"Starting MultiDisplay Receiver on {host}:{port}")
    print("Press Ctrl+C to stop.")

    display_manager = DisplayManager()

    with ReceiverClient(host=host, port=port) as receiver:
        receiver.connect()

        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nReceiver stopped.")


def main():
    """Main entry point for MultiDisplay."""
    parser = argparse.ArgumentParser(description="MultiDisplay - Screen sharing tool")
    subparsers = parser.add_subparsers(dest='command')

    sender_parser = subparsers.add_parser('send', help='Capture and stream your display')
    sender_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    sender_parser.add_argument('--port', type=int, default=51820, help='Port to listen on (default: 51820)')

    receiver_parser = subparsers.add_parser('receive', help='Receive and render screen frames')
    receiver_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    receiver_parser.add_argument('--port', type=int, default=51821, help='Port to listen on (default: 51821)')

    dashboard_parser = subparsers.add_parser('dashboard', help='Open the local control dashboard')
    dashboard_parser.add_argument('--host', default='127.0.0.1', help='Dashboard bind host (default: 127.0.0.1)')
    dashboard_parser.add_argument('--port', type=int, default=8765, help='Dashboard port (default: 8765)')

    subparsers.add_parser('list', help='List all available displays')

    args = parser.parse_args()

    if args.command == 'send':
        run_sender(host=args.host, port=args.port)
    elif args.command == 'receive':
        run_receiver(host=args.host, port=args.port)
    elif args.command == 'dashboard':
        run_dashboard(host=args.host, port=args.port)
    elif args.command == 'list':
        display_manager = DisplayManager()
        monitors = display_manager.list_displays()

        print(f"Found {len(monitors)} displays:")
        for i, monitor in enumerate(monitors):
            print(f"  [{i}] {monitor.width}x{monitor.height} @ {monitor.refresh_rate}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
