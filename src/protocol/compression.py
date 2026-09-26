"""Frame compression for the legacy binary protocol."""

import zlib

from .error import ProtocolError


class CompressionLevel(int):
    """Compression speed vs quality tradeoff (0=none, 3=highest)."""
    NONE = 0
    LOW = 1      # Fast, lower quality
    MEDIUM = 2   # Balanced
    HIGH = 3     # Slow, highest quality


def compress_frame(
    frame_data: bytes,
    codec_id: int,
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
) -> tuple[int, bytes]:
    """
    Compress video/audio frame data.
    
    Returns:
        Tuple of (compressed_size_in_bytes, compressed_data)
    """
    if compression_level == CompressionLevel.NONE:
        return len(frame_data), frame_data
    
    # For H.264/HEVC, use zlib with appropriate compression level
    # In a real implementation, this would call FFmpeg via subprocess or libav
    if compression_level == CompressionLevel.LOW:
        return _compress(frame_data, 1)
    elif compression_level == CompressionLevel.MEDIUM:
        return _compress(frame_data, 6)
    else:  # HIGH
        return _compress(frame_data, 9)


def decompress_frame(
    compressed_data: bytes, 
    expected_size: int = None
) -> bytes:
    """Decompress frame data back to original."""
    try:
        if len(compressed_data) > 256 * 1024:  # Safety limit
            raise OverflowError("Compressed data too large")
        
        # Try zlib decompression first (for our simple compression path)
        return zlib.decompress(compressed_data, w=-15)
    except Exception as e:
        # If not zlib-compressed, return as-is (pass-through for uncompressed streams)
        if expected_size and len(compressed_data) == expected_size:
            return compressed_data
        raise ProtocolError(f"Decompression failed: {e}")


def _compress(data: bytes, level: int = 6) -> bytes:
    """Internal zlib compression wrapper."""
    # -15 indicates zlib format (no zlib header), for raw NALU data
    return zlib.compress(data, w=-15, level=level)
