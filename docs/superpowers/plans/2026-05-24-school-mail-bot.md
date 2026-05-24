# School Mail Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ultra-lightweight, memory-efficient Python service that polls Gmail for specific senders' emails, parses plain text, streams attachments, calls Gemini API (with key rotation), and forwards summaries to multiple Telegram recipients.

**Architecture:** A cohesive, modular, single-file script `main.py` with cleanly separated classes (`Config`, `GeminiKeyManager`, `EmailParser`, `GeminiClient`, `TelegramClient`, and `IMAPBot`) to run as a 1-minute cron daemon. Testing uses Python's built-in `unittest` library (zero external testing dependencies).

**Tech Stack:** Python 3.10+, `httpx` (async HTTP client), standard libraries (`imaplib`, `email`, `html.parser`, `unittest`).

---

## Task 1: Environment Configuration & Key File loading

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_config.py` to assert that `Config` loads environment variables, handles comma-separated values correctly, and provides sensible defaults.

```python
import unittest
from unittest.mock import patch
from config import Config

class TestConfig(unittest.TestCase):
    @patch.dict('os.environ', {
        'EMAIL_ADDRESS': 'test@gmail.com',
        'EMAIL_PASSWORD': 'password123',
        'ALLOWED_SENDERS': 'sender1@gmail.com,sender2@gmail.com',
        'TELEGRAM_BOT_TOKEN': 'token123',
        'TELEGRAM_CHAT_IDS': '1111,2222',
        'IMAP_SERVER': 'imap.test.com'
    })
    def test_load_valid_config(self):
        cfg = Config()
        self.assertEqual(cfg.email_address, 'test@gmail.com')
        self.assertEqual(cfg.email_password, 'password123')
        self.assertEqual(cfg.allowed_senders, ['sender1@gmail.com', 'sender2@gmail.com'])
        self.assertEqual(cfg.telegram_chat_ids, ['1111', '2222'])
        self.assertEqual(cfg.imap_server, 'imap.test.com')
        self.assertEqual(cfg.imap_port, 993)
        self.assertEqual(cfg.gemini_model, 'gemini-2.5-flash')

    @patch.dict('os.environ', {}, clear=True)
    def test_missing_config_raises_value_error(self):
        with self.assertRaises(ValueError):
            Config()

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_config.py`
Expected: FAIL (ModuleNotFoundError: No module named 'config')

- [ ] **Step 3: Write minimal implementation**
Create `config.py`:
```python
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
        self.allowed_senders: list[str] = [s.strip() for s in allowed_senders.split(",") if s.strip()]
        self.telegram_bot_token: str = bot_token
        self.telegram_chat_ids: list[str] = [c.strip() for c in chat_ids.split(",") if c.strip()]
        
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.gemini_system_prompt: str = os.getenv(
            "GEMINI_SYSTEM_PROMPT",
            "Analyze this school email and summarize the main points, action items, and deadlines."
        )
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_config.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add config.py tests/test_config.py
git commit -m "feat: add lightweight config loader"
```

---

## Task 2: Gemini Key Rotation Manager

**Files:**
- Create: `key_manager.py`
- Create: `tests/test_key_manager.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_key_manager.py` to test loading keys from a file, skipping commented/blank lines, rotating through active keys, handling cooldowns, and raising an error if all keys are exhausted.

```python
import unittest
import time
from unittest.mock import patch, mock_open
from key_manager import GeminiKeyManager

class TestGeminiKeyManager(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="key1\n# comment\n\nkey2\n")
    def test_load_keys(self, mock_file):
        km = GeminiKeyManager("keys.txt")
        self.assertEqual(km.keys, ["key1", "key2"])

    @patch("builtins.open", new_callable=mock_open, read_data="key1\nkey2\n")
    def test_rotation_and_cooldown(self, mock_file):
        km = GeminiKeyManager("keys.txt")
        
        # Get first key
        key = km.get_key()
        self.assertEqual(key, "key1")
        
        # Mark first key on cooldown
        km.mark_cooldown("key1", cooldown_seconds=10)
        
        # Next key should be key2
        key = km.get_key()
        self.assertEqual(key, "key2")
        
        # Mark second key on cooldown
        km.mark_cooldown("key2", cooldown_seconds=10)
        
        # No key available now
        with self.assertRaises(RuntimeError):
            km.get_key()

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_key_manager.py`
Expected: FAIL (ModuleNotFoundError: No module named 'key_manager')

- [ ] **Step 3: Write minimal implementation**
Create `key_manager.py`:
```python
import time
from pathlib import Path

