import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import demo


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class TestDemo(unittest.TestCase):
    def test_output_filename_cannot_escape_current_directory(self):
        self.assertEqual(demo.output_filename("..\\..\\private"), "private.png")
        self.assertEqual(demo.output_filename("CON"), "screenshot.png")
        self.assertEqual(demo.output_filename("CON.txt"), "screenshot.png")

    def test_client_uses_request_timeout(self):
        with patch.object(demo, "urlopen", return_value=FakeResponse({"ok": True})) as urlopen:
            result = demo.get_window_screenshot("Editor")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], demo.REQUEST_TIMEOUT_SECONDS)

    def test_client_does_not_log_exception_details(self):
        with patch.object(demo, "urlopen", side_effect=RuntimeError("private-marker")):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = demo.get_window_screenshot("Editor")

        self.assertIsNone(result)
        self.assertEqual(stderr.getvalue(), "Error requesting screenshot\n")


if __name__ == "__main__":
    unittest.main()
