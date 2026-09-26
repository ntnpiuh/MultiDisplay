# MultiDisplay Development Reference

## Architecture

MultiDisplay has a macOS host and a browser-based Android receiver.

1. `src/display/display_manager.py` creates and releases macOS virtual displays through PyObjC's `CGVirtualDisplay` API.
2. `src/multidisplay/streaming.py` captures a selected display with CoreGraphics, encodes JPEG frames, and serves them as an MJPEG stream.
3. `src/multidisplay/web_app.py` runs the local dashboard and receiver control API. Pairing issues a session cookie before the stream or input route is usable.
4. `src/receiver/receiver_client.py` translates authenticated normalized pointer and keyboard events into Quartz events. It belongs to the legacy binary receiver path and is currently used only for input handling.
5. `android/app/src/main/java/com/multidisplay/receiver/MainActivity.kt` hosts the receiver page in a WebView. The page handles stream display and sends input events over HTTP.

The active transport is HTTP/MJPEG because Android Chrome and the WebView can decode it without a native codec dependency. The `src/protocol/` tree contains an isolated TSRI binary framing format for future transport work; it is not part of the active runtime.

## Host Workflow

Run the dashboard from the project environment:

```sh
./.venv/bin/python -m multidisplay
```

The dashboard creates virtual displays, starts capture workers, shows the receiver URL and pairing code, and reports capture errors. A receiver can connect over LAN or through the ADB reverse bridge:

```sh
adb reverse tcp:51820 tcp:51820
```

The receiver page is available at `/receiver`. It first fetches `/displays`, pairs with `POST /pair`, then loads `/stream/<display-id>`. Input is sent as JSON to `POST /api/input` with the session cookie issued by pairing.

## Input Contract

Pointer events use normalized coordinates in the inclusive range 0 to 1:

```json
{
  "type": "mouse_click",
  "display_id": 16,
  "x": 0.5,
  "y": 0.5,
  "button": "left"
}
```

Supported event types are `touch_down`, `touch_move`, `touch_up`, `mouse_move`, `mouse_click`, `mouse_wheel`, `key_down`, and `key_up`. The host maps coordinates to the configured display dimensions and rejects malformed or unsupported events.

## macOS Constraints

- A logged-in desktop session is required for virtual display creation.
- Screen Recording permission is required for CoreGraphics capture.
- `CGVirtualDisplay` is a private macOS API and may change between macOS releases.
- The display object must remain retained until `remove_virtual_display` releases it.
- Real-device validation should check display creation, a non-empty JPEG frame, pairing, stream rendering, and authenticated input injection.

## Validation

Run the host regression suite:

```sh
./.venv/bin/python -m pytest -q
```

Build the Android receiver with JDK 21 and the configured Android SDK:

```sh
JAVA_HOME=/path/to/jdk-21 ./android/gradlew -p android assembleDebug
```

The real-device workflow additionally requires Screen Recording permission, an attached Android device, and a USB reverse tunnel or reachable LAN address.
