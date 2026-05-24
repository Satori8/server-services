import unittest
from unittest.mock import MagicMock, patch
from gemini_client import GeminiClient
from config import Config
from key_manager import GeminiKeyManager


class TestGeminiClient(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MagicMock(spec=Config)
        self.config.gemini_model = "gemini-2.5-flash"
        self.config.gemini_system_prompt = "Summarize this email."

        self.key_manager = MagicMock(spec=GeminiKeyManager)
        self.key_manager.get_key.return_value = "mock_key_1"
        self.key_manager.keys = ["mock_key_1"]

    @patch("httpx.Client")
    def test_query_gemini_success(self, mock_httpx) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]
            },
        )

        gc = GeminiClient(self.config, self.key_manager)
        response = gc.query("Original email body", [])
        self.assertEqual(response, "Summarized content")


if __name__ == "__main__":
    unittest.main()
