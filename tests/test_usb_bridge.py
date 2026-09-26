import subprocess

from multidisplay.usb_bridge import ADBReverseBridge


class FakeBridge(ADBReverseBridge):
    def __init__(self, results):
        super().__init__(port=51820)
        self.adb = "adb"
        self.results = iter(results)
        self.commands = []

    def _command(self, *args):
        self.commands.append(args)
        return next(self.results)


def test_bridge_forwards_each_authorized_device():
    bridge = FakeBridge([
        subprocess.CompletedProcess([], 0, "List of devices attached\nphone-1 device\nphone-2 unauthorized\n", ""),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "Physical size: 1080x2340\n", ""),
        subprocess.CompletedProcess([], 0, "refreshRate=90.0", ""),
    ])
    bridge._refresh()

    assert bridge.devices == ("phone-1",)
    assert bridge.commands == [
        ("devices",),
        ("-s", "phone-1", "reverse", "tcp:51820", "tcp:51820"),
        ("-s", "phone-1", "shell", "wm", "size"),
        ("-s", "phone-1", "shell", "dumpsys", "display"),
    ]
    assert "127.0.0.1:51820" in bridge.status
    assert bridge.profile == {"width": 2340, "height": 1080, "refresh_rate": 90, "device": "phone-1"}
