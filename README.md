# screenshot-ocr-server

screenshot-ocr-server is a lightweight HTTP server that captures a Windows window and extracts its text via OCR.

Request a screenshot of any window by name, get back a PNG image and OCR-extracted text in one response.

## Features

- Local HTTP server on localhost by default (opt-in only)
- POST endpoint accepts window name, returns PNG and text
- Uses snap.exe for focus-safe window capture
- Optional token-based authentication
- Pure Python stdlib (http.server)
- Configurable OCR using pytesseract if available

## Requirements

- Python 3.8 or higher
- Windows
- snap.exe in PATH (focus-safe capture utility)
- pytesseract and tesseract-ocr (optional, for OCR)

## Installation

```bash
git clone https://github.com/KitsuneTech1/screenshot-ocr-server.git
cd screenshot-ocr-server
```

For OCR support, install tesseract:

```bash
# Windows with chocolatey
choco install tesseract

# Then install pytesseract
pip install pytesseract
```

## Usage

Start the server:

```bash
python screenshot_ocr_server.py
```

Options:

- `--host`: Bind address (default: 127.0.0.1, localhost only)
- `--port`: Bind port (default: 8888)
- `--token`: Optional auth token (X-Auth-Token header)
- `--snap`: Path to snap.exe (default: snap.exe in PATH)

## API

POST request to http://127.0.0.1:8888

Request body (JSON):

```json
{
  "window": "Notepad"
}
```

Response (JSON):

```json
{
  "window": "Notepad",
  "png_base64": "iVBORw0KGgoAAAANS...",
  "text": "extracted text from window..."
}
```

With authentication:

```bash
curl -X POST http://127.0.0.1:8888 \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your-secret-token" \
  -d '{"window": "Notepad"}'
```

## Security

By default, the server binds to localhost (127.0.0.1) and does not accept remote connections.

Optional token authentication can be enabled with the `--token` flag to require an X-Auth-Token header.

Never bind to 0.0.0.0 without strong authentication, as screenshot data is sensitive.

## Running the Demo Client

```bash
python demo.py
```

## Running Tests

```bash
python -m unittest discover tests
```

## License

MIT License. Copyright (c) 2026 KitsuneTech1.
