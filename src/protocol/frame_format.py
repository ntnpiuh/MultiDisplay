"""Frame format definitions - binary structure for screen frames."""

from enum import IntEnum, Flag
import struct


class FrameType(IntEnum):
    """Types of frames transmitted over the protocol."""
    VIDEO = 0x01       # H.264 video frame (NALU)
    AUDIO = 0x02       # AAC audio stream (raw frames)
    METADATA = 0x03    # Metadata: resolution, FPS, codec info
    ACK = 0x04         # Acknowledgment for flow control
    HEARTBEAT = 0x05   # Keep-alive ping
    CONTROL = 0x06     # Control messages (resize, pause, etc.)


class CodecId(IntEnum):
    """Supported video codec identifiers."""
    H264 = 100
    HEVC_H265 = 101
    VP8 = 102
    VP9 = 103
    AV1 = 104


class FrameHeader:
    """
    Binary frame header: 20 bytes

    offset  size  field
    ------  ----  -----
    0       4     magic (0x54537249 = 'TSRI' - MultiDisplay signature)
    4       4     sequence number (uint32)
    8       4     frame type (uint32)
    12      4     payload length (uint32)
    16      4     codec_id (uint32)
    """

    MAGIC = b'TSRI'

    @classmethod
    def from_bytes(cls, data: bytes):
        """Parse frame header from raw bytes."""
        if len(data) < 20:
            raise FrameFormatError("Header too short")

        magic_bytes = data[:4]
        if magic_bytes != cls.MAGIC:
            raise FrameFormatError(f"Invalid magic bytes: {magic_bytes!r}")

        seq_num, frame_type, payload_length, codec_id = struct.unpack_from('!IIII', data, 4)

        return FrameHeader(
            magic=cls.MAGIC,
            sequence_number=seq_num,
            frame_type=frame_type,
            payload_length=payload_length,
            codec_id=codec_id,
        )

    def __init__(self, magic: bytes, sequence_number: int, frame_type: int,
                 payload_length: int, codec_id: int):
        self.magic = magic
        self.sequence_number = sequence_number
        self.frame_type = frame_type
        self.payload_length = payload_length
        self.codec_id = codec_id

    def to_bytes(self) -> bytes:
        """Convert header back to raw bytes."""
        return struct.pack(
            '!IIII',
            int.from_bytes(self.magic, 'big'),
            self.sequence_number,
            self.frame_type,
            self.payload_length,
        ) + struct.pack('!I', self.codec_id)


class FrameFormatError(Exception):
    """Raised when frame format is invalid or parsing fails."""

# Constants for compression levels
COMPRESSION_LEVELS = [0, 1, 2, 3]  # 0=none, 1-3=increasing quality/speed tradeoff
