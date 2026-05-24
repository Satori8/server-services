import time
from pathlib import Path


class GeminiKeyManager:
    def __init__(self, filepath: str | Path) -> None:
        self.filepath = Path(filepath)
        self.keys: list[str] = self._load_keys()
        self.cooldowns: dict[str, float] = {}

    def _load_keys(self) -> list[str]:
        try:
            keys = []
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    keys.append(line)
            return keys
        except FileNotFoundError:
            return []

    def get_key(self) -> str:
        if not self.keys:
            raise RuntimeError("No Gemini API keys loaded from keys.txt")

        now = time.time()
        for key in self.keys:
            cooldown_until = self.cooldowns.get(key, 0.0)
            if now >= cooldown_until:
                return key

        raise RuntimeError("All Gemini API keys are currently on cooldown")

    def mark_cooldown(self, key: str, cooldown_seconds: float = 300.0) -> None:
        if key in self.keys:
            self.cooldowns[key] = time.time() + cooldown_seconds
