"""
screenshot-ocr-server
Local HTTP server: POST a window name, get back a PNG and its OCR text.
Capture is delegated to snap.exe. OCR is optional.
"""

import argparse
import base64
import http.server
import io
import json
import os
import socketserver
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


__version__ = "0.1.0"


def run_ocr_on_png(png_data: bytes) -> str:
    """
    Attempt to extract text from PNG using pytesseract.
    Returns a clear status message if the optional OCR packages are unavailable.
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(png_data))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        return "[OCR unavailable: install pytesseract, Pillow, and Tesseract]"
    except Exception as e:
        return f"[OCR error: {str(e)}]"


def capture_window_as_png(window_name: str, snap_cmd: str = "snap.exe") -> Optional[bytes]:
    """
    Capture a window to PNG using snap.exe.
    Returns PNG bytes or None if capture failed.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [snap_cmd, "--window", window_name, "--output", tmp_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        png_data = Path(tmp_path).read_bytes()
        if not png_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return None

        return png_data
    except Exception as e:
        print(f"Capture error: {e}", file=sys.stderr)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


class RequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for screenshot-ocr-server."""

    # Server configuration
    token_header = None  # Set from main
    snap_cmd = "snap.exe"

    def send_json(self, status: int, payload: dict) -> None:
        """Write a JSON response with a complete response body."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def method_not_allowed(self) -> None:
        """Reject methods other than POST with the API's JSON error shape."""
        self.send_json(405, {"error": "method not allowed"})

    def do_GET(self):
        self.method_not_allowed()

    def do_PUT(self):
        self.method_not_allowed()

    def do_PATCH(self):
        self.method_not_allowed()

    def do_DELETE(self):
        self.method_not_allowed()

    def do_POST(self):
        """Handle POST requests."""
        # Check authorization token if set
        if self.token_header:
            auth = self.headers.get("X-Auth-Token", "")
            if auth != self.token_header:
                self.send_json(401, {"error": "unauthorized"})
                return

        # Parse request
        try:
            content_length = int(self.headers.get("Content-Length", ""))
            if content_length < 0:
                raise ValueError("negative content length")
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid request"})
            return

        if not isinstance(data, dict):
            self.send_json(400, {"error": "invalid request"})
            return

        window_name = data.get("window")
        if not isinstance(window_name, str) or not window_name.strip():
            self.send_json(400, {"error": "window name required"})
            return
        window_name = window_name.strip()

        # Capture window
        png_data = capture_window_as_png(window_name, snap_cmd=self.snap_cmd)
        if png_data is None:
            self.send_json(500, {"error": "capture failed"})
            return

        # Extract text from PNG
        text = run_ocr_on_png(png_data)

        # Return response
        response = {
            "window": window_name,
            "png_base64": base64.b64encode(png_data).decode(),
            "text": text
        }

        self.send_json(200, response)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    """Start the screenshot-ocr server."""
    parser = argparse.ArgumentParser(
        description="Local HTTP server for screenshot + OCR."
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Bind address (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Bind port (default: 8888)"
    )
    parser.add_argument(
        "--token",
        help="Optional auth token header (X-Auth-Token)"
    )
    parser.add_argument(
        "--snap",
        default="snap.exe",
        help="Path to snap.exe (default: snap.exe)"
    )

    args = parser.parse_args()

    # Set up handler
    RequestHandler.token_header = args.token
    RequestHandler.snap_cmd = args.snap

    # Create server
    address = (args.host, args.port)
    with socketserver.TCPServer(address, RequestHandler) as httpd:
        print(f"screenshot-ocr-server listening on {args.host}:{args.port}")
        print(f"Auth token: {'required' if args.token else 'disabled'}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
