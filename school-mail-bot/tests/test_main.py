import unittest
from unittest.mock import MagicMock, patch
import main


class TestMainLoop(unittest.TestCase):
    @patch("main.Config")
    @patch("main.GeminiKeyManager")
    @patch("main.IMAPBot")
    @patch("main.GeminiClient")
    @patch("main.TelegramClient")
    def test_run_orchestrator(
        self, mock_tc, mock_gc, mock_bot, mock_km, mock_config
    ) -> None:
        # Configure Mocks
        bot_instance = mock_bot.return_value
        bot_instance.connect.return_value = MagicMock()
        bot_instance.fetch_unseen_emails.return_value = [("123", MagicMock())]
        bot_instance.is_allowed_sender.return_value = True
        bot_instance.parse_email_message.return_value = ("Hello body", [])

        gemini_instance = mock_gc.return_value
        gemini_instance.query.return_value = "Gemini output"

        tel_instance = mock_tc.return_value
        tel_instance.send_message.return_value = True

        # Run main runner
        main.run()

        # Verify the pipeline worked
        bot_instance.is_allowed_sender.assert_called_once()
        gemini_instance.query.assert_called_once()
        tel_instance.send_message.assert_called_once_with("Gemini output")
        bot_instance.mark_seen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
