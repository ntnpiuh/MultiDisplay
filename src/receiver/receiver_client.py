"""
Receiver Client - Receives screen frames and renders them as virtual displays.

This module handles:
1. Network reception of screen frames (TCP socket)
2. Frame decoding (JPEG/RAW/H.264)
3. Display rendering on macOS virtual monitors
4. Input handling (mouse/touch from receiver back to sender)
"""

import socket
import struct
import threading
import time
from typing import Optional, Callable, Dict
from dataclasses import dataclass
from enum import Enum

try:
    from ..protocol.frame_format import FrameType, CodecId
    from ..protocol.error import ProtocolError
except ImportError:  # pragma: no cover - fallback for direct src execution
    from protocol.frame_format import FrameType, CodecId
    from protocol.error import ProtocolError


class ReceiverState(Enum):
    """States of the receiver."""
    IDLE = "idle"
    CONNECTING = "connecting"
    RECEIVING = "receiving"
    RENDERING = "rendering"
    STOPPED = "stopped"


@dataclass
class ConnectionInfo:
    """Information about an established connection to a sender."""
    host: str
    port: int
    frame_rate: float = 30.0
    codec_id: CodecId = CodecId.H264
    connected_at: float = time.time()


class ReceiverClient:
    """
    Client-side receiver that connects to a screen sender and renders frames.
    
    Usage:
        receiver = ReceiverClient(host='127.0.0.1', port=51821)
        receiver.connect()
        
        # The receiver will automatically start receiving and rendering
        
        receiver.stop()
    """
    
    def __init__(
        self, 
        host: str = '0.0.0.0', 
        port: int = 51821,
        display_manager=None,
        on_frame_received: Optional[Callable[[bytes], None]] = None
    ):
        self.host = host
        self.port = port
        self.display_manager = display_manager
        
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.state = ReceiverState.IDLE
        
        self.connections: Dict[str, ConnectionInfo] = {}
        
        # Frame processing callback (optional - allows custom rendering)
        self.on_frame_received = on_frame_received
    
    def connect(self) -> bool:
        """Connect to the sender and start receiving frames."""
        if self.running:
            return False

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # Connection timeout

            self.socket.connect((self.host, self.port))
            self.running = True
            self.state = ReceiverState.CONNECTING

            # Start the receive thread in background
            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()

            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            self.state = ReceiverState.STOPPED
            return False
    
    def _receive_loop(self):
        """Main receive loop - reads frames from socket."""
        
        buffer = b''
        
        while self.running and self.socket:
            try:
                # Read available data
                chunk = self.socket.recv(65536)
                if not chunk:
                    break
                
                buffer += chunk
                
                # Process complete frames
                while len(buffer) > 40:  # Minimum frame size (header + padding)
                    try:
                        frame_bytes = self._extract_frame_from_buffer(buffer)
                        if frame_bytes is None:
                            break
                        
                        # Parse and process frame
                        self._process_frame(frame_bytes)
                        
                        buffer = buffer[len(frame_bytes):]
                    
                    except ProtocolError as e:
                        print(f"Frame processing error: {e}")
                        # Skip malformed frames
                        break
                
                if not chunk:  # Connection closed
                    break
                    
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Receive loop error: {e}")
                break
        
        self._cleanup()
    
    def _extract_frame_from_buffer(self, buffer: bytes) -> Optional[bytes]:
        """Extract a full frame from the receive buffer based on the 20-byte header."""
        if len(buffer) < 20:
            return None

        try:
            magic = buffer[:4]
            if magic != b'TSRI':
                raise ProtocolError(f"Invalid frame magic: {magic!r}")

            seq_num, frame_type, payload_length, codec_id = struct.unpack_from('!IIII', buffer, 4)
            frame_end = 20 + payload_length
            if len(buffer) < frame_end:
                return None

            return buffer[:frame_end]
        except (struct.error, ValueError, ProtocolError) as e:
            print(f"Frame parsing error: {e}")
            return None

    def _process_frame(self, frame_data: bytes):
        """Process a received frame."""
        try:
            magic = frame_data[:4]
            if magic != b'TSRI':
                raise ProtocolError(f"Invalid frame magic: {magic!r}")

            seq_num, frame_type, payload_length, codec_id = struct.unpack_from('!IIII', frame_data, 4)
            if frame_type == FrameType.VIDEO:
                self._handle_video_frame(frame_data, len(frame_data))
            elif frame_type == FrameType.AUDIO:
                self._handle_audio_frame(frame_data)
            elif frame_type == FrameType.HEARTBEAT:
                pass
            else:
                print(f"Unknown frame type: {frame_type}")
        except Exception as e:
            print(f"Error processing frame: {e}")

    def _handle_video_frame(self, frame_data: bytes, total_length: int):
        """Handle a video frame."""
        payload = frame_data[20:]

        if self.on_frame_received:
            self.on_frame_received(payload)
    
    def _handle_audio_frame(self, frame_data: bytes):
        """Handle an audio frame."""
        pass  # Audio handling would go here
    
    def stop(self):
        """Stop receiving frames and close connections."""
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
        
        self.state = ReceiverState.STOPPED
    
    def _cleanup(self):
        """Cleanup resources."""
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
        
        self.state = ReceiverState.STOPPED
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class InputHandler:
    """Handles input from receiver devices (mouse/touch/keyboard) back to the Mac."""

    def __init__(self, host: str = '127.0.0.1', port: int = 51822):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None

    def start(self):
        """Start listening for input events."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)
        threading.Thread(target=self._listen_for_input, daemon=True).start()

    def _listen_for_input(self):
        """Listen for input events from the receiver device."""
        while True:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                event = data.decode('utf-8', errors='replace')
                try:
                    payload = __import__('json').loads(event)
                    self.handle_input_event(payload)
                except Exception:
                    pass
            except socket.timeout:
                continue

    def handle_input_event(self, payload):
        """Translate a parsed event into a native macOS CoreGraphics input event."""
        if not isinstance(payload, dict):
            raise ValueError('Input event payload must be a JSON object')

        event_type = str(payload.get('type', '')).strip()
        if not event_type:
            raise ValueError('Input event is missing a type')

        try:
            import Quartz.CoreGraphics as cg
        except Exception:
            return False

        x = float(payload.get('x', 0.0))
        y = float(payload.get('y', 0.0))
        width = float(payload.get('width', 0.0) or 1.0)
        height = float(payload.get('height', 0.0) or 1.0)

        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            x *= max(width, 1.0)
            y *= max(height, 1.0)

        if event_type in {'touch_down', 'touch_move', 'mouse_move'}:
            event = cg.CGEventCreateMouseEvent(
                None,
                cg.kCGEventMouseMoved if event_type != 'touch_down' else cg.kCGEventLeftMouseDown,
                (x, y),
                cg.kCGMouseButtonLeft,
            )
            if event is not None:
                cg.CGEventPost(cg.kCGHIDEventTap, event)
            return True

        if event_type in {'touch_up', 'mouse_click'}:
            event = cg.CGEventCreateMouseEvent(
                None,
                cg.kCGEventLeftMouseUp,
                (x, y),
                cg.kCGMouseButtonLeft,
            )
            if event is not None:
                cg.CGEventPost(cg.kCGHIDEventTap, event)
            return True

        if event_type == 'mouse_wheel':
            dx = float(payload.get('delta_x', 0.0))
            dy = float(payload.get('delta_y', 0.0))
            scroll_event = cg.CGEventCreateScrollWheelEvent(None, cg.kCGScrollEventUnitPixel, 2, int(dy), int(dx))
            if scroll_event is not None:
                cg.CGEventPost(cg.kCGHIDEventTap, scroll_event)
            return True

        if event_type in {'key_down', 'key_up'}:
            key_code = int(payload.get('key_code', 0) or 0)
            if key_code == 0:
                key = str(payload.get('key', ''))
                if key and len(key) == 1:
                    key_code = ord(key.upper())
            if key_code:
                event = cg.CGEventCreateKeyboardEvent(None, key_code, event_type == 'key_down')
                if event is not None:
                    cg.CGEventPost(cg.kCGHIDEventTap, event)
            return True

        return False