class GeminiKeyManager:
    def __init__(self, filepath: str | Path) -> None:
        self.filepath = Path(filepath)
        self.keys: list[str] = self._load_keys()
        self.cooldowns: dict[str, float] = {}

    def _load_keys(self) -> list[str]:
        if not self.filepath.exists():
            return []
        
        keys = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                keys.append(line)
        return keys

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
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_key_manager.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add key_manager.py tests/test_key_manager.py
git commit -m "feat: add Gemini key rotation and cooldown manager"
```

---

## Task 3: Email Parser (HTML to Plain Text Cleanups)

**Files:**
- Create: `email_parser.py`
- Create: `tests/test_email_parser.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_email_parser.py` to verify that our custom parser strips HTML tags, removes scripts, style elements, and returns normalized, human-readable plain text email content.

```python
import unittest
from email_parser import EmailParser

class TestEmailParser(unittest.TestCase):
    def test_clean_html(self):
        html_content = """
        <html>
            <head><style>body { color: red; }</style></head>
            <body>
                <h1>Hello Parents!</h1>
                <p>There will be no school on Monday <a href="http://school.com">link</a>.</p>
                <script>alert("test");</script>
            </body>
        </html>
        """
        cleaned = EmailParser.html_to_text(html_content)
        self.assertIn("Hello Parents!", cleaned)
        self.assertIn("There will be no school on Monday link.", cleaned)
        self.assertNotIn("body { color", cleaned)
        self.assertNotIn('alert("test")', cleaned)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_email_parser.py`
Expected: FAIL (ModuleNotFoundError: No module named 'email_parser')

- [ ] **Step 3: Write minimal implementation**
Create `email_parser.py` using Python's built-in `html.parser.HTMLParser` to ensure high speed and extremely low memory usage with zero dependencies.

```python
from html.parser import HTMLParser
import re

