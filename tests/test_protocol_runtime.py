from protocol.frame_format import FrameHeader, FrameType, CodecId
from receiver.receiver_client import ReceiverClient


def test_frame_header_round_trip():
    header = FrameHeader(
        magic=b"TSRI",
        sequence_number=7,
        frame_type=FrameType.VIDEO,
        payload_length=5,
        codec_id=CodecId.H264,
    )

    decoded = FrameHeader.from_bytes(header.to_bytes())

    assert decoded.magic == b"TSRI"
    assert decoded.sequence_number == 7
    assert decoded.frame_type == FrameType.VIDEO
    assert decoded.payload_length == 5
    assert decoded.codec_id == CodecId.H264


def test_receiver_extracts_complete_frame():
    receiver = ReceiverClient(host="127.0.0.1", port=9000)
    payload = b"hello"
    frame = FrameHeader(
        magic=b"TSRI",
        sequence_number=3,
        frame_type=FrameType.VIDEO,
        payload_length=len(payload),
        codec_id=CodecId.H264,
    ).to_bytes() + payload

    assert receiver._extract_frame_from_buffer(frame) == frame
