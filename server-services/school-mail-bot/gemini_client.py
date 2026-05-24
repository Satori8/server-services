import base64
import mimetypes
from pathlib import Path
import httpx
import logging
from config import Config
from key_manager import GeminiKeyManager

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, config: Config, key_manager: GeminiKeyManager) -> None:
        self.config = config
        self.key_manager = key_manager

    def _file_to_part(self, filepath: Path) -> dict:
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = "application/octet-stream"

        with open(filepath, "rb") as f:
            data = f.read()

        b64_data = base64.b64encode(data).decode("utf-8")
        return {"inlineData": {"mimeType": mime_type, "data": b64_data}}

    def query(self, email_body: str, attachments: list[Path]) -> str:
        parts = [
            {
                "text": f"System Prompt: {self.config.gemini_system_prompt}\n\nEmail Body:\n{email_body}"
            }
        ]

        for path in attachments:
            parts.append(self._file_to_part(path))

        payload = {"contents": [{"parts": parts}]}

        # Keep trying keys if rate limits or failures are encountered
        attempts = len(self.key_manager.keys) if self.key_manager.keys else 1
        for _ in range(attempts):
            api_key = self.key_manager.get_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.gemini_model}:generateContent?key={api_key}"

            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(url, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return text
                    elif response.status_code in (429, 500, 503):
                        logger.warning(
                            f"Key failed with status {response.status_code}. Placing on cooldown."
                        )
                        self.key_manager.mark_cooldown(api_key, cooldown_seconds=300)
                    else:
                        logger.error(
                            f"Gemini API error (Status {response.status_code}): {response.text}"
                        )
                        self.key_manager.mark_cooldown(api_key, cooldown_seconds=300)
            except Exception as e:
                logger.error(f"Exception during Gemini call: {e}")
                self.key_manager.mark_cooldown(api_key, cooldown_seconds=120)

        raise RuntimeError("Failed to query Gemini API: all attempts/keys exhausted.")