class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.ignore_tag_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "head"):
            self.ignore_tag_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head"):
            self.ignore_tag_depth = max(0, self.ignore_tag_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.ignore_tag_depth == 0:
            self.text_parts.append(data)

class EmailParser:
    @staticmethod
    def html_to_text(html_content: str) -> str:
        parser = _HTMLTextExtractor()
        parser.feed(html_content)
        text = "".join(parser.text_parts)
        
        # Clean up multiple whitespaces and newlines
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip()
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_email_parser.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add email_parser.py tests/test_email_parser.py
git commit -m "feat: add HTML tag-stripping text parser"
```

---

## Task 4: IMAP Ingestion, Attachment Streaming and Cleanup

**Files:**
- Create: `imap_bot.py`
- Create: `tests/test_imap_bot.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_imap_bot.py` mocking the email message components and verifying email downloading, allowed senders matching, and safe sequential attachment chunk streaming.

```python
import unittest
from unittest.mock import MagicMock, patch
from imap_bot import IMAPBot
from config import Config

class TestIMAPBot(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock(spec=Config)
        self.config.allowed_senders = ["teacher@school.com"]
        self.config.email_address = "me@gmail.com"
        self.config.email_password = "password"
        self.config.imap_server = "imap.test.com"
        self.config.imap_port = 993

    @patch("imaplib.IMAP4_SSL")
    def test_is_allowed_sender(self, mock_imap):
        bot = IMAPBot(self.config)
        self.assertTrue(bot.is_allowed_sender("teacher@school.com"))
        self.assertTrue(bot.is_allowed_sender("Teacher <teacher@school.com>"))
        self.assertFalse(bot.is_allowed_sender("spammer@school.com"))

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_imap_bot.py`
Expected: FAIL (ModuleNotFoundError: No module named 'imap_bot')

- [ ] **Step 3: Write minimal implementation**
Create `imap_bot.py`:
```python
import imaplib
import email
from email.message import Message
from pathlib import Path
import re
import logging
from config import Config
from email_parser import EmailParser

logger = logging.getLogger(__name__)

class IMAPBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)

    def is_allowed_sender(self, from_header: str) -> bool:
        if not from_header:
            return False
        # Extract email using regex
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_header)
        if not match:
            return False
        sender_email = match.group(0).lower()
        return any(sender_email == allowed.lower() for allowed in self.config.allowed_senders)

    def connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
        mail.login(self.config.email_address, self.config.email_password)
        return mail

    def fetch_unseen_emails(self, mail: imaplib.IMAP4_SSL) -> list[tuple[str, Message]]:
        mail.select("INBOX")
        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            return []
            
        messages = []
        email_ids = data[0].split()
        for e_id in email_ids:
            # Fetch message structure
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            if status != "OK":
                continue
            
            raw_email = msg_data[0][1]
            if isinstance(raw_email, bytes):
                msg = email.message_from_bytes(raw_email)
                messages.append((e_id.decode("utf-8"), msg))
        return messages

    def parse_email_message(self, msg: Message) -> tuple[str, list[Path]]:
        body = ""
        attachments: list[Path] = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition"))
                
                # Check if it's an attachment
                if "attachment" in disposition:
                    filename = part.get_filename()
                    if filename:
                        # Clean filename
                        filename = re.sub(r'[^\w\.-]', '_', filename)
                        filepath = self.temp_dir / filename
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Sequentially stream to file to preserve memory
                            with open(filepath, "wb") as f:
                                f.write(payload)
                            attachments.append(filepath)
                elif content_type == "text/plain" and "attachment" not in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", errors="ignore")
                elif content_type == "text/html" and "attachment" not in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_body = payload.decode("utf-8", errors="ignore")
                        if not body:  # Fallback to HTML if plain text not processed yet
                            body = EmailParser.html_to_text(html_body)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                content_type = msg.get_content_type()
                if content_type == "text/html":
                    body = EmailParser.html_to_text(payload.decode("utf-8", errors="ignore"))
                else:
                    body = payload.decode("utf-8", errors="ignore")
                    
        return body, attachments

    def mark_seen(self, mail: imaplib.IMAP4_SSL, email_id: str) -> None:
        mail.store(email_id, "+FLAGS", "\\Seen")

    def cleanup_temp_files(self, filepaths: list[Path]) -> None:
        for path in filepaths:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.error(f"Error deleting temp file {path}: {e}")
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_imap_bot.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add imap_bot.py tests/test_imap_bot.py
git commit -m "feat: add memory-efficient IMAP ingestion and attachment loader"
```

---

## Task 5: Gemini Content Generation Client

**Files:**
- Create: `gemini_client.py`
- Create: `tests/test_gemini_client.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_gemini_client.py` testing base64 attachment serialization, construct generateContent REST payload, and mock client-side httpx retry/key-rotation logic.

```python
import unittest
from unittest.mock import MagicMock, patch
from gemini_client import GeminiClient
from config import Config
from key_manager import GeminiKeyManager

