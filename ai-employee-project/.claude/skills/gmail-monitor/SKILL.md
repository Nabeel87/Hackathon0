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
  credentials_dir: ~/Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials
  vault_inbox: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Inbox
---

# Skill: gmail-monitor

Checks Gmail for unread priority emails matching keywords, then creates
structured task cards in the vault Inbox. Read-only OAuth2 — never sends,
deletes, or modifies anything.

---

## What This Skill Does

1. Authenticates with Gmail using saved `token.json` (no browser unless first run)
2. Queries inbox: `is:unread label:inbox ("urgent" OR "asap" OR "invoice" OR "payment")`
3. Skips any message already logged (checked by message ID in vault Inbox filenames)
4. For each new match, creates an `EMAIL_*.md` card in `Vault/Inbox/`
5. Calls the `update-dashboard` skill after all cards are created

---

## How to Run

Import and call `GmailWatcher` from `watchers/gmail_watcher.py` for a single-shot check:

```
Project root: ~/Desktop/Hackathon/Hackathon0/ai-employee-project
Module:       watchers.gmail_watcher
Class:        GmailWatcher(vault_path)
Methods:      _get_service() → authenticate
              check_for_updates() → list of email dicts
              create_action_file(item) → writes vault card
```

1. Instantiate `GmailWatcher` with `vault_path`
2. Call `watcher._get_service()` to authenticate (reuses `token.json`, auto-refreshes)
3. Call `watcher.check_for_updates()` once — returns list of new email dicts
4. Call `watcher.create_action_file(item)` for each result
5. After all cards created, invoke the `update-dashboard` skill

---

## Gmail API Setup (first time only)

### Prerequisites

1. Go to Google Cloud Console → create project `ai-employee`
2. Enable the **Gmail API** under APIs & Services → Library
3. Create **OAuth client ID** → Desktop app → download JSON
4. Save the file to `.credentials/credentials.json`

### Credentials location

```
ai-employee-project/.credentials/credentials.json   ← downloaded from Google
ai-employee-project/.credentials/token.json         ← auto-created on first run
```

Both files are in `.gitignore` and will never be committed.

### First-run authorization

On first run, a browser window opens to grant `gmail.readonly` access.
After approval, `token.json` is saved automatically.
All future runs reuse and auto-refresh `token.json` — no browser needed.

---

## Security Notes

| Property | Detail |
|----------|--------|
| Scope | `gmail.readonly` — zero write access |
| Data stored | Sender, subject, 200-char snippet only — no full body |
| Credentials | Local disk only, never committed to git |
| Token refresh | Automatic via `google-auth` library |
| Network calls | Only to `gmail.googleapis.com` |

---

## Output: Vault Card Format

Each matching email produces a card at `Vault/Inbox/EMAIL_YYYYMMDD_HHMMSS_<msgid>_<subject>.md`:

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

**Priority rules:**
- `high` — subject or snippet contains `urgent` or `asap`
- `normal` — contains `invoice` or `payment` (finance checklist attached)

---

## Expected Output

**Emails found:**
```
[gmail-monitor] Authenticating with Gmail API...
[gmail-monitor] Query: is:unread label:inbox ("urgent" OR "asap" OR "invoice" OR "payment")
[gmail-monitor] 2 matching unread email(s) found.
  [new]  Card created: EMAIL_20260404_143055_1a2b3c4d_Invoice_for_April.md
  [new]  Card created: EMAIL_20260404_091200_5e6f7a8b_Urgent_contract_review.md
[gmail-monitor] 2 new inbox card(s) created.
[gmail-monitor] Calling update-dashboard to refresh status...
```

**Nothing new:**
```
[gmail-monitor] Authenticating with Gmail API...
[gmail-monitor] Query: is:unread label:inbox ("urgent" OR "asap" OR "invoice" OR "payment")
[gmail-monitor] 0 matching unread email(s) found.
[gmail-monitor] No new priority emails to log.
```

---

## After This Skill Runs

Always invoke the `update-dashboard` skill so Dashboard.md reflects the latest
email count, last-checked time, and any high-priority alerts.
