---
name: whatsapp-monitor
description: "On-demand WhatsApp Web scan for unread business messages"
triggers:
  - check whatsapp
  - check my whatsapp
  - any whatsapp messages
  - scan whatsapp
  - whatsapp urgent
config:
  keywords:
    - urgent
    - asap
    - client
    - payment
    - meeting
    - invoice
    - deadline
    - action required
  session_dir: ~/Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials/whatsapp_session
  vault_path: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault
  headless: false
  tier: silver
---

# Skill: whatsapp-monitor

Performs a single on-demand scan of WhatsApp Web for unread messages matching
business keywords. For each match, it creates a structured task card in the
vault and updates the Dashboard. Read-only — this skill never sends or deletes
messages.

---

## Purpose

- Surfaces urgent WhatsApp messages (from clients, about payments, meeting requests) as actionable vault cards without waiting for the automatic 60-second polling cycle
- Gives the operator immediate visibility when they know an important message has arrived
- Bridges WhatsApp Web and the Obsidian vault pipeline alongside email and file monitoring
- Deduplicates: messages already logged to any vault folder are silently skipped
- Uses browser session persistence — QR code is only required once per machine

---

## Process

1. Add the project root to the Python path so the `watchers` package is importable
2. Instantiate `WhatsAppWatcher` with `vault_path`, `session_dir`, and `headless` from config
3. Launch a Playwright Chromium browser using the saved persistent session in `.credentials/whatsapp_session/`
4. If no session exists yet, display a QR code in a visible browser window — wait up to 2 minutes for the operator to scan it, then save the session for future runs
5. Navigate to `web.whatsapp.com` and wait for the chat list sidebar to become visible
6. Call `check_for_updates()` exactly once — scrapes unread chat rows from the sidebar, filters by keywords, and deduplicates against existing vault cards
7. For each new matching message, call `create_action_file(item)` — writes a `WHATSAPP_*.md` card to `Vault/Needs_Action/` if priority is high, or `Vault/Inbox/` otherwise
8. Close the browser cleanly after the single check completes
9. Invoke the `update-dashboard` skill to refresh activity log and message count

---

## How to Run

**Standalone (single-shot check):**
```
cd ~/Desktop/Hackathon/Hackathon0/ai-employee-project
python watchers/whatsapp_watcher.py
```

Optional arguments:
```
python watchers/whatsapp_watcher.py --vault <vault_path>
python watchers/whatsapp_watcher.py --headless
python watchers/whatsapp_watcher.py --session-dir <path>
python watchers/whatsapp_watcher.py --interval 60
```

**From Python (import):**
```
Project root:  ~/Desktop/Hackathon/Hackathon0/ai-employee-project
Module:        watchers.whatsapp_watcher
Class:         WhatsAppWatcher(vault_path, session_dir, headless, keywords)
Methods:       check_for_updates()      -> list of message dicts
               create_action_file(item) -> Path of created vault card
               stop()                  -> closes browser cleanly
```

Call `check_for_updates()` exactly once per skill invocation — no loop, no sleep.
Always call `stop()` after to release the browser process.

---

## WhatsApp Web Setup (first time only)

1. Run the watcher once in visible mode (headless=false — the default)
2. A Chromium window opens and shows the WhatsApp Web QR code
3. Open WhatsApp on your phone → Linked Devices → Link a Device → scan the QR
4. Session is saved to `.credentials/whatsapp_session/` automatically
5. All future runs reuse this session — no QR scan needed

**Session location:**
```
.credentials/whatsapp_session/   ← auto-created on first run, never commit this
```

This directory is listed in `.gitignore`.

---

## Security Notes

| Property | Detail |
|----------|--------|
| Access | Read-only — cannot send, delete, or modify messages |
| Data stored | Contact name and first 300 chars of message preview only |
| Session | Browser cookies saved locally, never committed to git |
| Keywords filter | Only chats matching business keywords produce vault cards |
| Network calls | Only to `web.whatsapp.com` via local Chromium browser |

---

## Output: Vault Card Format

Each matching message produces `Vault/Inbox/WHATSAPP_YYYYMMDD_HHMMSS_<contact>.md`
or `Vault/Needs_Action/WHATSAPP_*.md` for high-priority messages:

```yaml
---
type: whatsapp
from: "John Smith"
message_preview: "Urgent: can we reschedule the client meeting to 3pm?"
received: "2026-04-07 14:30:22"
priority: high
status: pending
uid: "John_Smith__Urgent__can_we_reschedule_the_cl"
---
```

**Priority rules:**
- `high` → message contains `urgent`, `asap`, `deadline`, or `action required` — card goes directly to `Needs_Action/`
- `normal` → message contains `client`, `payment`, `meeting`, or `invoice` — card goes to `Inbox/`

---

## Expected Output

**Messages found:**
```
[whatsapp-monitor] Session dir: .credentials/whatsapp_session/
[whatsapp-monitor] Loading WhatsApp Web...
[whatsapp-monitor] Found 3 candidate chat row(s).
[whatsapp-monitor] New message from John Smith: Urgent: can we reschedule the client meeting...
[whatsapp-monitor] New message from Accounts: Invoice payment overdue — please confirm receipt
  [new] Card created: WHATSAPP_20260407_143022_John_Smith.md → Needs_Action/
  [new] Card created: WHATSAPP_20260407_143022_Accounts.md → Inbox/
[whatsapp-monitor] 2 new vault card(s) created.
[whatsapp-monitor] Calling update-dashboard to refresh status...
```

**Nothing new:**
```
[whatsapp-monitor] Session dir: .credentials/whatsapp_session/
[whatsapp-monitor] Loading WhatsApp Web...
[whatsapp-monitor] Found 0 candidate chat row(s).
[whatsapp-monitor] No new priority messages to log.
```

---

## Dependencies

- `watchers/whatsapp_watcher.py` — must exist; provides `WhatsAppWatcher`
- `watchers/base_watcher.py` — base class, required by `whatsapp_watcher.py`
- `helpers/dashboard_updater.py` — used by `post_cycle()` to update Dashboard
- `playwright` Python package — install with `uv add playwright && uv run playwright install chromium`
- `.credentials/whatsapp_session/` — created automatically on first QR scan
- `Vault/Inbox/` and `Vault/Needs_Action/` — created automatically if missing

---

## Notes

- WhatsApp Web selectors may change when Meta updates their web client — if scraping stops working, inspect the chat sidebar in browser DevTools and update `UNREAD_CHAT_SELECTOR` in `whatsapp_watcher.py`
- The `uid` field in the frontmatter is a hash of contact name + message preview — do not rename vault cards manually or deduplication may break
- If the session expires (WhatsApp logs out linked devices after ~30 days of inactivity), delete `.credentials/whatsapp_session/` and run in visible mode to re-scan the QR
- Running headless before a session is saved will fail — always do the first run in visible mode
- This skill is Silver Tier — it runs on-demand only; for continuous monitoring, `WhatsAppWatcher` is added to the orchestrator in `main.py`
- Keywords can be extended by editing `config.keywords` in this frontmatter and passing the updated list to `WhatsAppWatcher(keywords=[...])`
