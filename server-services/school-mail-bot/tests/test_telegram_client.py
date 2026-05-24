import unittest
from unittest.mock import MagicMock, patch
from telegram_client import TelegramClient
from config import Config


class TestTelegramClient(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MagicMock(spec=Config)
        self.config.telegram_bot_token = "mock_token"
        self.config.telegram_chat_ids = ["1111", "2222"]

    @patch("httpx.Client")
    def test_send_message_split(self, mock_httpx) -> None:
        client_instance = mock_httpx.return_value.__enter__.return_value
        client_instance.post.return_value = MagicMock(status_code=200)

        tc = TelegramClient(self.config)
        # 5000 chars text
        long_text = "A" * 5000
        tc.send_message(long_text)

        # Verify post called at least twice per chat id -> total >= 4 calls
        self.assertGreaterEqual(client_instance.post.call_count, 4)


if __name__ == "__main__":
    unittest.main()
