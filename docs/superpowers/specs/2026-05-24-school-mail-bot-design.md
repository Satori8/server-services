# School Mail Bot Design Document

A lightweight, memory-efficient, and reliable backend service designed to automate the processing of specific incoming school emails, analyze them using Google Gemini API, and forward formatted summaries/alerts to a Telegram channel/chat.

This service is optimized to run on an Oracle Cloud Free Tier instance (`VM.Standard.E2.1.Micro`) with severe resource constraints (1/8 AMD OCPU, 1 GB RAM).

## 1. System Architecture & Flow

The service operates as a single-execution script triggered periodically (e.g., every 1 minute) via a standard system cron job. This model guarantees that the process does not suffer from long-term memory leaks, since RAM is fully reclaimed by the operating system after each run.

```
                  +-------------------------+
                  |       System Cron       |
                  |     (Every 1 Minute)    |
                  +-------------------------+
                               |
                               | (Triggers execution)
                               v
                  +-------------------------+
                  |    school-mail-bot      |
                  |     (main.py)           |
                  +-------------------------+
                   /           |           \
                  /            |            \
                 v             v             v
         +------------+  +------------+  +--------------+
         | Gmail IMAP |  | Gemini API |  | Telegram API |
         | (Ingestion)|  | (Analysis) |  | (Delivery)   |
         +------------+  +------------+  +--------------+
```

### Execution Steps:
1. **Poll & Filter**: Connect to the Gmail IMAP server, fetch all `UNSEEN` emails, and filter to keep only those from `ALLOWED_SENDER`.
2. **Process Mail & Streaming**: 
   - Parse each matching email for plain text content (or HTML stripped of tags).
   - Stream attachments directly to disk into a temporary `temp/` folder.
3. **Analyze Content via Gemini**:
   - Send the extracted text body and the attachments as inline base64 content (or via File API if larger than 20MB) to Gemini API using a rotated API key.
   - Obtain structured Markdown or HTML analysis from Gemini.
4. **Deliver via Telegram**:
   - Post the analyzed text to the target Telegram chat/channel using standard HTML/Markdown styling.
5. **Mark as Seen & Cleanup**:
   - If processing is successful, mark the email as `\Seen` on the IMAP server.
   - Clean up and delete all files in the `temp/` directory immediately.

---

## 2. Directory Structure

The workspace layout is clean and minimal, excluding any heavy packages (like Pydantic or Pytest):

```
school-mail-bot/
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-05-24-school-mail-bot-design.md
├── temp/                # Temp directory for downloading attachments
├── .env                 # Secret configurations and environment variables
├── keys.txt             # List of Gemini API Keys (one per line)
└── main.py              # Single lightweight python script
```

---

## 3. Detailed Component Designs

### 3.1. Configuration (.env)
We load configurations from standard environment variables:

- `IMAP_SERVER`: Hostname of the IMAP server (default: `imap.gmail.com`).
- `IMAP_PORT`: Port of the IMAP server (default: `993`).
- `EMAIL_ADDRESS`: Email address for authentication.
- `EMAIL_PASSWORD`: App password (not the main password) for Gmail.
- `ALLOWED_SENDER`: Email address of the sender to filter.
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for API.
- `TELEGRAM_CHAT_ID`: Telegram channel or personal chat ID.
- `GEMINI_MODEL`: Gemini model to use (default: `gemini-2.5-flash`).
- `GEMINI_SYSTEM_PROMPT`: Instructions for Gemini to format and extract info.

### 3.2. Gemini API Key Rotation & Cooldown
- **File Source**: Read all keys from `keys.txt` on startup. Blank lines or lines starting with `#` are ignored.
- **In-Memory State**: Maintain an in-memory tracker `key_cooldowns: dict[str, float]` storing the timestamp when each key is allowed to be used again.
- **Failover Logic**: 
  - Loop through keys. Check if key cooldown timestamp is in the past.
  - If a key fails with an API error (e.g., HTTP 429, 500, 503, or connection failure), we mark its cooldown for 5 minutes (`time.time() + 300`) and raise a temporary exception.
  - Catch exception, choose the next available key, and retry the request up to `N` times (equal to total number of available keys).
  - If all keys are locked or on cooldown, raise an error, log the incident, and gracefully exit.

### 3.3. Email Parsing & HTML to Text Cleanups
Using Python's built-in `email` and `html.parser` modules to parse emails and attachments:
- Extracts plain text body directly.
- If only HTML exists, use a custom lightweight subclass of `html.parser.HTMLParser` to extract textual content, removing all scripts, style tags, and CSS, resulting in clean plain text.

### 3.4. Memory-Efficient Attachment Streaming
To prevent OOM on 1 GB RAM:
- Email body and metadata parsing are kept in memory.
- Email attachments are streamed using chunks (e.g., 8192 bytes) when writing to the `temp/` directory.
- For Gemini API, attachments are encoded to base64 inline or streamed. Because base64 takes ~33% more memory than raw binary, files are processed sequentially.
- A `try...finally` block guarantees that `temp/` folder is wiped after every processed email.

### 3.5. Direct HTTP API Interaction (using `httpx`)
Instead of importing the large Google Generative AI SDK or python-telegram-bot SDK, we interact directly with REST endpoints:

#### Gemini generateContent Endpoint:
`POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}`
Payload structure:
```json
{
  "contents": [
    {
      "parts": [
        {"text": "SYSTEM PROMPT..."},
        {"text": "EMAIL BODY..."},
        {
          "inlineData": {
            "mimeType": "application/pdf",
            "data": "BASE64_ENCODED_CONTENT"
          }
        }
      ]
    }
  ]
}
```

#### Telegram sendMessage Endpoint:
`POST https://api.telegram.org/bot{token}/sendMessage`
Payload structure:
```json
{
  "chat_id": "TELEGRAM_CHAT_ID",
  "text": "FORMATTED_GEMINI_SUMMARY",
  "parse_mode": "HTML"
}
```
- If the text exceeds the 4,096 character Telegram limit, it is cleanly split on paragraph breaks (`\n\n` or `\n`) and sent as sequential messages.

---

## 4. Error Handling & Recovery

- **IMAP Connection Dropouts**: Wrap the connection in `try-except`. On failure, log the error and let the next cron run retry.
- **API Rate Limits / Server Errors**: Handled by the Gemini Key Rotation and Cooldown logic.
- **Malformed Emails**: If an email is totally unparseable, log it, mark it as read (or log its ID for debugging) to prevent infinite loops of failing cron runs.
- **Atomic Operations**: Only mark an email as read (`\Seen`) AFTER Telegram delivery confirms with a success HTTP 200 response. This ensures no emails are lost.

---

## 5. Deployment & Run Instructions

1. Put the code in the directory.
2. Create `.env` and `keys.txt` files.
3. Configure crontab on the Oracle Cloud Free Tier server:
   ```cron
   * * * * * cd /path/to/school-mail-bot && /usr/bin/python3 main.py >> bot.log 2>&1
   ```
