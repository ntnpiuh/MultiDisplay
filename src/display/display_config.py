"""Display configuration data structures."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RefreshRate(Enum):
    """Supported refresh rates for virtual displays."""
    HZ_30 = 30
    HZ_60 = 60
    HZ_90 = 90
    HZ_120 = 120


@dataclass
class MonitorInfo:
    """Information about a physical or virtual monitor."""
    
    width: int
    height: int
    pixel_size_x: int = 1
    pixel_size_y: int = 1
    is_physical: bool = False
    refresh_rate: RefreshRate = RefreshRate.HZ_60
    
    @property
    def physical_pixel_width(self) -> int:
        """Physical pixel width (for HiDPI displays)."""
        return self.width * self.pixel_size_x
    
    @property
    # Pixel height for HiDPI displays.
    def physical_pixel_height(self) -> int:
        return self.height * self.pixel_size_y


@dataclass
class DisplayConfig:
    """Configuration for a virtual display."""
    
    name: str = "MultiDisplay Virtual"
    width: int = 1920
    height: int = 1080
    refresh_rate: RefreshRate = RefreshRate.HZ_60
    pixel_scale: float = 1.0
    position: Optional[tuple[int, int]] = None  # (x, y) offset
    
    @property
    def physical_width(self) -> int:
        return int(self.width * self.pixel_scale)
    
    @property
    def physical_height(self) -> int:
        return int(self.height * self.pixel_scale)


class DisplayType(Enum):
    """Types of display configurations."""
    VIRTUAL = "virtual"      # Created via CoreDisplay API
    MIRROR = "mirror"       # Mirrors an existing display
    EXTENDED = "extended"   # Extends the primary display
