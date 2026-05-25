import os
from pathlib import Path


class Config:
    def __init__(self) -> None:
        # Load .env file dynamically if it exists to support local execution
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if (val.startswith('"') and val.endswith('"')) or (
                            val.startswith("'") and val.endswith("'")
                        ):
                            val = val[1:-1]
                        if key not in os.environ:
                            os.environ[key] = val

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
        prompt_path = Path(__file__).parent / "prompt.md"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.gemini_system_prompt: str = f.read().strip()
        else:
            self.gemini_system_prompt: str = os.getenv(
                "GEMINI_SYSTEM_PROMPT",
                "Analyze this school email and summarize the main points, action items, and deadlines.",
            )
