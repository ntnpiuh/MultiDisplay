"""MJPEG transport for the mobile receiver.

This first transport is deliberately browser-native: Android Chrome can decode
the multipart JPEG stream without installing codecs or opening native sockets.
The same HTTP endpoint works over Wi-Fi and any USB network interface that
routes the phone to the Mac.
"""

import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import urlparse


class FrameStore:
    """Thread-safe latest-frame cache; slow receivers skip old frames."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frames: Dict[int, bytes] = {}

    def publish(self, display_id: int, jpeg: bytes) -> None:
        with self._lock:
            self._frames[display_id] = jpeg

    def get(self, display_id: int) -> Optional[bytes]:
        with self._lock:
            return self._frames.get(display_id)

    def remove(self, display_id: int) -> None:
        with self._lock:
            self._frames.pop(display_id, None)


class DisplayCapture:
    """Capture selected CoreGraphics display IDs to JPEG on a worker thread."""

    def __init__(self, display_id: int, frames: FrameStore, fps: int = 30, quality: int = 65):
        self.display_id = display_id
        self.frames = frames
        self.fps = max(1, min(fps, 30))
        self.quality = max(1, min(int(quality), 100))
        self.running = False
        self.error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def capture_jpeg(display_id: int, quality: int = 78) -> bytes:
        """Capture one screen image; requires macOS Screen Recording permission."""
        try:
            import AppKit
            import Quartz.CoreGraphics as cg
        except ImportError as error:
            raise RuntimeError("Screen capture requires the macOS PyObjC frameworks") from error

        image = None
        display_capture_error = None
        try:
            # The display framebuffer is the fast path. Window-list capture is
            # substantially more expensive and is only needed as a fallback.
            image = cg.CGDisplayCreateImage(display_id)
        except Exception as error:
            display_capture_error = error

        if image is None:
            try:
                create_window_image = getattr(cg, "CGWindowListCreateImage")
                bounds = cg.CGDisplayBounds(display_id)
                image = create_window_image(
                    bounds,
                    cg.kCGWindowListOptionOnScreenOnly | cg.kCGWindowListOptionIncludingWindow,
                    cg.kCGNullWindowID,
                    cg.kCGWindowImageDefault,
                )
            except Exception as error:
                display_capture_error = display_capture_error or error
            if image is None:
                details = ""
                if display_capture_error is not None:
                    details = f" Display/window capture failed: {display_capture_error}."
                raise RuntimeError(
                    "macOS returned no image for display "
                    f"{display_id}. Enable Screen Recording for MultiDisplay in System Settings."
                    f"{details}"
                )
        bitmap = AppKit.NSBitmapImageRep.alloc().initWithCGImage_(image)
        options = {AppKit.NSImageCompressionFactor: float(quality) / 100.0}
        data = bitmap.representationUsingType_properties_(AppKit.NSJPEGFileType, options)
        if data is None:
            raise RuntimeError("macOS could not encode the captured display as JPEG")
        return bytes(data)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, name=f"capture-{self.display_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.frames.remove(self.display_id)

    def _diagnose(self, error: Exception) -> str:
        """Augment capture errors with display state diagnostics."""
        try:
            import Quartz.CoreGraphics as cg
            status, display_ids, count = cg.CGGetActiveDisplayList(64, None, None)
            active_ids = set(display_ids[:count]) if status == 0 else set()
            display_id = int(self.display_id)
            details = []
            if status != 0:
                details.append(f"CGGetActiveDisplayList returned status {status}")
            if display_id in active_ids:
                details.append(f"display {display_id} is active in CoreGraphics")
            else:
                details.append(f"display {display_id} is NOT active in CoreGraphics")
            return f"{error}. Diagnostics: " + "; ".join(details)
        except Exception:
            return str(error)

    def _run(self) -> None:
        interval = 1.0 / self.fps
        while self.running:
            started = time.monotonic()
            try:
                self.frames.publish(self.display_id, self.capture_jpeg(self.display_id, self.quality))
                self.error = None
            except Exception as error:
                # Augment with diagnostics to debug "wallpaper only" cases
                # where the display ID is stale or the virtual display is gone.
                self.error = self._diagnose(error)
                # A missing Screen Recording grant should not busy-loop or kill
                # the service. A later settings change can make capture recover.
                time.sleep(min(2.0, interval * 4))
            else:
                time.sleep(max(0.0, interval - (time.monotonic() - started)))


RECEIVER_HTML = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#101714"><title>MultiDisplay Receiver</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101714;color:#eff4ee;font:16px system-ui,sans-serif;height:100dvh;display:grid;place-items:center}.pair{width:min(90vw,360px);text-align:center}.pair h1{font-size:1.5rem}.pair p{color:#aab8af}input,button{font:inherit;padding:14px;border-radius:10px;border:1px solid #53645a;width:100%;margin:6px 0}input{background:#1b2821;color:white;text-align:center;letter-spacing:.2em}button{background:#75dcaa;border:0;color:#102018;font-weight:700}#stage{display:none;position:relative;width:100vw;height:100dvh;overflow:hidden;touch-action:none}#screen{display:block;width:100%;height:100%;object-fit:fill;touch-action:none}#host-cursor{position:absolute;z-index:2;display:none;left:0;top:0;width:28px;height:36px;overflow:visible;pointer-events:none;filter:drop-shadow(1px 2px 2px #000)}body.connected{display:block}body.connected #stage{display:block}body.connected .pair{display:none}</style>
<section class="pair"><h1>Connect to your Mac</h1><p>Choose a virtual display and enter the pairing code shown in the Mac dashboard.</p><select id="display" aria-label="Virtual display"></select><form id="pair"><input inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="8-digit code" required><button>Connect</button></form><p id="error" role="status"></p></section><div id="stage"><img id="screen" alt="Extended Mac display"><svg id="host-cursor" aria-hidden="true" viewBox="0 0 28 36"><path d="M2 2v27l7-7 5 12 6-3-5-11h10z" fill="white" stroke="#111" stroke-width="2" stroke-linejoin="round"/></svg></div>
<script>
const params=new URLSearchParams(location.search),stage=document.querySelector('#stage'),img=document.querySelector('#screen'),hostCursor=document.querySelector('#host-cursor'),form=document.querySelector('#pair'),err=document.querySelector('#error'),picker=document.querySelector('#display'),connect=form.querySelector('button');let hostSize={width:1,height:1},pendingMove=null,moveTimer=0,cursorTimer=0,cursorPending=false;
async function loadDisplays(){
    try{const r=await fetch('/displays',{cache:'no-store'}),items=await r.json();picker.replaceChildren();items.forEach(d=>{const o=document.createElement('option');o.value=d.id;o.dataset.width=d.width;o.dataset.height=d.height;o.textContent=`${d.name} · ${d.width} × ${d.height}`;picker.append(o)});connect.disabled=!items.length;const id=params.get('display');if(id)picker.value=id;updateHostSize();if(!items.length)err.textContent='Create a virtual display on the Mac first.'}catch(_){connect.disabled=true;err.textContent='Could not load displays from the Mac.'}
}
function updateHostSize(){const option=picker.selectedOptions[0];hostSize={width:Number(option?.dataset.width)||1,height:Number(option?.dataset.height)||1}}
picker.addEventListener('change', updateHostSize);
function sendInput(type, detail = {}) {
  if (!document.body.classList.contains('connected')) return;
  const payload = Object.assign({type, width: hostSize.width, height: hostSize.height}, detail);
  if(type==='mouse_move'||type==='touch_move'){pendingMove=payload;if(!moveTimer)moveTimer=setTimeout(()=>{const latest=pendingMove;pendingMove=null;moveTimer=0;fetch('/api/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(latest),cache:'no-store'}).catch(()=>{})},32);return}
  fetch('/api/input', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload),cache:'no-store'}).catch(()=>{});
}
function normaliseEvent(event) {
  const rect = img.getBoundingClientRect();
  const x = (event.clientX - rect.left) / Math.max(rect.width,1);
  const y = (event.clientY - rect.top) / Math.max(rect.height,1);
    const normalisedX = Math.max(0, Math.min(1, x)), normalisedY = Math.max(0, Math.min(1, y));
    return {x: normalisedX, y: normalisedY, display_id: Number(picker.value) || 0};
}
async function updateHostCursor(){if(!document.body.classList.contains('connected')||cursorPending)return;cursorPending=true;try{const response=await fetch('/cursor/'+encodeURIComponent(picker.value),{cache:'no-store'});if(!response.ok)throw new Error('cursor unavailable');const cursor=await response.json();if(cursor.visible){hostCursor.style.left=`${cursor.x*100}%`;hostCursor.style.top=`${cursor.y*100}%`;hostCursor.style.display='block'}else hostCursor.style.display='none'}catch(_){hostCursor.style.display='none'}finally{cursorPending=false;if(document.body.classList.contains('connected'))cursorTimer=setTimeout(updateHostCursor,40)}}
img.addEventListener('pointerdown', event => { img.setPointerCapture?.(event.pointerId);sendInput('touch_down', normaliseEvent(event)); });
img.addEventListener('pointermove', event => { const detail = normaliseEvent(event); sendInput(event.pressure > 0 || event.buttons !== 0 ? 'touch_move' : 'mouse_move', detail); });
img.addEventListener('pointerup', event => sendInput('touch_up', normaliseEvent(event)));
img.addEventListener('pointerleave', event => sendInput('touch_up', normaliseEvent(event)));
img.addEventListener('wheel', event => sendInput('mouse_wheel', {...normaliseEvent(event), delta_x: event.deltaX, delta_y: event.deltaY}), {passive: true});
window.addEventListener('keydown', event => sendInput('key_down', {key: event.key, code: event.code, key_code: event.keyCode}));
window.addEventListener('keyup', event => sendInput('key_up', {key: event.key, code: event.code, key_code: event.keyCode}));
window.addEventListener('pagehide', () => { img.src = ''; clearTimeout(cursorTimer); navigator.sendBeacon?.('/session/close', ''); });
loadDisplays();
form.onsubmit=async e=>{e.preventDefault();err.textContent='Connecting…';try{const r=await fetch('/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:form.querySelector('input').value})});if(!r.ok)throw new Error((await r.json()).error||'Could not pair');document.body.classList.add('connected');if(document.documentElement.requestFullscreen)document.documentElement.requestFullscreen().catch(()=>{});if(screen.orientation&&screen.orientation.lock)screen.orientation.lock('landscape').catch(()=>{});if('wakeLock'in navigator)navigator.wakeLock.request('screen').catch(()=>{});img.src='/stream/'+encodeURIComponent(picker.value);updateHostCursor();img.onerror=()=>{document.body.classList.remove('connected');clearTimeout(cursorTimer);hostCursor.style.display='none';stage.style.display='none';err.textContent='Stream ended. Reconnect from the Mac dashboard.'}}catch(x){err.textContent=x.message}}
</script></html>"""


class ReceiverHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ReceiverHandler(BaseHTTPRequestHandler):
    state = None

    def _reply(self, status: HTTPStatus, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/receiver":
            self._reply(HTTPStatus.OK, RECEIVER_HTML.encode(), "text/html; charset=utf-8")
            return
        if path == "/displays":
            import json
            displays = self.state.display_details()
            self._reply(HTTPStatus.OK, json.dumps(displays).encode(), "application/json; charset=utf-8")
            return
        if path.startswith("/cursor/"):
            if not self.state.is_paired(self.headers.get("Cookie", "")):
                self._reply(HTTPStatus.UNAUTHORIZED, b'{"error":"Pair from the dashboard first"}', "application/json; charset=utf-8")
                return
            try:
                display_id = int(path.rsplit("/", 1)[1])
            except ValueError:
                self._reply(HTTPStatus.NOT_FOUND, b'{"error":"Unknown display"}', "application/json; charset=utf-8")
                return
            if display_id not in self.state.display_ids():
                self._reply(HTTPStatus.NOT_FOUND, b'{"error":"Display no longer exists"}', "application/json; charset=utf-8")
                return
            import json
            self._reply(HTTPStatus.OK, json.dumps(self.state.cursor_position(display_id)).encode(), "application/json; charset=utf-8")
            return
        if not path.startswith("/stream/"):
            self._reply(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        if not self.state.is_paired(self.headers.get("Cookie", "")):
            self._reply(HTTPStatus.UNAUTHORIZED, b"Pair from the dashboard first", "text/plain; charset=utf-8")
            return
        try:
            display_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            self._reply(HTTPStatus.NOT_FOUND, b"Unknown display", "text/plain; charset=utf-8")
            return
        if display_id not in self.state.display_ids():
            self._reply(HTTPStatus.NOT_FOUND, b"Display no longer exists", "text/plain; charset=utf-8")
            return

        boundary = b"--multidisplay-frame\r\n"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=multidisplay-frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        last_frame = None
        try:
            while display_id in self.state.display_ids():
                frame = self.state.frames.get(display_id)
                if frame and frame is not last_frame:
                    self.wfile.write(boundary)
                    self.wfile.write(f"Content-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame + b"\r\n")
                    self.wfile.flush()
                    last_frame = frame
                time.sleep(0.02)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/session/close":
            self._reply(HTTPStatus.NO_CONTENT, b"", "text/plain; charset=utf-8")
            return
        if path == "/api/input":
            if not self.state.is_paired(self.headers.get("Cookie", "")):
                self._reply(HTTPStatus.UNAUTHORIZED, b'{"error":"Pair from the dashboard first"}', "application/json")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Invalid request")
                import json
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Input payload must be a JSON object")
                ok = self.state.handle_input_event(payload)
                self._reply(HTTPStatus.OK, b'{"ok":true}' if ok else b'{"ok":false,"error":"Unsupported input event"}', "application/json")
            except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
                self._reply(HTTPStatus.BAD_REQUEST, b'{"error":"Invalid input request"}', "application/json")
            return
        if path != "/pair":
            self._reply(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("Invalid request")
            import json
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not self.state.pair(
                str(payload.get("code", "")), self.client_address[0]
            ):
                self._reply(HTTPStatus.FORBIDDEN, b'{"error":"Incorrect pairing code"}', "application/json")
                return
            response = b'{"paired":true}'
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Set-Cookie", f"MDSESSION={self.state.session_token}; HttpOnly; SameSite=Strict; Path=/")
            self.end_headers()
            self.wfile.write(response)
        except (ValueError, TypeError, UnicodeDecodeError):
            self._reply(HTTPStatus.BAD_REQUEST, b'{"error":"Invalid pairing request"}', "application/json")

    def log_message(self, format: str, *args) -> None:
        return


class ReceiverServer:
    """LAN-facing HTTP server for Android receiver pages and MJPEG streams."""

    def __init__(self, state, host: str = "0.0.0.0", port: int = 51820):
        self.state = state
        handler = type("BoundReceiverHandler", (ReceiverHandler,), {"state": state})
        self.server = ReceiverHTTPServer((host, port), handler)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, name="receiver-http", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
