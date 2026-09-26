"""USB transport over Android Debug Bridge reverse port forwarding.

This works without Android USB networking drivers: the Android browser connects
to its own localhost and ADB forwards that TCP connection over the USB data
channel to the Mac. Android USB debugging must be enabled and authorized once.
"""

import shutil
import subprocess
import threading
import time
import re
from typing import Optional


class ADBReverseBridge:
    """Maintain an ADB reverse mapping for each authorized connected phone."""

    def __init__(self, port: int = 51820, poll_interval: float = 2.0):
        self.port = port
        self.poll_interval = poll_interval
        self.adb = shutil.which("adb")
        self.status = "USB ready when an authorized Android phone is connected"
        self.devices = ()
        self.profile = None
        self._stopping = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None or not self.adb:
            if not self.adb:
                self.status = "ADB is not installed; Wi-Fi receiver remains available"
            return
        self._thread = threading.Thread(target=self._run, name="adb-usb-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _command(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.adb, *args], capture_output=True, text=True, timeout=4, check=False
        )

    def _run(self) -> None:
        while not self._stopping.is_set():
            self._refresh()
            self._stopping.wait(self.poll_interval)

    def _refresh(self) -> None:
        try:
            result = self._command("devices")
        except (OSError, subprocess.TimeoutExpired) as error:
            self.status = f"ADB is unavailable: {error}"
            self.devices = ()
            return
        if result.returncode:
            self.status = result.stderr.strip() or "Could not query ADB devices"
            self.devices = ()
            return

        authorized = []
        unauthorized = 0
        for line in result.stdout.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2 and fields[1] == "device":
                authorized.append(fields[0])
            elif len(fields) >= 2 and fields[1] == "unauthorized":
                unauthorized += 1

        self.devices = tuple(authorized)
        if not authorized:
            self.profile = None
            self.status = (
                "Unlock the phone and approve its USB debugging prompt"
                if unauthorized else "USB ready when an authorized Android phone is connected"
            )
            return

        failures = []
        detected_profile = None
        for serial in authorized:
            try:
                mapping = f"tcp:{self.port}"
                result = self._command("-s", serial, "reverse", mapping, mapping)
                if result.returncode:
                    failures.append(result.stderr.strip() or serial)
                if detected_profile is None:
                    detected_profile = self._device_profile(serial)
            except (OSError, subprocess.TimeoutExpired) as error:
                failures.append(str(error))
        self.profile = detected_profile
        self.status = (
            "USB connected — open http://127.0.0.1:%d/receiver on the phone" % self.port
            if not failures else "USB forwarding failed: " + "; ".join(failures)
        )

    def _device_profile(self, serial: str):
        """Read the connected Android's active raster and display refresh rate."""
        try:
            size = self._command("-s", serial, "shell", "wm", "size")
            display = self._command("-s", serial, "shell", "dumpsys", "display")
            if size.returncode:
                return None
            sizes = re.findall(r"(\d{3,5})x(\d{3,5})", size.stdout)
            if not sizes:
                return None
            width, height = max(((int(w), int(h)) for w, h in sizes), key=lambda pair: pair[0] * pair[1])
            active_rate = re.search(r"renderFrameRate\s*[=: ]\s*(\d{2,3}(?:\.\d+)?)", display.stdout, re.I)
            rates = [float(value) for value in re.findall(r"(?:refreshRate|fps|刷新率)[^\d]{0,16}(\d{2,3}(?:\.\d+)?)", display.stdout, re.I)]
            detected_rate = float(active_rate.group(1)) if active_rate else (max(rates) if rates else 60)
            rate = min((30, 60, 90, 120), key=lambda candidate: abs(candidate - detected_rate))
            # The receiver locks to landscape, so configure its widest orientation.
            width, height = max(width, height), min(width, height)
            return {"width": width, "height": height, "refresh_rate": rate, "device": serial}
        except (OSError, subprocess.TimeoutExpired, StopIteration):
            return None
