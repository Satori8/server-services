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
    def test_query_with_word_document_attachment_extracts_text(
        self, mock_httpx
    ) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]
            },
        )

        gc = GeminiClient(self.config, self.key_manager)
        # Mock _extract_text_from_file to return text for .txt and None for other extensions
        gc._extract_text_from_file = MagicMock(
            side_effect=lambda path: (
                "Mock attachment text contents" if path.suffix == ".txt" else None
            )
        )

        # Mock _file_to_part so we can check if it was called
        gc._file_to_part = MagicMock(
            return_value={
                "inlineData": {
                    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "data": "docx_b64",
                }
            }
        )

        email_body = "Hello! Please find the attachment here."
        mock_path = Path("temp/notes.docx")
        mock_txt_path = Path("temp/notes.txt")

        gc.query(email_body, [mock_path, mock_txt_path])

        # _extract_text_from_file should have been called for both files
        gc._extract_text_from_file.assert_any_call(mock_path)
        gc._extract_text_from_file.assert_any_call(mock_txt_path)
        # _file_to_part should have been called for the Word document
        gc._file_to_part.assert_called_once_with(mock_path)

        # The payload post arguments should contain the extracted text
        args, kwargs = client_instance.post.call_args
        payload = kwargs["json"]
        parts = payload["contents"][0]["parts"]
        self.assertEqual(len(parts), 3)
        self.assertEqual(
            parts[1],
            {
                "inlineData": {
                    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "data": "docx_b64",
                }
            },
        )
        self.assertIn(
            "Attachment 'notes.txt' Text Content:\nMock attachment text contents",
            parts[2]["text"],
        )

    @patch("httpx.Client")
    def test_query_without_word_document_attachment_sends_inlineData_on_failure(
        self, mock_httpx
    ) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]
            },
        )

        gc = GeminiClient(self.config, self.key_manager)
        # Mock _extract_text_from_file to return None to force fallback to inlineData
        gc._extract_text_from_file = MagicMock(return_value=None)
        gc._file_to_part = MagicMock(
            return_value={"inlineData": {"mimeType": "text/plain", "data": "b64"}}
        )

        email_body = "Hello! Please find the attachment here."
        mock_path = Path("temp/notes.txt")

        gc.query(email_body, [mock_path])

        # _extract_text_from_file SHOULD be called now
        gc._extract_text_from_file.assert_called_once_with(mock_path)
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

    @patch("docx.Document")
    @patch("httpx.Client")
    def test_query_with_docx_attachment_extracts_text_using_library(
        self, mock_httpx, mock_docx
    ) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]
            },
        )

        # Mock docx.Document to return paragraphs
        mock_doc = MagicMock()
        para1 = MagicMock()
        para1.text = "Hello world"
        para2 = MagicMock()
        para2.text = "This is a docx."
        mock_doc.paragraphs = [para1, para2]
        mock_docx.return_value = mock_doc

        gc = GeminiClient(self.config, self.key_manager)

        email_body = "Attached is a word doc."
        mock_path = Path("temp/test.docx")

        # We need to make sure _extract_text_from_file is NOT mocked so we test the real logic
        # but _file_to_part SHOULD be mocked to avoid real file reading
        gc._file_to_part = MagicMock()

        gc.query(email_body, [mock_path])

        # Verify post payload contains the extracted text
        args, kwargs = client_instance.post.call_args
        payload = kwargs["json"]
        parts = payload["contents"][0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertIn("Hello world\nThis is a docx.", parts[1]["text"])
        self.assertIn("Attachment 'test.docx' Text Content:", parts[1]["text"])


if __name__ == "__main__":
    unittest.main()
