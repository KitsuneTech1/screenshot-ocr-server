<p align="center"><a href="https://kitsunetechnologies.org/work"><img src="https://raw.githubusercontent.com/KitsuneTech1/.github/main/assets/kitsune-banner.svg" alt="Built by Kitsune Technologies" width="760"></a></p>

# Sightline Local

HTTP server for Windows that captures window screenshots and extracts text via OCR.

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) ![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)

Post a window name to the server. It captures the window to PNG (using `snap.exe`), runs OCR if available, and returns both the image and extracted text. The server binds to localhost by default and does not activate windows or send input.

## Quick start

Clone the repo and start the server:

```bash
git clone https://github.com/KitsuneTech1/screenshot-ocr-server.git
cd screenshot-ocr-server
python screenshot_ocr_server.py
```

The server listens on `http://localhost:8888` by default.

## Requirements

- Python 3.8 or newer
- Windows
- `snap.exe` in PATH (or provide its path with `--snap`)

## Optional: Enable OCR

OCR is optional. If `pytesseract` and `Pillow` are not installed, the server still returns the PNG and reports OCR unavailable.

To enable OCR, install the packages and Tesseract:

```bash
python -m pip install pytesseract Pillow
```

Then install Tesseract separately and make sure its command is available to your environment.

## Configuration

Command-line options:

- `--host`: Bind address. Defaults to `localhost`.
- `--port`: Listen port. Defaults to `8888`.
- `--token`: API token. Required if binding to a non-loopback address.
- `--snap`: Path to `snap.exe`. Defaults to `snap.exe`.

Authentication is optional on localhost. If you bind to a non-loopback address, you must provide `--token`. Screenshots can contain sensitive information, so use authentication when binding remotely.

## API

Send a JSON POST request:

```bash
curl -X POST http://localhost:8888 \
  -H "Content-Type: application/json" \
  -d '{"window": "Notepad"}'
```

Response:

```json
{
  "window": "Notepad",
  "png_base64": "iVBORw0KGgoAAAANS...",
  "text": "text extracted from the window"
}
```

With authentication:

```bash
curl -X POST http://localhost:8888 \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your-secret-token" \
  -d '{"window": "Notepad"}'
```

The server returns JSON for errors, missing auth, and capture failures. Failed captures return HTTP 500. OCR failures do not discard a successful PNG.

Limits: 1 MiB request body, 512-character window names, 20 MiB PNG, 10-second request timeout.

## Examples

Run the demo client (requires server running):

```bash
python demo.py
```

It captures a Notepad window, saves the PNG, and prints the extracted text.

## Testing

Run the test suite:

```bash
python -m unittest discover tests
```

Tests use mocks and do not capture real windows, call `snap.exe`, or make network requests.

## License

MIT. Copyright (c) 2026 Kitsune Technologies LLC. Do what you like with it, commercially or otherwise, just keep the copyright notice. Full text in [LICENSE](LICENSE).

---

<p align="center"><sub>Part of <b>Buildtober 2026</b>: 31 open source projects in 31 days. Built by <a href="https://kitsunetechnologies.org/work">Kitsune Technologies</a>. More at <a href="https://github.com/KitsuneTech1">github.com/KitsuneTech1</a>.</sub></p>
