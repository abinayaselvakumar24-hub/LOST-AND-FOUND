import os
import unittest
from unittest.mock import patch

import httpx

import main


class ExtractEntitiesTests(unittest.TestCase):
    def test_http_transport_error_uses_offline_extractor(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "main.call_gemini",
                side_effect=httpx.ConnectError(
                    "[SSL: UNEXPECTED_EOF_WHILE_READING]"
                ),
            ):
                entities = main.extract_entities("A red Samsung phone")

        self.assertEqual(entities["item"], "phone")
        self.assertEqual(entities["colour"], "red")
        self.assertEqual(entities["brand"], "Samsung")


if __name__ == "__main__":
    unittest.main()
