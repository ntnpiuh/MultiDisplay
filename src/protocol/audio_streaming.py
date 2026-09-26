"""Audio stream encoding/decoding for the legacy binary protocol."""

from enum import IntEnum
from typing import Tuple


class AudioCodecId(IntEnum):
    """Supported audio codec identifiers."""
    AAC = 100     # Apple Advanced Audio Coding (48kHz)
    OPUS = 101     # Opus codec
    ALAC = 102     # Apple Lossless Audio
    AAC_LC = 103   # AAC-LC (used in screen sharing for lower bitrate)


# Compatibility alias for callers of the original audio module API.
CodecId = AudioCodecId


def encode_audio_frame(
    audio_data: bytes,
    codec_id: AudioCodecId = AudioCodecId.AAC_LC
) -> Tuple[int, bytes]:
    """
    Encode a single audio frame.
    
    Args:
        audio_data: Raw PCM or encoded audio data
        codec_id: Codec identifier
    
    Returns:
        (frame_length, encoded_frame_bytes)
    """
    # In real implementation: apply codec-specific encoding
    # For now, pass-through with length prefix
    return len(audio_data), audio_data


def decode_audio_frame(
    frame_data: bytes, 
    expected_size: int = None
) -> Tuple[int, bytes]:
    """
    Decode an audio frame.
    
    Args:
        frame_data: Encoded audio frame
        expected_size: Expected original size (optional)
    
    Returns:
        (original_length, decoded_audio_bytes)
    """
    # In real implementation: decode to PCM/audio stream
    return len(frame_data), frame_data
