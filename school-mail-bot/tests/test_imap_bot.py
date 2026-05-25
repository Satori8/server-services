import unittest
from unittest.mock import MagicMock, patch
from imap_bot import IMAPBot
from config import Config


class TestIMAPBot(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MagicMock(spec=Config)
        self.config.allowed_senders = ["teacher@school.com"]
        self.config.email_address = "me@gmail.com"
        self.config.email_password = "password"
        self.config.imap_server = "imap.test.com"
        self.config.imap_port = 993

    @patch("imaplib.IMAP4_SSL")
    def test_is_allowed_sender(self, mock_imap) -> None:
        bot = IMAPBot(self.config)
        self.assertTrue(bot.is_allowed_sender("teacher@school.com"))
        self.assertTrue(bot.is_allowed_sender("Teacher <teacher@school.com>"))
        self.assertFalse(bot.is_allowed_sender("spammer@school.com"))

    def test_mark_unseen(self) -> None:
        bot = IMAPBot(self.config)
        mock_mail = MagicMock()
        bot.mark_unseen(mock_mail, "123")
        mock_mail.store.assert_called_once_with("123", "-FLAGS", "\\Seen")


if __name__ == "__main__":
    unittest.main()
