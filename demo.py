"""
Demo client for screenshot-ocr-server.
Shows how to call the HTTP endpoint.
"""

import base64
import binascii
import json
import re
import sys

try:
    from urllib.request import Request, urlopen
except ImportError:
    print("Error: Python 3 required", file=sys.stderr)
    sys.exit(1)


REQUEST_TIMEOUT_SECONDS = 10
_WINDOW_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_WINDOW_RESERVED_NAMES = {
    "AUX",
    "CON",
    "NUL",
    "PRN",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def output_filename(window_name: str) -> str:
    """Create a simple filename without accepting path components."""
    filename = _WINDOW_FILENAME_RE.sub("_", window_name).strip("._")
    if not filename or filename.split(".", 1)[0].upper() in _WINDOW_RESERVED_NAMES:
        filename = "screenshot"
    return f"{filename[:100]}.png"


def get_window_screenshot(window_name: str, server_url: str = "http://localhost:8888", token: str = None):
    """Get screenshot and OCR text for a window."""
    payload = {"window": window_name}
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Auth-Token"] = token

    req = Request(server_url, data=json.dumps(payload).encode(), headers=headers, method="POST")

    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception:
        print("Error requesting screenshot", file=sys.stderr)
        return None


def main():
    print("screenshot-ocr-server demo client")
    print()

    window_name = "Notepad"
    print(f"Requesting screenshot of '{window_name}'...")
    print()

    result = get_window_screenshot(window_name)
    if not result:
        print("Failed to get screenshot", file=sys.stderr)
        return

    if "error" in result:
        print(f"Server error: {result['error']}", file=sys.stderr)
        return

    # Save PNG
    try:
        png_bytes = base64.b64decode(result["png_base64"], validate=True)
        png_file = output_filename(window_name)
        with open(png_file, "wb") as f:
            f.write(png_bytes)
    except (KeyError, TypeError, ValueError, binascii.Error, OSError):
        print("Invalid screenshot response", file=sys.stderr)
        return
    print(f"PNG saved to: {png_file}")
    print()

    # Show OCR text
    print("OCR text:")
    print("-" * 40)
    print(result["text"])
    print("-" * 40)


if __name__ == "__main__":
    main()
