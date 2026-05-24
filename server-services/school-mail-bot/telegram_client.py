import httpx
import logging
from config import Config

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, config: Config) -> None:
        self.config = config

    def _split_message(self, text: str, max_length: int = 4000) -> list[str]:
        if len(text) <= max_length:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break

            # Find closest newline to cut nicely
            cut_idx = text.rfind("\n", 0, max_length)
            if cut_idx == -1:
                cut_idx = max_length

            chunks.append(text[:cut_idx].strip())
            text = text[cut_idx:].strip()
        return chunks

    def send_message(self, text: str) -> bool:
        chunks = self._split_message(text)
        success_all = True

        for chat_id in self.config.telegram_chat_ids:
            for chunk in chunks:
                url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
                payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}
                try:
                    with httpx.Client(timeout=30.0) as client:
                        res = client.post(url, json=payload)
                        if res.status_code != 200:
                            logger.error(
                                f"Failed to send to Telegram chat {chat_id}: {res.text}"
                            )
                            success_all = False
                except Exception as e:
                    logger.error(f"Error calling Telegram API for chat {chat_id}: {e}")
                    success_all = False

        return success_all
