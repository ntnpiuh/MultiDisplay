"""Display module - Manages virtual displays on macOS."""

from .display_manager import DisplayManager
from .display_config import DisplayConfig, DisplayType, MonitorInfo

__all__ = ["DisplayManager", "DisplayConfig", "DisplayType", "MonitorInfo"]
