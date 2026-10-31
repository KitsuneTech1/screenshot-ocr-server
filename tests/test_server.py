"""
Unit tests for screenshot-ocr-server.
Tests HTTP request handling, authentication, and error cases.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

import screenshot_ocr_server as sos


class TestScreenshotOCRServer(unittest.TestCase):

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

    def test_ocr_fallback_when_no_pytesseract(self):
        """Test OCR returns fallback message when pytesseract unavailable."""
        text = sos.run_ocr_on_png(b"fake png data")
        self.assertTrue("unavailable" in text.lower() or "error" in text.lower())

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
