import os
from pathlib import Path


class Config:
    def __init__(self) -> None:
        self.imap_server: str = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.imap_port: int = int(os.getenv("IMAP_PORT", "993"))

        email_addr = os.getenv("EMAIL_ADDRESS")
        email_pwd = os.getenv("EMAIL_PASSWORD")
        allowed_senders = os.getenv("ALLOWED_SENDERS")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_ids = os.getenv("TELEGRAM_CHAT_IDS")

        if not all([email_addr, email_pwd, allowed_senders, bot_token, chat_ids]):
            raise ValueError("Missing required configuration variables in environment")

        self.email_address: str = email_addr
        self.email_password: str = email_pwd
        self.allowed_senders: list[str] = [
            s.strip() for s in allowed_senders.split(",") if s.strip()
        ]
        self.telegram_bot_token: str = bot_token
        self.telegram_chat_ids: list[str] = [
            c.strip() for c in chat_ids.split(",") if c.strip()
        ]

        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.gemini_system_prompt: str = os.getenv(
            "GEMINI_SYSTEM_PROMPT",
            "Analyze this school email and summarize the main points, action items, and deadlines.",
        )
