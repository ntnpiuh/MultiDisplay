"""MultiDisplay Protocol - Binary framing protocol for screen sharing."""

__version__ = "1.0.0"

from .frame_format import FrameHeader, FrameType, CodecId
from .compression import compress_frame, decompress_frame, CompressionLevel
from .error import ProtocolError, FrameParseError


__all__ = [
    "FrameHeader",
    "FrameType",
    "CodecId",
    "compress_frame",
    "decompress_frame",
    "CompressionLevel",
    "ProtocolError",
    "FrameParseError",
]
