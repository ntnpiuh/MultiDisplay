"""Protocol error definitions."""


class ProtocolError(Exception):
    """Base exception for protocol errors."""
    
    def __init__(self, message: str = "Protocol error occurred"):
        self.message = message
        super().__init__(message)


class FrameParseError(ProtocolError):
    """Raised when a frame cannot be parsed correctly."""
    
    def __init__(self, raw_data: bytes = b'', position: int = 0):
        self.raw_data = raw_data[:64] if len(raw_data) > 64 else raw_data
        self.position = position
        message = f"Failed to parse frame at pos {position}: {raw_data.hex()[:32]}"
        super().__init__(message)


class ConnectionError(ProtocolError):
    """Raised on connection/transport errors."""
    
    def __init__(self, host: str = "", port: int = 0, message: str = ""):
        loc = f"{host}:{port}" if host else str(message)
        super().__init__(f"Connection failed at {loc}")


class FrameBufferError(ProtocolError):
    """Raised when frame buffering fails."""
    
    def __init__(self, expected_size: int = 0, actual_size: int = 0):
        message = f"Mismatched size: expected={expected_size}, got={actual_size}"
        super().__init__(message)
