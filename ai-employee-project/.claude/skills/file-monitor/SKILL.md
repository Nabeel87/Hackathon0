---
name: file-monitor
description: "Monitors ~/Downloads for new files (privacy-safe default)"
triggers:
  - check for new files
  - monitor downloads
  - scan downloads
  - check downloads folder
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
and creates a structured task card in the vault Inbox for each safe file found.
Runs once per invocation — not a continuous watcher.

---

## Purpose

- Gives the AI employee visibility into files that arrive from outside (downloads, attachments, shared files)
- Converts raw file arrivals into actionable vault cards with suggested next steps
- Protects privacy by only monitoring `~/Downloads` and blocking sensitive file patterns
- Deduplicates: files already logged are silently skipped on repeat runs
- Feeds the vault pipeline — cards created here are later processed by `process-inbox`

---

## Process

1. Add the project root to the Python path so the `watchers` package is importable
2. Instantiate `FileWatcher` with `vault_path` pointing to the AI Employee Vault
3. Iterate all files in `~/Downloads` (non-recursive)
4. For each file, call `_is_safe(path)` — skip hidden files, temp files, and blacklisted patterns
5. For each safe file, build an item dict containing: `path`, `name`, `suffix`, `size_bytes`, `detected_at`
6. Call `watcher.create_action_file(item)` — this writes a `FILE_*.md` card to `Vault/Inbox/`
7. After all cards are written, invoke the `update-dashboard` skill

---

## How to Run

```
Project root:  ~/Desktop/Hackathon/Hackathon0/ai-employee-project
Module:        watchers.file_watcher
Class:         FileWatcher(vault_path, watch_dir)
Helper:        _is_safe(path) → bool
Method:        create_action_file(item) → Path
```

Add the project root to `sys.path` before importing, then run as a single-shot scan (not a loop).

---

## Security Blacklist

These patterns are always blocked — no vault card is ever created for them:

| Pattern | Reason |
|---------|--------|
| `.ssh` | SSH keys — catastrophic if exposed |
| `.config` | App credentials and personal settings |
| `.env` | Almost always contains secrets |
| `credentials` | Any file with this in the name |
| `passwords` | Any file with this in the name |
| `secret`, `private_key`, `id_rsa` | Cryptographic material |
| `.pem`, `.p12`, `.pfx` | Certificate and key files |

The blacklist checks the full file path — `~/Downloads/my-credentials-backup.csv` is also blocked.

---

## Output: Vault Card Format

Each detected file produces `Vault/Inbox/FILE_YYYYMMDD_HHMMSS_<name>.md`:

```yaml
---
type: file
name: "report.pdf"
path: "/home/user/Downloads/report.pdf"
size_kb: 1230.4
file_type: ".pdf"
detected: "2026-04-05 14:30:22 UTC"
priority: high
status: pending
---
```

**Priority rules:**
- `high` — `.pdf`, `.docx`, `.xlsx`, `.zip`, `.exe`, or filename contains `urgent`, `invoice`, `contract`, or `payment`
- `normal` — everything else

---

## Usage Examples

> "Check for new files"
> "Scan my downloads"
> "Monitor downloads"
> "Any new files in downloads?"

**Files found:**
```
[file-monitor] Starting single-shot scan...
[file-monitor] 2 eligible file(s) found in ~/Downloads
  [new]  Card created: FILE_20260405_143022_report_pdf.md
  [new]  Card created: FILE_20260405_143022_invoice_April.md
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

## Dependencies

- `watchers/file_watcher.py` — must exist; provides `FileWatcher` and `_is_safe`
- `watchers/base_watcher.py` — base class, required by `file_watcher.py`
- `watchdog` Python package — used internally by `FileWatcher`
- `Vault/Inbox/` folder — created automatically if missing

---

## Notes

- This skill performs a point-in-time snapshot of `~/Downloads`, not live monitoring
- Files already logged (matched by name in existing vault cards) are silently skipped
- To add more monitored folders, update `config.monitored_folders` in this frontmatter and pass the additional paths to `FileWatcher`
- Executable files (`.exe`, `.dmg`) are not blocked but receive a "do not run without verifying" action checklist
- Always call `update-dashboard` after this skill to keep stats and activity log current
