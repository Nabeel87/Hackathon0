---
name: gmail-monitor
description: "Monitors Gmail inbox for important emails"
triggers:
  - check gmail
  - check my email
  - scan inbox
  - monitor email
config:
  scopes:
    - https://www.googleapis.com/auth/gmail.readonly
  keywords:
    - urgent
    - asap
    - invoice
    - payment
  labels:
    - IMPORTANT
    - INBOX
  credentials_dir: ~/Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials
  vault_inbox: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Inbox
---

# Skill: gmail-monitor

Scans your Gmail inbox for unread emails matching priority keywords, then
creates structured task cards in the vault Inbox for each match. Uses
read-only OAuth2 — it never sends, deletes, or modifies anything.

---

## Gmail API Setup

### Step 1 — Create a Google Cloud project

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it `ai-employee` and click **Create**

### Step 2 — Enable the Gmail API

1. In the left sidebar go to **APIs & Services → Library**
2. Search for **Gmail API** and click it
3. Click **Enable**

### Step 3 — Create OAuth2 credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. If prompted, configure the **OAuth consent screen** first:
   - User type: **External**
   - App name: `AI Employee`
   - Add your Gmail address as a test user
4. Back in Create Credentials, choose:
   - Application type: **Desktop app**
   - Name: `ai-employee-desktop`
5. Click **Create** then **Download JSON**

### Step 4 — Save credentials.json

Place the downloaded file at:

```
ai-employee-project/.credentials/credentials.json
```

Create the folder if it doesn't exist:
```bash
mkdir -p ~/Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials
mv ~/Downloads/client_secret_*.json \
   ~/Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials/credentials.json
```

The `.credentials/` folder is listed in `.gitignore` — it will never be committed.

### Step 5 — First-run authorization

The first time this skill runs it will:
1. Open a browser window asking you to log in to Google
2. Ask you to grant read-only Gmail access to the app
3. Save a `token.json` file next to `credentials.json`

All subsequent runs reuse `token.json` and refresh it automatically. You
will not be prompted again unless the token is deleted or revoked.

---

## Security Notes

| Property | Detail |
|----------|--------|
| Scope | `gmail.readonly` — zero write access to your account |
| Data stored | Sender, subject, 200-char snippet only — no full body |
| Credentials location | Local disk only, inside `.credentials/` |
| Token refresh | Automatic via `google-auth` library |
| Network calls | Only to `gmail.googleapis.com` — no third-party services |
| Committed to git | Never — `.credentials/` is in `.gitignore` |

---

## Implementation

