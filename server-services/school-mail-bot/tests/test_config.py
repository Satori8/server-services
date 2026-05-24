import unittest
from unittest.mock import patch
from config import Config


class TestConfig(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "EMAIL_ADDRESS": "test@gmail.com",
            "EMAIL_PASSWORD": "password123",
            "ALLOWED_SENDERS": "sender1@gmail.com,sender2@gmail.com",
            "TELEGRAM_BOT_TOKEN": "token123",
            "TELEGRAM_CHAT_IDS": "1111,2222",
            "IMAP_SERVER": "imap.test.com",
        },
    )
    def test_load_valid_config(self) -> None:
        cfg = Config()
        self.assertEqual(cfg.email_address, "test@gmail.com")
        self.assertEqual(cfg.email_password, "password123")
        self.assertEqual(
            cfg.allowed_senders, ["sender1@gmail.com", "sender2@gmail.com"]
        )
        self.assertEqual(cfg.telegram_chat_ids, ["1111", "2222"])
        self.assertEqual(cfg.imap_server, "imap.test.com")
        self.assertEqual(cfg.imap_port, 993)
        self.assertEqual(cfg.gemini_model, "gemini-2.5-flash")

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_config_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Config()


if __name__ == "__main__":
    unittest.main()
