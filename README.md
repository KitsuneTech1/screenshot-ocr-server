# screenshot-ocr-server

`screenshot-ocr-server` is a small HTTP server for Windows. Send it a window name and it asks `snap.exe` for a PNG capture. The response includes the PNG as base64 and text extracted from it.

The server binds to localhost by default. It does not activate a window or send input itself.

## Requirements

- Python 3.8 or newer
- Windows
- `snap.exe` in `PATH`, or a path supplied with `--snap`

OCR is optional. Without OCR packages, the response still includes the PNG and reports that OCR is unavailable. To enable OCR, install Tesseract and the Python packages it uses:

```bash
python -m pip install pytesseract Pillow
```

Install Tesseract separately and make sure its command is available to the server process.

The HTTP server uses Python's standard library. `pytesseract` and Pillow are optional runtime dependencies for OCR only.

## Install

```bash
git clone https://github.com/KitsuneTech1/screenshot-ocr-server.git
cd screenshot-ocr-server
```

## Run

```bash
python screenshot_ocr_server.py
```

Options:

- `--host`: Address to bind to. Defaults to `localhost`.
- `--port`: Port to bind to. Defaults to `8888`.
- `--token`: Require this value in the `X-Auth-Token` header.
- `--snap`: Path or command name for `snap.exe`. Defaults to `snap.exe`.

Do not bind to a public interface unless you understand the risk. Screenshots can contain sensitive information.

## API

Send a JSON POST request to `http://localhost:8888`:

```json
{
  "window": "Notepad"
}
```

A successful response is JSON:

```json
{
  "window": "Notepad",
  "png_base64": "iVBORw0KGgoAAAANS...",
  "text": "text extracted from the window"
}
```

Example with authentication:

```bash
curl -X POST http://localhost:8888 \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your-secret-token" \
  -d '{"window": "Notepad"}'
```

The POST endpoint returns JSON errors for invalid requests, missing authentication, and failed captures. Other methods are not supported. A failed capture returns HTTP 500. OCR failures do not discard a successful PNG capture.

## Demo client

Start the server, then run:

```bash
python demo.py
```

The demo requests a window named `Notepad`, saves the returned PNG in the current directory, and prints the returned text.

## Tests

```bash
python -m unittest discover tests
```

The tests use mocks. They do not open windows, send input, call `snap.exe`, or make network requests.

## License

MIT License. Copyright (c) 2026 KitsuneTech1.