```python
import os
import re
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parseaddr

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Config ────────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_DIR = Path.home() / "Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

VAULT_INBOX = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Inbox"

KEYWORDS = ["urgent", "asap", "invoice", "payment"]

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_gmail_service():
    """Authenticate and return an authorised Gmail API service object."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[gmail-monitor] Refreshing access token...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}\n"
                    "Follow the Gmail API Setup section in this SKILL.md to create it."
                )
            print("[gmail-monitor] Opening browser for first-time authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        print(f"[gmail-monitor] Token saved to {TOKEN_FILE}")

    return build("gmail", "v1", credentials=creds)


# ── Helpers ───────────────────────────────────────────────────────────────────

def keyword_priority(subject: str, snippet: str) -> str:
    """Return 'high' if any keyword appears in subject, else 'normal'."""
    combined = (subject + " " + snippet).lower()
    high_keywords = ["urgent", "asap"]
    if any(kw in combined for kw in high_keywords):
        return "high"
    return "normal"


def already_logged(message_id: str) -> bool:
    """Check if a vault card for this message_id already exists."""
    if not VAULT_INBOX.exists():
        return False
    return any(message_id in f.name for f in VAULT_INBOX.iterdir())


def parse_received_time(internal_date_ms: str) -> tuple[str, str]:
    """Convert Gmail internalDate (ms epoch) to ISO string and slug."""
    ts = int(internal_date_ms) / 1000
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    slug = dt.strftime("%Y%m%d_%H%M%S")
    return iso, slug


def suggested_actions(subject: str, snippet: str) -> str:
    """Return a checklist tailored to detected email type."""
    combined = (subject + " " + snippet).lower()
    if "invoice" in combined or "payment" in combined:
        return (
            "- [ ] Verify invoice amount and sender legitimacy\n"
            "- [ ] Check if payment is due or already processed\n"
            "- [ ] Forward to accounts or log in expense tracker\n"
            "- [ ] Reply to confirm receipt if required"
        )
    if "urgent" in combined or "asap" in combined:
        return (
            "- [ ] Read full email immediately\n"
            "- [ ] Determine who needs to be notified\n"
            "- [ ] Draft response or escalate within 1 hour\n"
            "- [ ] Log outcome in Notes section below"
        )
    return (
        "- [ ] Read full email\n"
        "- [ ] Determine if action or reply is needed\n"
        "- [ ] Archive or file when resolved"
    )


def safe_slug(text: str, max_len: int = 40) -> str:
    """Convert arbitrary text to a filename-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text).strip()
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len]


def create_inbox_card(msg_meta: dict) -> Path:
    """Write a markdown task card to the vault Inbox and return its path."""
    message_id = msg_meta["id"]
    subject = msg_meta.get("subject", "(no subject)")
    sender = msg_meta.get("sender", "unknown")
    snippet = msg_meta.get("snippet", "")
    received_iso, received_slug = parse_received_time(msg_meta["internalDate"])
    priority = keyword_priority(subject, snippet)
    actions = suggested_actions(subject, snippet)

    subject_slug = safe_slug(subject)
    card_name = f"EMAIL_{received_slug}_{message_id[:8]}_{subject_slug}.md"
    card_path = VAULT_INBOX / card_name

    VAULT_INBOX.mkdir(parents=True, exist_ok=True)

    # Escape any quotes in YAML string fields
    def yml(value: str) -> str:
        return value.replace('"', '\\"')

    card_content = f"""---
type: email
from: "{yml(sender)}"
subject: "{yml(subject)}"
received: "{received_iso}"
priority: {priority}
status: pending
message_id: "{message_id}"
---

# Email: {subject}

**From:** {sender}
**Received:** {received_iso}
**Priority:** {priority}

---

## Snippet

> {snippet}

---

## Suggested Actions

{actions}

---

## Notes

_Add context here as you process this email._
"""

    card_path.write_text(card_content, encoding="utf-8")
    return card_path


# ── Gmail query & fetch ───────────────────────────────────────────────────────

def build_query() -> str:
    """Build Gmail search query: unread, in inbox or important, keyword match."""
    keyword_clause = " OR ".join(f'"{kw}"' for kw in KEYWORDS)
    return f"is:unread label:inbox ({keyword_clause})"


def fetch_messages(service, query: str, max_results: int = 20) -> list[dict]:
    """Return list of message metadata dicts matching the query."""
    try:
        result = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
    except HttpError as e:
        print(f"[gmail-monitor] API error during list: {e}")
        return []

    messages = result.get("messages", [])
    if not messages:
        return []

    enriched = []
    for msg in messages:
        try:
            full = service.users().messages().get(
                userId="me", id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
        except HttpError as e:
            print(f"[gmail-monitor] Could not fetch message {msg['id']}: {e}")
            continue

        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        enriched.append({
            "id": full["id"],
            "subject": headers.get("Subject", "(no subject)"),
            "sender": headers.get("From", "unknown"),
            "snippet": full.get("snippet", "")[:200],
            "internalDate": full["internalDate"],
        })

    return enriched


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("[gmail-monitor] Authenticating with Gmail API...")
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        print(f"[gmail-monitor] Setup required:\n{e}")
        return []

    query = build_query()
    print(f"[gmail-monitor] Query: {query}")

    messages = fetch_messages(service, query)
    print(f"[gmail-monitor] {len(messages)} matching unread email(s) found.")

    new_cards = []
    for msg in messages:
        if already_logged(msg["id"]):
            print(f"  [skip] Already logged: {msg['subject'][:60]}")
            continue

        card_path = create_inbox_card(msg)
        new_cards.append(card_path)
        print(f"  [new]  Card created: {card_path.name}")

    if new_cards:
        print(f"\n[gmail-monitor] {len(new_cards)} new inbox card(s) created.")
        print("[gmail-monitor] Calling update-dashboard to refresh status...")
    else:
        print("[gmail-monitor] No new priority emails to log.")

    return new_cards


run()
```

---

## Dashboard Integration

After this skill runs, always invoke the `update-dashboard` skill so
Dashboard.md reflects the latest email count, last-checked time, and any
high-priority alerts.

---

## Usage Examples

**Invoke manually:**
> "Check Gmail"
> "Check my email"
> "Scan inbox"
> "Monitor email"

**Expected output (matches found):**
```
[gmail-monitor] Authenticating with Gmail API...
[gmail-monitor] Query: is:unread label:inbox ("urgent" OR "asap" OR "invoice" OR "payment")
[gmail-monitor] 2 matching unread email(s) found.
  [new]  Card created: EMAIL_20260404_143055_1a2b3c4d_Invoice_for_April_services.md
  [new]  Card created: EMAIL_20260404_091200_5e6f7a8b_Urgent_contract_review_needed.md
[gmail-monitor] 2 new inbox card(s) created.
[gmail-monitor] Calling update-dashboard to refresh status...
```

**Expected output (nothing new):**
```
[gmail-monitor] Authenticating with Gmail API...
[gmail-monitor] Query: is:unread label:inbox ("urgent" OR "asap" OR "invoice" OR "payment")
[gmail-monitor] 0 matching unread email(s) found.
[gmail-monitor] No new priority emails to log.
```

**Vault card produced** (`Inbox/EMAIL_20260404_143055_1a2b3c4d_Invoice_for_April_services.md`):
```yaml
---
type: email
from: "billing@vendor.com"
subject: "Invoice for April services"
received: "2026-04-04 14:30:55 UTC"
priority: normal
status: pending
message_id: "1a2b3c4d5e6f7a8b"
---
```

---

## Dependencies

- `google-api-python-client` — Gmail REST API client
- `google-auth-httplib2` — HTTP transport for Google auth
- `google-auth-oauthlib` — OAuth2 browser flow and token management
