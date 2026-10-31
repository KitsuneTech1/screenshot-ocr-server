"""
Demo client for screenshot-ocr-server.
Shows how to call the HTTP endpoint.
"""

import base64
import json
import sys
from pathlib import Path

try:
    from urllib.request import Request, urlopen
except ImportError:
    print("Error: Python 3 required", file=sys.stderr)
    sys.exit(1)


def get_window_screenshot(window_name: str, server_url: str = "http://127.0.0.1:8888", token: str = None):
    """Get screenshot and OCR text for a window."""
    payload = {"window": window_name}
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Auth-Token"] = token

    req = Request(server_url, data=json.dumps(payload).encode(), headers=headers, method="POST")

    try:
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
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
    png_bytes = base64.b64decode(result["png_base64"])
    png_file = f"{window_name.replace(' ', '_')}.png"
    with open(png_file, "wb") as f:
        f.write(png_bytes)
    print(f"PNG saved to: {png_file}")
    print()

    # Show OCR text
    print("OCR text:")
    print("-" * 40)
    print(result["text"])
    print("-" * 40)


if __name__ == "__main__":
    main()
