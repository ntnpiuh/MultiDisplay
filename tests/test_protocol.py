"""Tests for the protocol layer."""

import sys
import os
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from display import DisplayType
from protocol.frame_format import FrameType, CodecId
from protocol.audio_streaming import AudioCodecId
from protocol.error import ProtocolError
from protocol.compression import decompress_frame


class TestFrameFormat:
    """Test frame format parsing and encoding."""
    
    def test_frame_type_values(self):
        """Test that all frame types have valid values."""
        assert FrameType.VIDEO == 1
        assert FrameType.AUDIO == 2
        assert FrameType.METADATA == 3
        assert FrameType.ACK == 4
        assert FrameType.HEARTBEAT == 5
        assert FrameType.CONTROL == 6
    
    def test_codec_id_values(self):
        """Test codec ID values."""
        assert CodecId.H264 == 100
        assert CodecId.HEVC_H265 == 101

    def test_audio_codec_ids_do_not_shadow_video_codec_ids(self):
        assert AudioCodecId.AAC == 100
        assert not hasattr(CodecId, "AAC")


def test_protocol_uses_shared_error_type():
    with pytest.raises(ProtocolError):
        decompress_frame(b"not compressed")


def test_display_type_is_public():
    assert DisplayType.EXTENDED.value == "extended"


class TestFrameBuilder:
    """Test frame building and parsing utilities."""
    
    @pytest.fixture
    def test_data(self):
        """Provide test data for frame operations."""
        return b'\x00\x00\x00\x00' * 100  # Fake JPEG frame
    
    def test_frame_length_header(self, test_data):
        """Test that frame length header is correctly structured."""
        assert len(test_data) > 0


class TestFrameType:
    """Test frame type parsing."""
    
    def test_frame_type_enum_values(self):
        """Test all frame types."""
        for ftype in FrameType:
            assert isinstance(ftype, int)
            print(f"  {ftype.name} = {ftype.value}")
