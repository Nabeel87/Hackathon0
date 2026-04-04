---
name: file-monitor
description: "Monitors ~/Downloads for new files (privacy-safe default)"
triggers:
  - check for new files
  - monitor downloads
  - scan downloads
config:
  monitored_folders:
    - ~/Downloads
  ignored_patterns:
    - .ssh
    - .config
    - .env
    - credentials
    - passwords
---

# Skill: file-monitor

Scans `~/Downloads` for new files, filters out anything sensitive or temporary,
and creates structured task cards in the vault Inbox for each safe file found.

---

## What This Skill Does

1. Scans `~/Downloads` for all files (non-recursive)
2. Skips hidden files (`.dotfiles`), temp files (`~file`, `.tmp`, `.part`), and anything matching the security blacklist
3. For each new safe file not already logged, creates a `FILE_*.md` card in `Vault/Inbox/`
4. Calls the `update-dashboard` skill after all cards are created

---

## How to Run

Import and call `FileWatcher` from `watchers/file_watcher.py` for a single-shot scan:

```
Project root: ~/Desktop/Hackathon/Hackathon0/ai-employee-project
Module:       watchers.file_watcher
Class:        FileWatcher(vault_path, watch_dir)
Method:       create_action_file(item)
```

1. Instantiate `FileWatcher` with `vault_path` and `watch_dir`
2. Iterate files in `watch_dir`, filter with `_is_safe(path)`
3. Build an `item` dict: `path`, `name`, `suffix`, `size_bytes`, `detected_at`
4. Call `watcher.create_action_file(item)` for each file
5. After all cards created, invoke the `update-dashboard` skill

---

## Security Blacklist

These patterns are **always blocked** — no vault card is ever created for them:

| Pattern | Reason |
|---------|--------|
| `.ssh` | SSH keys — catastrophic if exposed |
| `.config` | App credentials and personal settings |
| `.env` | Almost always contains secrets |
| `credentials` | Any file with this in the name |
| `passwords` | Any file with this in the name |
| `secret`, `private_key`, `id_rsa` | Cryptographic material |
| `.pem`, `.p12`, `.pfx` | Certificate and key files |

The blacklist applies to the **full file path**, so `~/Downloads/my-credentials-backup.csv` is also blocked.

---

## Output: Vault Card Format

Each detected file produces a card at `Vault/Inbox/FILE_YYYYMMDD_HHMMSS_<name>.md`:

```yaml
---
type: file
name: "report.pdf"
path: "/home/user/Downloads/report.pdf"
size_kb: 1230.4
file_type: ".pdf"
detected: "2026-04-04 14:30:22 UTC"
priority: high
status: pending
---
```

**Priority rules:**
- `high` — `.pdf`, `.docx`, `.xlsx`, `.zip`, `.exe`, or filename contains `urgent`/`invoice`/`contract`/`payment`
- `normal` — everything else

---

## Expected Output

**Files found:**
```
[file-monitor] Starting single-shot scan...
[file-monitor] 2 eligible file(s) found in ~/Downloads
  [new]  Card created: FILE_20260404_143022_report_pdf.md
  [new]  Card created: FILE_20260404_143022_invoice_April.md
[file-monitor] 2 new inbox card(s) created.
[file-monitor] Calling update-dashboard to refresh status...
```

**Nothing new:**
```
[file-monitor] Starting single-shot scan...
[file-monitor] 0 eligible file(s) found in ~/Downloads
[file-monitor] No new files detected.
```

---

## After This Skill Runs

Always invoke the `update-dashboard` skill so Dashboard.md reflects the latest
file count and recent activity.
