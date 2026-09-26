# Legacy Binary Protocol

This directory contains the original TSRI binary frame format, compression helpers, and audio helpers. It is intentionally isolated from the active HTTP/MJPEG dashboard and receiver flow.

The current runtime uses browser-native MJPEG transport because it works in Android Chrome and the WebView without a native codec pipeline. The TSRI modules are retained as a documented foundation for a future low-bandwidth transport; changes here must not be treated as changes to the active stream contract.
