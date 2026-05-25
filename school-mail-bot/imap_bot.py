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
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", from_header)
        if not match:
            return False
        sender_email = match.group(0).lower()
        return any(
            sender_email == allowed.lower() for allowed in self.config.allowed_senders
        )

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
                        filename = re.sub(r"[^\w\.-]", "_", filename)
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
                    body = EmailParser.html_to_text(
                        payload.decode("utf-8", errors="ignore")
                    )
                else:
                    body = payload.decode("utf-8", errors="ignore")

        return body, attachments

    def mark_seen(self, mail: imaplib.IMAP4_SSL, email_id: str) -> None:
        mail.store(email_id, "+FLAGS", "\\Seen")

    def mark_unseen(self, mail: imaplib.IMAP4_SSL, email_id: str) -> None:
        mail.store(email_id, "-FLAGS", "\\Seen")

    def cleanup_temp_files(self, filepaths: list[Path]) -> None:
        for path in filepaths:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.error(f"Error deleting temp file {path}: {e}")
