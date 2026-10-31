"""
screenshot-ocr-server
Local HTTP server: POST a window name, get back a PNG and its OCR text.
Built on snap.exe for focus-safe capture.
Requires pytesseract and tesseract-ocr, or falls back to text extraction.
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
from pathlib import Path
from typing import Optional, Tuple


__version__ = "0.1.0"


def run_ocr_on_png(png_data: bytes) -> str:
    """
    Attempt to extract text from PNG using pytesseract.
    Falls back to a placeholder if tesseract is not available.
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(png_data))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        return "[OCR unavailable: install pytesseract and tesseract-ocr]"
    except Exception as e:
        return f"[OCR error: {str(e)}]"


def capture_window_as_png(window_name: str, snap_cmd: str = "snap.exe") -> Optional[bytes]:
    """
    Capture a window to PNG using snap.exe.
    Returns PNG bytes or None if capture failed.
    """
    import tempfile

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
            error = result.stderr.strip() or f"snap.exe returned {result.returncode}"
            return None

        with open(tmp_path, "rb") as f:
            png_data = f.read()

        os.unlink(tmp_path)
        return png_data
    except Exception as e:
        print(f"Capture error: {e}", file=sys.stderr)
        return None


class RequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for screenshot-ocr-server."""

    # Server configuration
    token_header = None  # Set from main
    snap_cmd = "snap.exe"

    def do_POST(self):
        """Handle POST requests."""
        # Check authorization token if set
        if self.token_header:
            auth = self.headers.get("X-Auth-Token", "")
            if auth != self.token_header:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
                return

        # Parse request
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid request"}).encode())
            return

        window_name = data.get("window")
        if not window_name:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "window name required"}).encode())
            return

        # Capture window
        png_data = capture_window_as_png(window_name, snap_cmd=self.snap_cmd)
        if png_data is None:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "capture failed"}).encode())
            return

        # Extract text from PNG
        text = run_ocr_on_png(png_data)

        # Return response
        response = {
            "window": window_name,
            "png_base64": base64.b64encode(png_data).decode(),
            "text": text
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

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
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)"
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
