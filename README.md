# MultiDisplay

Turn smartphones, iPads, and spare devices into virtual displays for macOS using Python.

## Features

- **Virtual Display Creation** - Create additional monitors on macOS using CoreGraphics/CoreDisplay APIs
- **Screen Capture** - Capture virtual displays with macOS CoreGraphics
- **Frame Streaming** - Stream the latest JPEG frames over an HTTP MJPEG connection
- **Touch Input** - Send pointer, wheel, and keyboard events back to the Mac after pairing
- **Multi-Device Support** - Connect multiple receivers simultaneously

## Installation

```bash
pip install multidisplay
```

## Quick Start

### Start the host (on your Mac)

```bash
multidisplay dashboard
```

This opens the control dashboard in a native macOS window. Create a virtual display, then use the
receiver URL and pairing code shown in the dashboard. macOS must grant MultiDisplay
Screen Recording permission before frames can be captured.

To serve the dashboard without opening a native window, use `multidisplay dashboard --browser`
and open `http://127.0.0.1:8765` in a browser.

### Connect Android

Install the debug APK from `android/app/build/outputs/apk/debug/app-debug.apk`,
enter the Mac's Wi-Fi address and receiver port, and open the receiver page. Pair
with the code from the dashboard, select a virtual display, and use the rendered
display as a touch surface. For USB, enable and authorize Android USB debugging;
the dashboard maintains an ADB reverse tunnel and the app connects to
`http://127.0.0.1:51820/receiver`.

The Android app is a thin WebView receiver, so its input and stream behavior is
provided by the host's receiver page. The Mac and Android device must be able to
reach the receiver port on the local network.

### List Available Displays

```bash
multidisplay list
```

### Open the local dashboard

```bash
multidisplay dashboard
```

The native window shows detected displays and lets you create or remove virtual display configurations. The `--browser` mode serves the same interface at <http://127.0.0.1:8765>.

## Architecture

```
┌─────────────┐       HTTP/MJPEG 51820     ┌──────────────┐
│   Sender     │ ←────────────────────────→│   Receiver   │
│ (Your Mac)   │                            │ (Smartphone) │
├─────────────┤                            ├──────────────┤
│ • Capture    │                            │ • Receive    │
│ • Encode     │                            │ • WebView    │
│ • Stream     │ ←── JSON input ─────────── │ • Touch     │
└─────────────┘                            └──────────────┘

Host: Python, PyObjC CoreGraphics, HTTP server
Android: Kotlin Activity hosting a browser-native MJPEG receiver
```

## Tech Stack

- **Python 3.9+** - Core application language
- **PyObjC Quartz/AppKit** - Virtual display management and screen capture
- **HTTP/MJPEG** - Browser-native frame streaming
- **JSON over HTTP** - Paired pointer and keyboard input
- **ADB reverse** - Optional USB receiver connectivity

## License

MultiDisplay is released under the [MIT License](LICENSE).

## Security

MultiDisplay is intended for a trusted local network. The dashboard stays on
`127.0.0.1` by default, while the Android receiver uses HTTP and a pairing
code because it must be reachable over Wi-Fi or ADB reverse. Do not expose the
receiver port to the public Internet or share the pairing code. See
[SECURITY.md](SECURITY.md) for the deployment model and private vulnerability
reporting process.
