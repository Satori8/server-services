import unittest
from unittest.mock import patch, mock_open
from config import Config


class TestConfig(unittest.TestCase):
    @patch("pathlib.Path.exists")
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
    def test_load_valid_config(self, mock_exists) -> None:
        mock_exists.side_effect = [False, False]
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

    @patch("pathlib.Path.exists")
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_config_raises_value_error(self, mock_exists) -> None:
        mock_exists.side_effect = [False, False]
        with self.assertRaises(ValueError):
            Config()

    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="Custom Prompt From File")
    @patch.dict(
        "os.environ",
        {
            "EMAIL_ADDRESS": "test@gmail.com",
            "EMAIL_PASSWORD": "password123",
            "ALLOWED_SENDERS": "sender1@gmail.com",
            "TELEGRAM_BOT_TOKEN": "token123",
            "TELEGRAM_CHAT_IDS": "1111",
        },
    )
    def test_load_prompt_from_file(self, mock_file, mock_exists) -> None:
        mock_exists.side_effect = [False, True]
        cfg = Config()
        self.assertEqual(cfg.gemini_system_prompt, "Custom Prompt From File")

    @patch("pathlib.Path.exists")
    @patch.dict(
        "os.environ",
        {
            "EMAIL_ADDRESS": "test@gmail.com",
            "EMAIL_PASSWORD": "password123",
            "ALLOWED_SENDERS": "sender1@gmail.com",
            "TELEGRAM_BOT_TOKEN": "token123",
            "TELEGRAM_CHAT_IDS": "1111",
            "GEMINI_SYSTEM_PROMPT": "Env Prompt",
        },
    )
    def test_load_prompt_from_env_fallback(self, mock_exists) -> None:
        mock_exists.side_effect = [False, False]
        cfg = Config()
        self.assertEqual(cfg.gemini_system_prompt, "Env Prompt")

    @patch("pathlib.Path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="EMAIL_ADDRESS=file@gmail.com\nEMAIL_PASSWORD=filepass\nALLOWED_SENDERS=filesender@gmail.com\nTELEGRAM_BOT_TOKEN=filetoken\nTELEGRAM_CHAT_IDS=filechat\n",
    )
    @patch.dict("os.environ", {}, clear=True)
    def test_load_config_from_env_file(self, mock_file, mock_exists) -> None:
        mock_exists.side_effect = [True, False]
        cfg = Config()
        self.assertEqual(cfg.email_address, "file@gmail.com")
        self.assertEqual(cfg.email_password, "filepass")
        self.assertEqual(cfg.allowed_senders, ["filesender@gmail.com"])
        self.assertEqual(cfg.telegram_bot_token, "filetoken")
        self.assertEqual(cfg.telegram_chat_ids, ["filechat"])


if __name__ == "__main__":
    unittest.main()
