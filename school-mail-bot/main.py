import logging
import sys
from pathlib import Path
from config import Config
from key_manager import GeminiKeyManager
from imap_bot import IMAPBot
from gemini_client import GeminiClient
from telegram_client import TelegramClient

# Configure basic logging with stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("school-mail-bot")


def run() -> None:
    # 1. Load config
    try:
        config = Config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    # 2. Load API keys
    key_manager = GeminiKeyManager("keys.txt")
    if not key_manager.keys:
        logger.error("No keys found in keys.txt. Please populate it.")
        return

    # 3. Instantiate bot elements
    bot = IMAPBot(config)
    gemini = GeminiClient(config, key_manager)
    telegram = TelegramClient(config)

    # 4. Process email queue
    try:
        logger.info("Connecting to IMAP server...")
        mail_connection = bot.connect()
    except Exception as e:
        logger.error(f"IMAP login failure: {e}")
        return

    try:
        emails = bot.fetch_unseen_emails(mail_connection)
        logger.info(f"Found {len(emails)} unseen email(s).")

        for email_id, message in emails:
            sender = message.get("From", "")
            if not bot.is_allowed_sender(sender):
                logger.info(
                    f"Skipping email {email_id} from disallowed sender: {sender}"
                )
                continue

            logger.info(f"Processing email {email_id} from {sender}...")
            body, attachments = bot.parse_email_message(message)

            try:
                # Get Gemini summary
                summary = gemini.query(body, attachments)

                # Deliver to Telegram
                if telegram.send_message(summary):
                    # Only mark as seen if Telegram delivery succeeded
                    bot.mark_seen(mail_connection, email_id)
                    logger.info(f"Successfully processed email {email_id}")
                else:
                    logger.error(
                        f"Telegram delivery failed for email {email_id}; leaving unseen"
                    )
            except Exception as e:
                logger.error(f"Error processing email {email_id}: {e}")
            finally:
                # Guarantee local storage remains totally clean
                bot.cleanup_temp_files(attachments)

    finally:
        try:
            mail_connection.logout()
        except Exception:
            pass


if __name__ == "__main__":
    run()