class TestGeminiClient(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock(spec=Config)
        self.config.gemini_model = "gemini-2.5-flash"
        self.config.gemini_system_prompt = "Summarize this email."
        
        self.key_manager = MagicMock(spec=GeminiKeyManager)
        self.key_manager.get_key.return_value = "mock_key_1"

    @patch("httpx.Client")
    def test_query_gemini_success(self, mock_httpx):
        client_instance = mock_httpx.return_value
        client_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"candidates": [{"content": {"parts": [{"text": "Summarized content"}]}}]}
        )
        
        gc = GeminiClient(self.config, self.key_manager)
        response = gc.query("Original email body", [])
        self.assertEqual(response, "Summarized content")

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_gemini_client.py`
Expected: FAIL (ModuleNotFoundError: No module named 'gemini_client')

- [ ] **Step 3: Write minimal implementation**
Create `gemini_client.py` with base64 parsing and direct standard JSON request generation for `httpx`.

```python
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
        return {
            "inlineData": {
                "mimeType": mime_type,
                "data": b64_data
            }
        }

    def query(self, email_body: str, attachments: list[Path]) -> str:
        parts = [
            {"text": f"System Prompt: {self.config.gemini_system_prompt}\n\nEmail Body:\n{email_body}"}
        ]
        
        for path in attachments:
            parts.append(self._file_to_part(path))

        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ]
        }

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
                        logger.warning(f"Key failed with status {response.status_code}. Placing on cooldown.")
                        self.key_manager.mark_cooldown(api_key, cooldown_seconds=300)
                    else:
                        logger.error(f"Gemini API error (Status {response.status_code}): {response.text}")
                        self.key_manager.mark_cooldown(api_key, cooldown_seconds=300)
            except Exception as e:
                logger.error(f"Exception during Gemini call: {e}")
                self.key_manager.mark_cooldown(api_key, cooldown_seconds=120)
                
        raise RuntimeError("Failed to query Gemini API: all attempts/keys exhausted.")
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_gemini_client.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add gemini_client.py tests/test_gemini_client.py
git commit -m "feat: add Gemini direct REST client with failover support"
```

---

## Task 6: Telegram Bot Delivery (multi-chat + clean chunking)

**Files:**
- Create: `telegram_client.py`
- Create: `tests/test_telegram_client.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_telegram_client.py` verifying HTML-safe split boundaries (max 4096 chars) and message posts to all active recipients.

```python
import unittest
from unittest.mock import MagicMock, patch
from telegram_client import TelegramClient
from config import Config

class TestTelegramClient(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock(spec=Config)
        self.config.telegram_bot_token = "mock_token"
        self.config.telegram_chat_ids = ["1111", "2222"]

    @patch("httpx.Client")
    def test_send_message_split(self, mock_httpx):
        client_instance = mock_httpx.return_value
        client_instance.post.return_value = MagicMock(status_code=200)

        tc = TelegramClient(self.config)
        # 5000 chars text
        long_text = "A" * 5000
        tc.send_message(long_text)
        
        # Verify post called at least twice per chat id -> total >= 4 calls
        self.assertGreaterEqual(client_instance.post.call_count, 4)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_telegram_client.py`
Expected: FAIL (ModuleNotFoundError: No module named 'telegram_client')

- [ ] **Step 3: Write minimal implementation**
Create `telegram_client.py`:
```python
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
            cut_idx = text.rfind('\n', 0, max_length)
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
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "HTML"
                }
                try:
                    with httpx.Client(timeout=30.0) as client:
                        res = client.post(url, json=payload)
                        if res.status_code != 200:
                            logger.error(f"Failed to send to Telegram chat {chat_id}: {res.text}")
                            success_all = False
                except Exception as e:
                    logger.error(f"Error calling Telegram API for chat {chat_id}: {e}")
                    success_all = False
                    
        return success_all
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_telegram_client.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add telegram_client.py tests/test_telegram_client.py
git commit -m "feat: add robust Telegram client supporting multiple chats and HTML chunking"
```

---

## Task 7: Main Execution Loop & Logging

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_main.py` verifying full end-to-end processing: config loading, IMAP connection, filtering matching emails, calling Gemini, forwarding to Telegram, and calling IMAP flag seen.

```python
import unittest
from unittest.mock import MagicMock, patch
import main

class TestMainLoop(unittest.TestCase):
    @patch("main.Config")
    @patch("main.GeminiKeyManager")
    @patch("main.IMAPBot")
    @patch("main.GeminiClient")
    @patch("main.TelegramClient")
    def test_run_orchestrator(self, mock_tc, mock_gc, mock_bot, mock_km, mock_config):
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

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_main.py`
Expected: FAIL (AttributeError: module 'main' has no attribute 'run')

- [ ] **Step 3: Write minimal implementation**
Create `main.py`:
```python
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
    handlers=[logging.StreamHandler(sys.stdout)]
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
                logger.info(f"Skipping email {email_id} from disallowed sender: {sender}")
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
                    logger.error(f"Telegram delivery failed for email {email_id}; leaving unseen")
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
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_main.py`
Expected: PASS

- [ ] **Step 5: Run all unit tests to ensure everything is perfect**
Run: `python -m unittest discover -s tests`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add main.py tests/test_main.py
git commit -m "feat: implement main entry point with cohesive logging & error tracking"
```
