import http.client
import json

from multidisplay.streaming import FrameStore
from multidisplay.web_app import DashboardState
from display.display_config import MonitorInfo


class FakeDisplayManager:
    def __init__(self):
        self.next_id = 101

    def list_displays(self):
        return [MonitorInfo(width=1440, height=900, is_physical=True)]

    def create_virtual_display(self, _config):
        self.next_id += 1
        return self.next_id

    def remove_virtual_display(self, _display_id):
        return True

    def configure_virtual_display(self, _display_id, _config):
        return True


def test_frame_store_returns_newest_frame_and_removes_display():
    store = FrameStore()
    store.publish(42, b"frame-1")
    store.publish(42, b"frame-2")
    assert store.get(42) == b"frame-2"
    store.remove(42)
    assert store.get(42) is None


def test_receiver_page_tracks_host_cursor_with_low_latency_capture_and_teardown():
    from multidisplay.streaming import RECEIVER_HTML

    assert "CGDisplayCreateImage" not in RECEIVER_HTML
    assert 'id="host-cursor"' in RECEIVER_HTML
    assert "'/cursor/'+encodeURIComponent(picker.value)" in RECEIVER_HTML
    assert "pagehide" in RECEIVER_HTML
    assert "object-fit:fill" in RECEIVER_HTML
    assert "hostSize" in RECEIVER_HTML
    assert "width: hostSize.width" in RECEIVER_HTML


def test_receiver_rejects_unpaired_input_events():
    state = DashboardState(FakeDisplayManager())
    state.start_receiver(host="127.0.0.1", port=0)
    try:
        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("POST", "/api/input", json.dumps({"type": "mouse_move", "x": 10, "y": 20}), {"Content-Type": "application/json"})
        response = client.getresponse()
        assert response.status == 401
        client.close()
        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("GET", "/cursor/101")
        response = client.getresponse()
        assert response.status == 401
        client.close()
    finally:
        state.receiver_server.close()
        if hasattr(state, "usb_bridge"):
            state.usb_bridge.stop()


def test_receiver_pairs_and_streams_over_http():
    state = DashboardState(FakeDisplayManager())
    state.start_receiver(host="127.0.0.1", port=0)
    display_id = state.create({"name": "Phone", "width": 1280, "height": 800})
    state.frames.publish(display_id, b"test-jpeg")
    state.cursor_position = lambda requested_id: {"visible": requested_id == display_id, "x": 0.25, "y": 0.75}
    try:
        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("GET", "/receiver")
        response = client.getresponse()
        assert response.status == 200
        assert b"MultiDisplay Receiver" in response.read()
        client.close()

        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("GET", "/displays")
        response = client.getresponse()
        assert json.loads(response.read())[0]["id"] == display_id
        client.close()

        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("POST", "/pair", json.dumps({"code": state.pair_code}), {"Content-Type": "application/json"})
        response = client.getresponse()
        cookie = response.getheader("Set-Cookie").split(";", 1)[0]
        assert response.status == 200
        response.read()
        client.close()

        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("GET", f"/cursor/{display_id}", headers={"Cookie": cookie})
        response = client.getresponse()
        assert response.status == 200
        assert json.loads(response.read()) == {"visible": True, "x": 0.25, "y": 0.75}
        client.close()

        client = http.client.HTTPConnection("127.0.0.1", state.receiver_port, timeout=2)
        client.request("GET", f"/stream/{display_id}", headers={"Cookie": cookie})
        response = client.getresponse()
        assert response.status == 200
        assert "multipart/x-mixed-replace" in response.getheader("Content-Type")
        assert b"test-jpeg" in response.read(256)
        client.close()
    finally:
        state.remove(display_id)
        state.receiver_server.close()
        state.usb_bridge.stop()


def test_dashboard_configures_display_position_and_quality():
    state = DashboardState(FakeDisplayManager())
    display_id = state.create({'name': 'Phone', 'width': 1280, 'height': 800, 'jpeg_quality': 90})
    assert state.configure(display_id, {'position': [1440, 0], 'jpeg_quality': 65}) is True
    details = state.status()['displays'][-1]
    assert details['position'] == (1440, 0)
    assert details['jpeg_quality'] == 65
    assert state.remove(display_id) is True
