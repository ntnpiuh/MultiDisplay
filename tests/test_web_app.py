import sys
import os
import http.client
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from multidisplay.web_app import DashboardState
from multidisplay.web_app import DashboardHandler


def test_dashboard_state_creates_and_removes_virtual_display():
    state = DashboardState()
    display_id = state.create({'name': 'Tablet', 'width': 1280, 'height': 800, 'refresh_rate': 60})

    assert state.status()['virtual_displays'] == 1
    assert state.status()['displays'][-1]['name'] == 'Tablet'
    assert state.remove(display_id) is True
    assert state.status()['virtual_displays'] == 0


def test_dashboard_rejects_invalid_dimensions():
    state = DashboardState()

    try:
        state.create({'name': 'Too small', 'width': 10, 'height': 10, 'refresh_rate': 60})
    except ValueError as error:
        assert 'dimensions' in str(error)
    else:
        raise AssertionError('invalid dimensions should be rejected')


def test_dashboard_response_has_security_headers():
    state = DashboardState()

    class Handler(DashboardHandler):
        pass

    Handler.state = state
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        client.request("GET", "/api/status")
        response = client.getresponse()
        assert response.status == 200
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("X-Content-Type-Options") == "nosniff"
        assert response.getheader("X-Frame-Options") == "DENY"
        assert response.getheader("Referrer-Policy") == "no-referrer"
        client.close()
    finally:
        server.shutdown()
        server.server_close()