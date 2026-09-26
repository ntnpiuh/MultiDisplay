"""MultiDisplay Receiver - Receives screen frames and renders as virtual displays."""

try:
    from .display_manager import DisplayManager
    from .receiver_client import ReceiverClient
except ImportError:  # pragma: no cover - fallback for direct src execution
    from display.display_manager import DisplayManager
    from receiver.receiver_client import ReceiverClient

__all__ = ["DisplayManager", "ReceiverClient"]
