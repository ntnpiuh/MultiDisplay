"""Small local dashboard for managing MultiDisplay sessions."""

import hmac
import importlib
import json
import secrets
import socket
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

try:
    from ..display.display_config import DisplayConfig, RefreshRate
    from ..display.display_manager import DisplayBackendError, DisplayManager
    from ..receiver.receiver_client import InputHandler
    from .streaming import DisplayCapture, FrameStore, ReceiverServer
    from .usb_bridge import ADBReverseBridge
except ImportError:  # pragma: no cover - supports direct source execution
    from display.display_config import DisplayConfig, RefreshRate
    from display.display_manager import DisplayBackendError, DisplayManager
    from receiver.receiver_client import InputHandler
    from multidisplay.streaming import DisplayCapture, FrameStore, ReceiverServer
    from multidisplay.usb_bridge import ADBReverseBridge


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MultiDisplay Control Room</title>
  <style>
    :root { --ink:#17231f; --muted:#687770; --paper:#f4f1e8; --panel:#fffdf7; --line:#d9ddd2; --accent:#d45a34; --green:#28735e; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:radial-gradient(circle at 90% 0%, #e6efe4 0 18%, transparent 42%), var(--paper); font:15px/1.5 Georgia, serif; }
    .shell { max-width:1120px; margin:0 auto; padding:34px 22px 56px; }
    header { display:flex; justify-content:space-between; align-items:flex-end; gap:20px; margin-bottom:30px; }
    .eyebrow { color:var(--accent); font:700 11px/1.2 ui-monospace, SFMono-Regular, monospace; letter-spacing:.14em; text-transform:uppercase; }
    h1 { margin:7px 0 5px; font-size:clamp(2rem, 5vw, 4rem); line-height:.98; font-weight:500; letter-spacing:-.04em; }
    .lede { max-width:530px; margin:0; color:var(--muted); }
    .signal { display:flex; align-items:center; gap:8px; color:var(--green); font:700 12px ui-monospace, monospace; white-space:nowrap; }
    .dot { width:9px; height:9px; border-radius:50%; background:#55a982; box-shadow:0 0 0 5px #d5eadc; }
    .grid { display:grid; grid-template-columns:1.4fr .9fr; gap:18px; }
    .panel { background:color-mix(in srgb, var(--panel) 93%, transparent); border:1px solid var(--line); border-radius:8px; padding:22px; box-shadow:0 10px 30px #4852460d; }
    .panel h2 { margin:0 0 16px; font-size:1.35rem; font-weight:500; }
    .panel-head { display:flex; justify-content:space-between; align-items:center; gap:12px; }
    .metric-row { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:22px; }
    .metric { padding:14px; border-top:2px solid var(--ink); background:#f8f7f0; }
    .metric strong { display:block; font-size:1.8rem; font-weight:500; }
    .metric span { color:var(--muted); font:11px ui-monospace, monospace; text-transform:uppercase; }
    .display { display:flex; justify-content:space-between; align-items:center; gap:12px; border-top:1px solid var(--line); padding:14px 0; }
    .display:last-child { padding-bottom:0; }
    .display-name { font-weight:700; }
    .display-meta { color:var(--muted); font:12px ui-monospace, monospace; }
    button { border:0; border-radius:4px; padding:10px 13px; color:white; background:var(--ink); cursor:pointer; font:700 12px ui-monospace, monospace; }
    button:hover { background:var(--accent); }
    button.ghost { color:var(--ink); background:transparent; border:1px solid var(--line); }
    button.danger { color:var(--accent); background:transparent; border:1px solid #e7b8a9; }
    form { display:grid; gap:13px; }
    label { display:grid; gap:6px; color:var(--muted); font:11px ui-monospace, monospace; text-transform:uppercase; }
    input, select { width:100%; padding:11px; border:1px solid var(--line); border-radius:4px; color:var(--ink); background:#fff; font:15px Georgia, serif; }
    .form-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .actions { display:flex; justify-content:flex-end; margin-top:4px; }
    .note { margin:16px 0 0; color:var(--muted); font-size:13px; }
    .empty { color:var(--muted); padding:10px 0 3px; }
    #toast { position:fixed; right:22px; bottom:22px; max-width:320px; padding:12px 15px; color:white; background:var(--ink); border-radius:4px; opacity:0; transform:translateY(8px); transition:.2s ease; pointer-events:none; }
    #toast.show { opacity:1; transform:translateY(0); }
    @media (max-width:760px) { header { display:block; } .signal { margin-top:20px; } .grid { grid-template-columns:1fr; } .metric-row { grid-template-columns:1fr 1fr 1fr; } }
  </style>
</head>
<body>
  <main class="shell">
    <header>
    <div><div class="eyebrow">Local control room / v0.1</div><h1>MultiDisplay</h1><p class="lede">Turn a spare device into useful desk space. Configure virtual displays here, then connect receivers over your local network.</p></div>
    <div class="signal"><span class="dot"></span><span id="server-status">SERVER ONLINE</span><button class="danger" id="quit">Quit</button></div>
    </header>
    <div class="metric-row">
      <div class="metric"><strong id="physical-count">—</strong><span>Physical displays</span></div>
      <div class="metric"><strong id="virtual-count">—</strong><span>Virtual displays</span></div>
      <div class="metric"><strong id="receiver-port">51820</strong><span>Phone receiver port</span></div>
    </div>
    <section class="panel" style="margin-bottom:18px"><div class="panel-head"><div><h2>Connect an Android device</h2><div class="display-meta">Wi‑Fi: open this address in Chrome on your phone.</div></div><button class="ghost" id="copy-link">Copy Wi‑Fi link</button></div><p><strong id="receiver-url">Starting receiver…</strong></p><p class="display-meta">Pairing code <strong id="pair-code">········</strong></p><hr><div class="display-meta"><strong>USB:</strong> Connect a data cable, enable USB debugging, and approve the Mac. <span id="usb-status">Checking ADB…</span></div><p><strong id="usb-url">http://127.0.0.1:51820/receiver</strong></p></section>
    <section class="grid">
      <article class="panel"><div class="panel-head"><h2>Your displays</h2><button class="ghost" id="refresh">Refresh</button></div><div id="display-list"><div class="empty">Loading display inventory...</div></div></article>
      <aside class="panel"><h2>Add a virtual display</h2><form id="display-form">
        <label>Name<input name="name" value="Desk extension" maxlength="48" required></label>
        <div class="form-grid"><label>Width<input name="width" type="number" min="320" max="7680" value="1920" required></label><label>Height<input name="height" type="number" min="240" max="4320" value="1080" required></label></div>
        <label>Refresh rate<select name="refresh_rate"><option value="30">30 Hz</option><option value="60" selected>60 Hz</option><option value="90">90 Hz</option><option value="120">120 Hz</option></select></label>
        <label>JPEG quality<input name="jpeg_quality" type="number" min="1" max="100" value="65" required></label>
        <button type="button" class="ghost" id="auto-display" disabled>Detect phone display (USB)</button>
        <div class="actions"><button type="submit">Create display</button></div>
      </form><p class="note">Requires macOS screen recording permission. Virtual displays use Apple's private CoreGraphics API and are not available in App Store builds.</p></aside>
    </section>
  </main><div id="toast" role="status"></div>
  <script>
    const list = document.querySelector('#display-list'), toast = document.querySelector('#toast');
    function notify(message) { toast.textContent = message; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2600); }
    function escapeHtml(value) { return String(value).replace(/[&<>\"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[char])); }
    function displayMarkup(item) { const remove = item.virtual ? `<button class="danger" data-remove="${escapeHtml(item.id)}">Remove</button>` : ''; const stream = item.virtual ? `<div class="display-meta">${escapeHtml(item.stream_status || '')}</div>` : ''; return `<div class="display"><div><div class="display-name">${escapeHtml(item.name)}</div><div class="display-meta">${escapeHtml(item.width)} × ${escapeHtml(item.height)} · ${escapeHtml(item.refresh_rate)} Hz · ${item.virtual ? 'VIRTUAL' : 'PHYSICAL'}</div>${stream}</div>${remove}</div>`; }
    async function load() { const response = await fetch('/api/status'); const data = await response.json(); document.querySelector('#physical-count').textContent = data.physical_displays; document.querySelector('#virtual-count').textContent = data.virtual_displays; document.querySelector('#receiver-port').textContent = data.receiver_port; document.querySelector('#receiver-url').textContent = data.receiver_url; document.querySelector('#usb-url').textContent = data.usb_url; document.querySelector('#usb-status').textContent = data.usb_status; document.querySelector('#pair-code').textContent = data.pair_code; const detect=document.querySelector('#auto-display');detect.disabled=!data.phone_profile;detect.textContent=data.phone_profile?`Create ${data.phone_profile.width} × ${data.phone_profile.height} · ${data.phone_profile.refresh_rate} Hz display`:'Detect phone display (USB)'; list.innerHTML = data.displays.length ? data.displays.map(displayMarkup).join('') : '<div class="empty">No displays detected.</div>'; document.querySelectorAll('[data-remove]').forEach(button => button.onclick = () => removeDisplay(button.dataset.remove)); }
    async function removeDisplay(id) { const response = await fetch(`/api/displays/${id}`, {method:'DELETE'}); const data = await response.json(); notify(data.message || data.error); if (response.ok) load(); }
    document.querySelector('#display-form').onsubmit = async event => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.target)); body.width = Number(body.width); body.height = Number(body.height); body.refresh_rate = Number(body.refresh_rate); const response = await fetch('/api/displays', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); const data = await response.json(); notify(data.message || data.error); if (response.ok) { event.target.reset(); load(); } };
    document.querySelector('#refresh').onclick = load; load().catch(() => { document.querySelector('#server-status').textContent = 'SERVER ERROR'; }); setInterval(() => load().catch(() => {}), 4000);
    document.querySelector('#auto-display').onclick = async () => { const button=document.querySelector('#auto-display');button.disabled=true;try{const response=await fetch('/api/displays/auto',{method:'POST'});const result=await response.json();notify(result.message||result.error)}catch(_){notify('Could not detect the phone display')}finally{load()}};
    document.querySelector('#copy-link').onclick = async () => { try { await navigator.clipboard.writeText(document.querySelector('#receiver-url').textContent); notify('Receiver address copied'); } catch (_) { notify('Copy the receiver address shown here'); } };
    document.querySelector('#quit').onclick = async () => { if (!confirm('Quit MultiDisplay?')) return; await fetch('/api/quit', {method:'POST'}); document.querySelector('#server-status').textContent = 'STOPPING'; };
  </script>
</body>
</html>"""


class DashboardState:
    """Application state kept by one dashboard process."""

    def __init__(self, display_manager: Optional[DisplayManager] = None):
        self.display_manager = display_manager or DisplayManager()
        self.receiver_port = 51820
        self._lock = threading.Lock()
        self._configs: Dict[int, DisplayConfig] = {}
        self.frames = FrameStore()
        self._captures: Dict[int, DisplayCapture] = {}
        self.pair_code = f"{secrets.randbelow(100_000_000):08d}"
        self.session_token = secrets.token_urlsafe(32)
        self._pair_attempts: Dict[str, tuple[float, int]] = {}
        self.receiver_url = f"http://{_lan_address()}:{self.receiver_port}/receiver"
        self.receiver_server = None
        self.usb_bridge = ADBReverseBridge(self.receiver_port)
        self.input_handler = InputHandler(host="127.0.0.1", port=self.receiver_port + 1)
        self.quit_callback: Optional[Callable[[], None]] = None

    def start_receiver(self, host: str = "0.0.0.0", port: int = 51820) -> None:
        self.receiver_server = ReceiverServer(self, host=host, port=port)
        self.receiver_port = self.receiver_server.port
        self.receiver_url = f"http://{_lan_address()}:{self.receiver_port}/receiver"
        self.usb_bridge = ADBReverseBridge(self.receiver_port)
        self.input_handler = InputHandler(host="127.0.0.1", port=self.receiver_port + 1)
        self.usb_bridge.start()
        self.receiver_server.start()

    def pair(self, supplied_code: str, peer: str = "local") -> bool:
        now = time.monotonic()
        with self._lock:
            attempts = self._pair_attempts.get(peer)
            if attempts and now - attempts[0] < 60 and attempts[1] >= 10:
                return False
            if attempts is None or now - attempts[0] >= 60:
                attempts = (now, 0)
            matched = hmac.compare_digest(supplied_code, self.pair_code)
            if not matched:
                self._pair_attempts[peer] = (attempts[0], attempts[1] + 1)
            else:
                self._pair_attempts.pop(peer, None)
            return matched

    def is_paired(self, cookie: str) -> bool:
        for part in cookie.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name == "MDSESSION":
                return hmac.compare_digest(value, self.session_token)
        return False

    def display_ids(self):
        with self._lock:
            return tuple(self._configs)

    def display_details(self):
        with self._lock:
            return [{"id": display_id, "name": config.name, "width": config.width, "height": config.height} for display_id, config in self._configs.items()]

    def handle_input_event(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            raise ValueError("Input event payload must be a JSON object")
        return self.input_handler.handle_input_event(payload)

    def cursor_position(self, display_id: int) -> Dict[str, Any]:
        """Return the Mac cursor location normalized within a managed display."""
        if display_id not in self.display_ids():
            return {"visible": False}
        try:
            import Quartz.CoreGraphics as cg
            event = cg.CGEventCreate(None)
            if event is None:
                return {"visible": False}
            point = cg.CGEventGetLocation(event)
            bounds = cg.CGDisplayBounds(display_id)
            left, top = float(bounds.origin.x), float(bounds.origin.y)
            width, height = float(bounds.size.width), float(bounds.size.height)
            x, y = float(point.x), float(point.y)
            if width <= 0 or height <= 0 or not (left <= x < left + width and top <= y < top + height):
                return {"visible": False}
            return {"visible": True, "x": (x - left) / width, "y": (y - top) / height}
        except (ImportError, AttributeError, TypeError, ValueError):
            return {"visible": False}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            all_monitors = self.display_manager.list_displays()
            physical = [monitor for monitor in all_monitors if monitor.is_physical]
            displays = [
                {"id": f"physical-{index}", "name": "Built-in display" if index == 0 else f"Display {index + 1}", "width": monitor.width, "height": monitor.height, "refresh_rate": monitor.refresh_rate.value, "virtual": False}
                for index, monitor in enumerate(physical)
            ]
            displays.extend(
                {
                    "id": display_id,
                    "name": config.name,
                    "width": config.width,
                    "height": config.height,
                    "refresh_rate": config.refresh_rate.value,
                    "virtual": True,
                    "jpeg_quality": self._captures[display_id].quality,
                    "position": config.position,
                    "stream_status": (
                        self._captures[display_id].error
                        or (
                            "STREAMING" if self.frames.get(display_id) else "Starting capture…" if self._captures[display_id].running else "Receiver is not running"
                        )
                    ),
                }
                for display_id, config in self._configs.items()
            )
            return {
                "physical_displays": len(physical),
                "virtual_displays": len(self._configs),
                "receiver_port": self.receiver_port,
                "receiver_url": self.receiver_url,
                "usb_url": f"http://127.0.0.1:{self.receiver_port}/receiver",
                "usb_status": self.usb_bridge.status,
                "phone_profile": self.usb_bridge.profile,
                "pair_code": self.pair_code,
                "displays": displays,
            }

    def create(self, payload: Dict[str, Any]) -> int:
        if not isinstance(payload, dict):
            raise ValueError("Display configuration must be a JSON object")
        position = payload.get("position")
        if position is not None:
            if not isinstance(position, (list, tuple)) or len(position) != 2:
                raise ValueError("Position must contain x and y coordinates")
            position = (int(position[0]), int(position[1]))
        quality = int(payload.get("jpeg_quality", 78))
        if not 1 <= quality <= 100:
            raise ValueError("JPEG quality must be between 1 and 100")
        config = DisplayConfig(name=str(payload.get("name", "Desk extension"))[:48], width=int(payload["width"]), height=int(payload["height"]), refresh_rate=RefreshRate(int(payload.get("refresh_rate", 60))), position=position)
        if not 320 <= config.width <= 7680 or not 240 <= config.height <= 4320:
            raise ValueError("Display dimensions are outside the supported range")
        if config.width % 2 or config.height % 2:
            raise ValueError("Display dimensions must be even for HiDPI mode")
        if config.refresh_rate not in (RefreshRate.HZ_30, RefreshRate.HZ_60, RefreshRate.HZ_90, RefreshRate.HZ_120):
            raise ValueError("Supported refresh rates are 30, 60, 90, and 120 Hz")
        with self._lock:
            display_id = self.display_manager.create_virtual_display(config)
            self._configs[display_id] = config
            capture = DisplayCapture(display_id, self.frames, quality=quality)
            self._captures[display_id] = capture
            if self.receiver_server is not None:
                capture.start()
            return display_id

    def create_for_phone(self) -> int:
        profile = self.usb_bridge.profile
        if not profile:
            raise ValueError("Connect and authorize an Android phone over USB first")
        return self.create({"name": "Phone display", "width": profile["width"], "height": profile["height"], "refresh_rate": profile["refresh_rate"], "jpeg_quality": 65})

    def configure(self, display_id: int, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            raise ValueError("Display configuration must be a JSON object")
        with self._lock:
            current = self._configs.get(display_id)
            if current is None:
                return False
            position = payload.get("position", current.position)
            if position is not None:
                if not isinstance(position, (list, tuple)) or len(position) != 2:
                    raise ValueError("Position must contain x and y coordinates")
                position = (int(position[0]), int(position[1]))
            config = DisplayConfig(name=current.name, width=int(payload.get("width", current.width)), height=int(payload.get("height", current.height)), refresh_rate=RefreshRate(int(payload.get("refresh_rate", current.refresh_rate.value))), position=position)
            if config.width % 2 or config.height % 2:
                raise ValueError("Display dimensions must be even for HiDPI mode")
            if config.refresh_rate not in (RefreshRate.HZ_30, RefreshRate.HZ_60, RefreshRate.HZ_90, RefreshRate.HZ_120):
                raise ValueError("Supported refresh rates are 30, 60, 90, and 120 Hz")
            if not self.display_manager.configure_virtual_display(display_id, config):
                return False
            self._configs[display_id] = config
            if "jpeg_quality" in payload:
                quality = int(payload["jpeg_quality"])
                if not 1 <= quality <= 100:
                    raise ValueError("JPEG quality must be between 1 and 100")
                self._captures[display_id].quality = quality
            return True

    def remove(self, display_id: int) -> bool:
        with self._lock:
            removed = self.display_manager.remove_virtual_display(display_id)
            self._configs.pop(display_id, None)
            capture = self._captures.pop(display_id, None)
            if capture is not None:
                capture.stop()
            return removed


class DashboardHandler(BaseHTTPRequestHandler):
    state: DashboardState

    def _send(self, payload: Any, status: HTTPStatus = HTTPStatus.OK, content_type: str = "application/json") -> None:
        body = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send(HTML, content_type="text/html")
        elif path == "/api/status":
            self._send(self.state.status())
        else:
            self._send({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/quit":
            self._send({"message": "MultiDisplay is stopping"})
            if self.state.quit_callback is not None:
                threading.Thread(target=self.state.quit_callback, name="dashboard-quit", daemon=True).start()
            return
        if path == "/api/displays/auto":
            try:
                display_id = self.state.create_for_phone()
                self._send({"message": f"Phone-matched display {display_id} created", "id": display_id}, HTTPStatus.CREATED)
            except ValueError as error:
                self._send({"error": str(error)}, HTTPStatus.CONFLICT)
            except DisplayBackendError as error:
                self._send({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if path == "/api/displays":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Invalid request size")
                display_id = self.state.create(json.loads(self.rfile.read(length)))
                self._send({"message": f"Display {display_id} created", "id": display_id}, HTTPStatus.CREATED)
            except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                self._send({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            except DisplayBackendError as error:
                self._send({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self._send({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parts = urlparse(self.path).path.split("/")
        if len(parts) != 4 or parts[1:3] != ["api", "displays"]:
            self._send({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Invalid request size")
            configured = self.state.configure(int(parts[3]), json.loads(self.rfile.read(length)))
            self._send({"message": "Display configured"} if configured else {"error": "Display not found"}, HTTPStatus.OK if configured else HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._send({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        parts = urlparse(self.path).path.split("/")
        if len(parts) != 4 or parts[1:3] != ["api", "displays"]:
            self._send({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            removed = self.state.remove(int(parts[3]))
        except ValueError:
            removed = False
        self._send({"message": "Display removed" if removed else "Display not found"}, HTTPStatus.OK if removed else HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _lan_address() -> str:
    """Choose the Mac's default-route IPv4 address for phone setup guidance."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        address = probe.getsockname()[0]
        if not address.startswith("127."):
            return address
    except OSError:
        pass
    finally:
        probe.close()
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = str(result[4][0])
            if not address.startswith("127.") and not address.startswith("169.254."):
                return address
    except OSError:
        pass
    return "<mac-ip-address>"


def _new_dashboard_server(host: str, port: int) -> tuple[DashboardState, ThreadingHTTPServer]:
    state = DashboardState()

    class Handler(DashboardHandler):
        pass

    Handler.state = state
    server = ThreadingHTTPServer((host, port), Handler)
    state.quit_callback = lambda: server.shutdown()
    return state, server


def _close_dashboard(state: DashboardState, server: ThreadingHTTPServer) -> None:
    server.server_close()
    if state.receiver_server is not None:
        state.receiver_server.close()
    state.usb_bridge.stop()
    for capture in tuple(state._captures.values()):
        capture.stop()


def _run_native_dashboard(host: str, port: int, receiver_host: str, receiver_port: int) -> None:
    """Run the dashboard inside a native macOS WebKit window."""
    if sys.platform != "darwin":
        raise RuntimeError("The native dashboard window is only available on macOS")
    try:
        appkit = importlib.import_module("AppKit")
        foundation = importlib.import_module("Foundation")
        webkit = importlib.import_module("WebKit")
    except ImportError as error:
        raise RuntimeError("Install pyobjc-framework-WebKit to use the native dashboard window") from error

    NSApplication = getattr(appkit, "NSApplication")
    NSApplicationActivationPolicyRegular = getattr(appkit, "NSApplicationActivationPolicyRegular")
    NSBackingStoreBuffered = getattr(appkit, "NSBackingStoreBuffered")
    NSMakeRect = getattr(appkit, "NSMakeRect")
    NSResizableWindowMask = getattr(appkit, "NSResizableWindowMask")
    NSViewHeightSizable = getattr(appkit, "NSViewHeightSizable")
    NSViewWidthSizable = getattr(appkit, "NSViewWidthSizable")
    NSWindow = getattr(appkit, "NSWindow")
    NSWindowStyleMaskClosable = getattr(appkit, "NSWindowStyleMaskClosable")
    NSWindowStyleMaskMiniaturizable = getattr(appkit, "NSWindowStyleMaskMiniaturizable")
    NSWindowStyleMaskTitled = getattr(appkit, "NSWindowStyleMaskTitled")
    NSObject = getattr(foundation, "NSObject")
    NSURL = getattr(foundation, "NSURL")
    NSURLRequest = getattr(foundation, "NSURLRequest")
    WKWebView = getattr(webkit, "WKWebView")
    WKWebViewConfiguration = getattr(webkit, "WKWebViewConfiguration")

    state, server = _new_dashboard_server(host, port)
    state.start_receiver(host=receiver_host, port=receiver_port)
    server_thread = threading.Thread(target=server.serve_forever, name="dashboard-http", daemon=True)
    server_thread.start()

    class ApplicationDelegate(NSObject):
        def applicationShouldTerminateAfterLastWindowClosed_(self, _application):
            return True

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    app_delegate = ApplicationDelegate.alloc().init()
    app.setDelegate_(app_delegate)

    style_mask = (
        NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskMiniaturizable
        | NSResizableWindowMask
    )
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 1180, 820), style_mask, NSBackingStoreBuffered, False
    )
    web_view = WKWebView.alloc().initWithFrame_configuration_(
        NSMakeRect(0, 0, 1180, 820), WKWebViewConfiguration.alloc().init()
    )
    web_view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    window.setContentView_(web_view)
    window.setTitle_("MultiDisplay")
    window.center()
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    web_view.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(f"http://{host}:{port}/")))
    state.quit_callback = lambda: app.terminate_(None)
    print(f"MultiDisplay native dashboard running at http://{host}:{port}")
    try:
        app.run()
    finally:
        _close_dashboard(state, server)


def run_dashboard(host: str = "127.0.0.1", port: int = 8765, receiver_host: str = "0.0.0.0", receiver_port: int = 51820, native: bool = False) -> None:
    """Run the local dashboard, optionally inside a native macOS window."""
    if native:
        _run_native_dashboard(host, port, receiver_host, receiver_port)
        return

    state, server = _new_dashboard_server(host, port)
    try:
        state.start_receiver(host=receiver_host, port=receiver_port)
        print(f"MultiDisplay dashboard running at http://{host}:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        _close_dashboard(state, server)
