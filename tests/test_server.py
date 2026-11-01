"""
Unit tests for screenshot-ocr-server.
Tests HTTP request handling, authentication, and error cases.
"""

import base64
import io
import json
import subprocess
import sys
import unittest
from email.message import Message
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import screenshot_ocr_server as sos


class TestScreenshotOCRServer(unittest.TestCase):

    def run_handler(self, payload, token=None, request_token=None, method="POST"):
        """Run a handler request without opening a socket."""
        if isinstance(payload, bytes):
            body = payload
        else:
            body = json.dumps(payload).encode("utf-8")

        headers = Message()
        headers["Content-Length"] = str(len(body))
        if request_token is not None:
            headers["X-Auth-Token"] = request_token

        handler = sos.RequestHandler.__new__(sos.RequestHandler)
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        handler.headers = headers
        handler.command = method
        handler.request_version = "HTTP/1.1"
        handler.requestline = f"{method} / HTTP/1.1"
        handler.client_address = ("", 0)
        handler.server = SimpleNamespace(server_name="", server_port=0)

        original_token = sos.RequestHandler.token_header
        sos.RequestHandler.token_header = token
        try:
            getattr(handler, f"do_{method}")()
        finally:
            sos.RequestHandler.token_header = original_token

        raw = handler.wfile.getvalue()
        header_bytes, response_body = raw.split(b"\r\n\r\n", 1)
        status = int(header_bytes.splitlines()[0].split()[1])
        return status, json.loads(response_body)

    def test_capture_window_missing_snap(self):
        """Test capture fails gracefully when snap.exe is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=127, stderr="not found")
            result = sos.capture_window_as_png("Test Window")
            self.assertIsNone(result)

    def test_capture_window_timeout(self):
        """Test capture handles timeout."""
        with patch("screenshot_ocr_server.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("snap.exe", 10)
            result = sos.capture_window_as_png("Test Window")
            self.assertIsNone(result)

    def test_capture_window_returns_png_and_removes_temp_file(self):
        class TemporaryFile:
            name = "capture.png"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.object(sos, "tempfile", SimpleNamespace(NamedTemporaryFile=lambda **kwargs: TemporaryFile())):
            with patch.object(sos.subprocess, "run", return_value=MagicMock(returncode=0, stderr="")):
                with patch.object(sos.Path, "read_bytes", return_value=b"\x89PNG\r\n\x1a\nimage"):
                    with patch.object(sos.os, "unlink") as unlink:
                        result = sos.capture_window_as_png("Test Window")

        self.assertEqual(result, b"\x89PNG\r\n\x1a\nimage")
        unlink.assert_called_once_with("capture.png")

    def test_capture_window_rejects_missing_or_non_png_output(self):
        class TemporaryFile:
            name = "capture.png"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        for output in (FileNotFoundError(), b"not png"):
            with self.subTest(output=output):
                with patch.object(sos, "tempfile", SimpleNamespace(NamedTemporaryFile=lambda **kwargs: TemporaryFile())):
                    with patch.object(sos.subprocess, "run", return_value=MagicMock(returncode=0, stderr="")):
                        with patch.object(sos.Path, "read_bytes", side_effect=output if isinstance(output, Exception) else None, return_value=output if not isinstance(output, Exception) else None):
                            with patch.object(sos.os, "unlink") as unlink:
                                result = sos.capture_window_as_png("Test Window")

                self.assertIsNone(result)
                unlink.assert_called_once_with("capture.png")

    def test_http_success_returns_png_and_text(self):
        png = b"\x89PNG\r\n\x1a\nimage"
        with patch.object(sos, "capture_window_as_png", return_value=png) as capture:
            with patch.object(sos, "run_ocr_on_png", return_value="hello"):
                status, response = self.run_handler({"window": "Editor"})

        self.assertEqual(status, 200)
        self.assertEqual(response["window"], "Editor")
        self.assertEqual(base64.b64decode(response["png_base64"]), png)
        self.assertEqual(response["text"], "hello")
        capture.assert_called_once_with("Editor", snap_cmd=sos.RequestHandler.snap_cmd)

    def test_http_rejects_invalid_json_shapes_and_window_names(self):
        cases = [
            (b"not json", "invalid request"),
            (["Editor"], "invalid request"),
            ({"window": 42}, "window name required"),
            ({"window": "   "}, "window name required"),
        ]
        for payload, error in cases:
            with self.subTest(payload=payload):
                status, response = self.run_handler(payload)
                self.assertEqual(status, 400)
                self.assertEqual(response, {"error": error})

    def test_http_requires_token_before_capture(self):
        with patch.object(sos, "capture_window_as_png") as capture:
            status, response = self.run_handler({"window": "Editor"}, token="secret")

        self.assertEqual(status, 401)
        self.assertEqual(response, {"error": "unauthorized"})
        capture.assert_not_called()

    def test_http_success_with_matching_token_and_trimmed_window(self):
        png = b"\x89PNG\r\n\x1a\nimage"
        with patch.object(sos, "capture_window_as_png", return_value=png) as capture:
            with patch.object(sos, "run_ocr_on_png", return_value="hello"):
                status, response = self.run_handler(
                    {"window": "  Editor  "}, token="secret", request_token="secret"
                )

        self.assertEqual(status, 200)
        self.assertEqual(response["window"], "Editor")
        self.assertEqual(base64.b64decode(response["png_base64"]), png)
        self.assertEqual(response["text"], "hello")
        capture.assert_called_once_with("Editor", snap_cmd=sos.RequestHandler.snap_cmd)

    def test_http_rejects_empty_configured_token(self):
        with patch.object(sos, "capture_window_as_png") as capture:
            status, response = self.run_handler({"window": "Editor"}, token="")

        self.assertEqual(status, 401)
        self.assertEqual(response, {"error": "unauthorized"})
        capture.assert_not_called()

    def test_http_reports_capture_failure(self):
        with patch.object(sos, "capture_window_as_png", return_value=None):
            status, response = self.run_handler({"window": "Editor"})

        self.assertEqual(status, 500)
        self.assertEqual(response, {"error": "capture failed"})

    def test_http_rejects_non_post_requests(self):
        status, response = self.run_handler({}, method="GET")
        self.assertEqual(status, 405)
        self.assertEqual(response, {"error": "method not allowed"})

    def test_ocr_fallback_when_no_pytesseract(self):
        """Test OCR returns fallback message when pytesseract unavailable."""
        with patch.dict(sys.modules, {"pytesseract": None, "PIL": None}):
            text = sos.run_ocr_on_png(b"fake png data")
        self.assertIn("OCR unavailable", text)

    def test_ocr_with_invalid_png(self):
        """Test OCR handles invalid PNG gracefully."""
        text = sos.run_ocr_on_png(b"not a png")
        self.assertTrue("error" in text.lower() or "unavailable" in text.lower())

    def test_token_header_attribute(self):
        """Test RequestHandler token header attribute can be set."""
        original = sos.RequestHandler.token_header
        sos.RequestHandler.token_header = "test-token"
        self.assertEqual(sos.RequestHandler.token_header, "test-token")
        sos.RequestHandler.token_header = original

    def test_snap_cmd_attribute(self):
        """Test RequestHandler snap_cmd attribute can be set."""
        original = sos.RequestHandler.snap_cmd
        sos.RequestHandler.snap_cmd = "custom-snap.exe"
        self.assertEqual(sos.RequestHandler.snap_cmd, "custom-snap.exe")
        sos.RequestHandler.snap_cmd = original


if __name__ == "__main__":
    unittest.main()
