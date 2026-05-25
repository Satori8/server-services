import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
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

    @patch("time.sleep")
    @patch("httpx.Client")
    def test_query_gemini_key_rotation_delay_on_429(
        self, mock_httpx, mock_sleep
    ) -> None:
        # Mock key manager with two keys
        self.key_manager.keys = ["mock_key_1", "mock_key_2"]
        self.key_manager.get_key.side_effect = ["mock_key_1", "mock_key_2"]

        client_instance = mock_httpx.return_value.__enter__.return_value
        # First post fails with 429, second succeeds with 200
        mock_response_429 = MagicMock(status_code=429)
        mock_response_200 = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [
                    {"content": {"parts": [{"text": "Success after retry"}]}}
                ]
            },
        )
        client_instance.post.side_effect = [mock_response_429, mock_response_200]

        gc = GeminiClient(self.config, self.key_manager)
        response = gc.query("Original email body", [])

        # Should return the correct response
        self.assertEqual(response, "Success after retry")
        # Should call mark_cooldown for the first key with 429
        self.key_manager.mark_cooldown.assert_any_call(
            "mock_key_1", cooldown_seconds=300
        )
        # Should have slept for 0.5 seconds precisely once
        mock_sleep.assert_called_once_with(0.5)

    @patch("httpx.Client")
    def test_query_with_attachment_word_extracts_text(self, mock_httpx) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]
            },
        )

        gc = GeminiClient(self.config, self.key_manager)
        # Mock _extract_text_from_file to return text
        gc._extract_text_from_file = MagicMock(
            return_value="Mock attachment text contents"
        )

        # Mock _file_to_part so we can check if it was called
        gc._file_to_part = MagicMock()

        email_body = "Hello! Please find the attachment here."
        mock_path = Path("temp/notes.txt")

        gc.query(email_body, [mock_path])

        # _extract_text_from_file should have been called
        gc._extract_text_from_file.assert_called_once_with(mock_path)
        # _file_to_part should NOT have been called because it was extracted as text
        gc._file_to_part.assert_not_called()

        # The payload post arguments should contain the extracted text
        args, kwargs = client_instance.post.call_args
        payload = kwargs["json"]
        parts = payload["contents"][0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertIn(
            "Attachment 'notes.txt' Text Content:\nMock attachment text contents",
            parts[1]["text"],
        )

    @patch("httpx.Client")
    def test_query_without_attachment_word_sends_inlineData(self, mock_httpx) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]
            },
        )

        gc = GeminiClient(self.config, self.key_manager)
        gc._extract_text_from_file = MagicMock()
        gc._file_to_part = MagicMock(
            return_value={"inlineData": {"mimeType": "text/plain", "data": "b64"}}
        )

        email_body = "Just a normal email without the special word."
        mock_path = Path("temp/notes.txt")

        gc.query(email_body, [mock_path])

        # _extract_text_from_file should NOT be called
        gc._extract_text_from_file.assert_not_called()
        # _file_to_part should be called
        gc._file_to_part.assert_called_once_with(mock_path)

        # The payload post arguments should contain the inlineData
        args, kwargs = client_instance.post.call_args
        payload = kwargs["json"]
        parts = payload["contents"][0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(
            parts[1], {"inlineData": {"mimeType": "text/plain", "data": "b64"}}
        )


if __name__ == "__main__":
    unittest.main()
