"""
Unit tests for screenshot-ocr-server.
Tests HTTP request handling, authentication, and error cases.
"""

import base64
import argparse
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from email.message import Message
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import screenshot_ocr_server as sos


class TestScreenshotOCRServer(unittest.TestCase):

    def run_handler(
        self,
        payload,
        token=None,
        request_token=None,
        method="POST",
        content_length=None,
    ):
        """Run a handler request without opening a socket."""
        if isinstance(payload, bytes):
            body = payload
        else:
            body = json.dumps(payload).encode("utf-8")

        headers = Message()
        headers["Content-Length"] = str(
            len(body) if content_length is None else content_length
        )
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
                with patch.object(
                    sos.Path,
                    "open",
                    return_value=io.BytesIO(b"\x89PNG\r\n\x1a\nimage"),
                ):
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
                        with patch.object(sos.Path, "open", side_effect=output if isinstance(output, Exception) else None, return_value=io.BytesIO(output) if not isinstance(output, Exception) else None):
                            with patch.object(sos.os, "unlink") as unlink:
                                result = sos.capture_window_as_png("Test Window")

                self.assertIsNone(result)
                unlink.assert_called_once_with("capture.png")

    def test_capture_window_limits_output_size(self):
        class TemporaryFile:
            name = "capture.png"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.object(sos, "MAX_PNG_BYTES", 8):
            with patch.object(
                sos,
                "tempfile",
                SimpleNamespace(
                    NamedTemporaryFile=lambda **kwargs: TemporaryFile()
                ),
            ):
                with patch.object(
                    sos.subprocess,
                    "run",
                    return_value=MagicMock(returncode=0),
                ):
                    with patch.object(
                        sos.Path,
                        "open",
                        return_value=io.BytesIO(b"\x89PNG\r\n\x1a\n!") ,
                    ):
                        with patch.object(sos.os, "unlink"):
                            result = sos.capture_window_as_png("Test Window")

        self.assertIsNone(result)

    def test_capture_window_does_not_capture_child_output(self):
        class TemporaryFile:
            name = "capture.png"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.object(
            sos,
            "tempfile",
            SimpleNamespace(NamedTemporaryFile=lambda **kwargs: TemporaryFile()),
        ):
            with patch.object(
                sos.subprocess,
                "run",
                return_value=MagicMock(returncode=1),
            ) as run:
                with patch.object(sos.os, "unlink"):
                    sos.capture_window_as_png("Test Window")

        self.assertIs(run.call_args.kwargs["stdout"], sos.subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs["stderr"], sos.subprocess.DEVNULL)

    def test_capture_errors_do_not_log_exception_details(self):
        with patch.object(
            sos.subprocess,
            "run",
            side_effect=RuntimeError("private-marker"),
        ):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = sos.capture_window_as_png("Test Window")

        self.assertIsNone(result)
        self.assertEqual(stderr.getvalue(), "Capture error\n")

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

    def test_http_rejects_oversized_requests_before_reading_body(self):
        with patch.object(sos, "capture_window_as_png") as capture:
            status, response = self.run_handler(
                b"{}",
                content_length=sos.MAX_REQUEST_BYTES + 1,
            )

        self.assertEqual(status, 413)
        self.assertEqual(response, {"error": "request too large"})
        capture.assert_not_called()

    def test_http_rejects_oversized_window_names(self):
        status, response = self.run_handler(
            {"window": "x" * (sos.MAX_WINDOW_NAME_LENGTH + 1)}
        )

        self.assertEqual(status, 400)
        self.assertEqual(response, {"error": "window name too long"})

    def test_http_rejects_deeply_nested_json(self):
        body = b"[" * 1000 + b"]" * 1000
        status, response = self.run_handler(body)

        self.assertEqual(status, 400)
        self.assertEqual(response, {"error": "invalid request"})

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
        class ImageModule:
            @staticmethod
            def open(stream):
                raise RuntimeError("private-marker")

        with patch.dict(
            sys.modules,
            {"pytesseract": SimpleNamespace(), "PIL": SimpleNamespace(Image=ImageModule)},
        ):
            text = sos.run_ocr_on_png(b"not a png")

        self.assertEqual(text, "[OCR error]")

    def test_bind_security_requires_authentication_off_loopback(self):
        with self.assertRaises(ValueError):
            sos.validate_bind_security("0.0.0.0", None)

        sos.validate_bind_security("localhost", None)
        sos.validate_bind_security("0.0.0.0", "secret")

    def test_request_handler_has_a_socket_read_timeout(self):
        self.assertEqual(sos.RequestHandler.timeout, sos.REQUEST_TIMEOUT_SECONDS)

    def test_cli_value_parsers_reject_invalid_security_values(self):
        self.assertEqual(sos.port_number("8888"), 8888)
        self.assertEqual(sos.non_empty_token("secret"), "secret")
        with self.assertRaises(argparse.ArgumentTypeError):
            sos.port_number("70000")
        with self.assertRaises(argparse.ArgumentTypeError):
            sos.non_empty_token("   ")


if __name__ == "__main__":
    unittest.main()
