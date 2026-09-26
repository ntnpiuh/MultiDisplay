import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from multidisplay.web_app import DashboardState


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