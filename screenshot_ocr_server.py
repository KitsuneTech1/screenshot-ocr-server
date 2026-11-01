"""
screenshot-ocr-server
Local HTTP server: POST a window name, get back a PNG and its OCR text.
Capture is delegated to snap.exe. OCR is optional.
"""

import argparse
import base64
import http.server
import ipaddress
import io
import json
import os
import secrets
import socketserver
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


__version__ = "0.1.0"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_PNG_BYTES = 20 * 1024 * 1024
MAX_WINDOW_NAME_LENGTH = 512
CAPTURE_TIMEOUT_SECONDS = 10
REQUEST_TIMEOUT_SECONDS = 10


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
    except Exception:
        return "[OCR error]"


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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CAPTURE_TIMEOUT_SECONDS,
            check=False,
        )

        if result.returncode != 0:
            return None

        with Path(tmp_path).open("rb") as png_file:
            png_data = png_file.read(MAX_PNG_BYTES + 1)

        if len(png_data) > MAX_PNG_BYTES:
            return None
        if not png_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return None

        return png_data
    except Exception:
        print("Capture error", file=sys.stderr)
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
    timeout = REQUEST_TIMEOUT_SECONDS
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
        if self.token_header is not None:
            auth = self.headers.get("X-Auth-Token", "")
            if not self.token_header or not secrets.compare_digest(
                auth, self.token_header
            ):
                self.send_json(401, {"error": "unauthorized"})
                return

        # Parse request
        try:
            content_length = int(self.headers.get("Content-Length", ""))
            if content_length < 0:
                raise ValueError("negative content length")
            if content_length > MAX_REQUEST_BYTES:
                self.send_json(413, {"error": "request too large"})
                return
            body = self.rfile.read(content_length)
            if len(body) != content_length:
                raise ValueError("incomplete request body")
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError, RecursionError):
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
        if len(window_name) > MAX_WINDOW_NAME_LENGTH:
            self.send_json(400, {"error": "window name too long"})
            return

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


def validate_bind_security(host: str, token: Optional[str]) -> None:
    """Require authentication when binding anywhere beyond loopback."""
    normalized_host = host.strip().lower()
    is_loopback = normalized_host == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            is_loopback = False

    if not is_loopback and not token:
        raise ValueError("--token is required when --host is not loopback")


def port_number(value: str) -> int:
    """Parse a valid TCP port for argparse."""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def non_empty_token(value: str) -> str:
    """Reject an empty CLI token that would make authentication unusable."""
    if not value or not value.strip():
        raise argparse.ArgumentTypeError("token must not be empty")
    return value


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
        type=port_number,
        default=8888,
        help="Bind port (default: 8888)"
    )
    parser.add_argument(
        "--token",
        type=non_empty_token,
        help="Optional auth token header (X-Auth-Token)"
    )
    parser.add_argument(
        "--snap",
        default="snap.exe",
        help="Path to snap.exe (default: snap.exe)"
    )

    args = parser.parse_args()

    try:
        validate_bind_security(args.host, args.token)
    except ValueError as exc:
        parser.error(str(exc))

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
