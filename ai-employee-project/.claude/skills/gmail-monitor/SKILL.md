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
import sys
from pathlib import Path

# Ensure project root is on the path so watchers package is importable
PROJECT_ROOT = Path.home() / "Desktop/Hackathon/Hackathon0/ai-employee-project"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchers.gmail_watcher import GmailWatcher

# ── Config ────────────────────────────────────────────────────────────────────

VAULT_PATH = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault"

# ── Single-shot check (no continuous loop) ────────────────────────────────────

def run():
    print("[gmail-monitor] Authenticating with Gmail API...")

    watcher = GmailWatcher(vault_path=VAULT_PATH)

    try:
        # Initialise the Gmail service (handles token refresh / first-run OAuth)
        watcher._service = watcher._get_service()
    except FileNotFoundError as e:
        print(f"[gmail-monitor] Setup required:\n{e}")
        return []

    # Single call — no loop, no sleep
    items = watcher.check_for_updates()
    print(f"[gmail-monitor] {len(items)} matching unread email(s) found.")

    new_cards = []
    for item in items:
        card_path = watcher.create_action_file(item)
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
