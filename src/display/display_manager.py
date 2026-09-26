"""Physical and virtual display management for macOS.

Virtual display creation uses Apple's private ``CGVirtualDisplay`` API via
PyObjC. That API is not App Store compatible and can change between macOS
releases. On other platforms this module can still be imported, but it does
not report fabricated monitors or pretend display creation succeeded.
"""

import sys
import uuid
from typing import Dict, List, Optional

from .display_config import DisplayConfig, MonitorInfo, RefreshRate


class DisplayBackendError(RuntimeError):
    """Raised when the host cannot create or manage virtual displays."""


class DisplayManager:
    """Manage actual CoreGraphics displays and retained virtual display objects."""

    def __init__(self):
        self._virtual_displays: Dict[int, object] = {}
        self._configs: Dict[int, DisplayConfig] = {}
        self._cg = None
        self._virtual_api = None

        if sys.platform == "darwin":
            try:
                import Quartz.CoreGraphics as cg

                required = (
                    "CGVirtualDisplayDescriptor",
                    "CGVirtualDisplay",
                    "CGVirtualDisplaySettings",
                    "CGVirtualDisplayMode",
                )
                if not all(hasattr(cg, name) for name in required):
                    raise DisplayBackendError(
                        "This macOS version does not expose the CGVirtualDisplay API"
                    )
                self._cg = cg
                self._virtual_api = tuple(getattr(cg, name) for name in required)
            except ImportError as error:
                raise DisplayBackendError(
                    "Virtual displays require PyObjC Quartz. Install the project dependencies."
                ) from error

    def create_virtual_display(self, config: Optional[DisplayConfig] = None) -> int:
        """Create a real macOS virtual monitor and return its CoreGraphics ID."""
        if sys.platform != "darwin" or self._cg is None or self._virtual_api is None:
            raise DisplayBackendError(
                "Virtual display creation is supported only on macOS with CGVirtualDisplay available."
            )
        config = config or DisplayConfig()
        width, height = int(config.width), int(config.height)
        if width < 320 or height < 240:
            raise ValueError("Virtual display dimensions must be at least 320×240")
        if config.refresh_rate not in (RefreshRate.HZ_30, RefreshRate.HZ_60, RefreshRate.HZ_90, RefreshRate.HZ_120):
            raise ValueError("Supported virtual display refresh rates are 30, 60, 90, and 120 Hz")

        Descriptor, VirtualDisplay, Settings, Mode = self._virtual_api
        descriptor = Descriptor.alloc().init()
        descriptor.setName_(config.name or "MultiDisplay")
        # CGVirtualDisplay's mode API takes logical points; advertise twice
        # the requested raster and enable HiDPI to get the exact pixel size.
        points_wide, points_high = width // 2, height // 2
        if width % 2 or height % 2:
            raise ValueError("Virtual display pixel dimensions must be even for HiDPI mode")
        descriptor.setMaxPixelsWide_(width)
        descriptor.setMaxPixelsHigh_(height)
        descriptor.setSizeInMillimeters_((300.0, 170.0))
        descriptor.setVendorID_(0x4D44)  # "MD"
        descriptor.setProductID_(1)
        # Stable within this display object's lifetime, distinct across active
        # displays, and independent of list position or removal order.
        serial = uuid.uuid4().int & 0xFFFFFFFF
        descriptor.setSerialNum_(serial or 1)
        # If available, set perspective/to-virtual to ensure the display is treated
        # as an extended desktop rather than a mirror of the built-in display.
        if hasattr(descriptor, "setPerspective_"):
            descriptor.setPerspective_((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0))
        if hasattr(descriptor, "setToVirtual_"):
            descriptor.setToVirtual_(True)

        try:
            display = VirtualDisplay.alloc().initWithDescriptor_(descriptor)
            settings = Settings.alloc().init()
            settings.setHiDPI_(1)
            if config.position is not None and hasattr(settings, "setOrigin_"):
                settings.setOrigin_(tuple(config.position))
            settings.setModes_([Mode.alloc().initWithWidth_height_refreshRate_(
                points_wide, points_high, float(config.refresh_rate.value)
            )])
            if display is None or not display.applySettings_(settings):
                if not self._cg.CGGetActiveDisplayList(1, None, None)[2]:
                    raise DisplayBackendError(
                        "macOS currently exposes no displays to this process. Run MultiDisplay from a logged-in desktop session."
                    )
                raise DisplayBackendError(
                    "macOS rejected the virtual display mode. CGVirtualDisplay is a private API and can vary by macOS version."
                )
            display_id = int(display.displayID())
        except DisplayBackendError:
            raise
        except Exception as error:
            raise DisplayBackendError(f"Could not create a macOS virtual display: {error}") from error

        self._virtual_displays[display_id] = display
        self._configs[display_id] = config
        return display_id

    def list_displays(self) -> List[MonitorInfo]:
        """Return the active displays reported by CoreGraphics."""
        if self._cg is None:
            return []

        cg = self._cg
        status, display_ids, count = cg.CGGetActiveDisplayList(64, None, None)
        if status != 0:
            raise DisplayBackendError(f"Could not enumerate macOS displays (CoreGraphics {status})")

        monitors = []
        for display_id in display_ids[:count]:
            mode = cg.CGDisplayCopyDisplayMode(display_id)
            raw_refresh = cg.CGDisplayModeGetRefreshRate(mode) if mode else 0
            refresh = int(round(raw_refresh)) if raw_refresh else 60
            if refresh not in {30, 60, 90, 120}:
                refresh = min((30, 60, 90, 120), key=lambda candidate: abs(candidate - refresh))
            monitors.append(
                MonitorInfo(
                    width=int(cg.CGDisplayPixelsWide(display_id)),
                    height=int(cg.CGDisplayPixelsHigh(display_id)),
                    is_physical=display_id not in self._virtual_displays,
                    refresh_rate=RefreshRate(refresh),
                )
            )
        return monitors

    def configure_virtual_display(self, display_id: int, config: DisplayConfig) -> bool:
        """Apply a new mode to a virtual display managed by this process."""
        display = self._virtual_displays.get(display_id)
        if display is None:
            return False
        if self._virtual_api is None:
            return False
        _, _, Settings, Mode = self._virtual_api
        settings = Settings.alloc().init()
        if int(config.width) % 2 or int(config.height) % 2:
            raise ValueError("Virtual display pixel dimensions must be even for HiDPI mode")
        settings.setHiDPI_(1)
        if config.position is not None and hasattr(settings, "setOrigin_"):
            settings.setOrigin_(tuple(config.position))
        settings.setModes_([Mode.alloc().initWithWidth_height_refreshRate_(
            int(config.width) // 2, int(config.height) // 2, float(config.refresh_rate.value)
        )])
        if not display.applySettings_(settings):
            return False
        self._configs[display_id] = config
        return True

    def remove_virtual_display(self, display_id: int) -> bool:
        """Release a managed virtual display; macOS removes it from the desktop."""
        if display_id not in self._virtual_displays:
            return False
        display = self._virtual_displays[display_id]
        release = getattr(self._cg, "CGVirtualDisplayRelease", None) if self._cg is not None else None
        try:
            if callable(release):
                release(display)
            elif self._cg is not None and not getattr(self._cg, "__name__", "").startswith("Quartz"):
                # Test and alternate backends may expose only an object release hook.
                fallback_release = getattr(display, "release", None)
                if callable(fallback_release):
                    fallback_release()
        except Exception as error:
            raise DisplayBackendError(
                f"Could not release virtual display {display_id}: {error}"
            ) from error
        # Do not call NSObject.release() directly: PyObjC owns this wrapper.
        del self._virtual_displays[display_id]
        self._configs.pop(display_id, None)
        return True

    def get_active_displays(self) -> List[int]:
        """Return virtual display IDs created by this process."""
        return list(self._virtual_displays)
