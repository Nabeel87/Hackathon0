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

Scans configured folders for new files, filters out anything sensitive, and
creates structured task cards in the vault Inbox for each safe file detected.

---

## Privacy & Security

### Why only ~/Downloads by default

`~/Downloads` is the one folder where files arrive from outside — browser
downloads, email attachments saved manually, shared files. It has no personal
documents, no system config, and no secrets. Monitoring it gives maximum signal
with minimal privacy risk.

All other folders (`~/Documents`, `~/Desktop`, `~/Pictures`, `~/.ssh`, etc.)
are **off by default** because they contain personal or sensitive material that
an AI employee has no business reading.

### What NEVER to monitor

Even if a user adds a folder to `monitored_folders`, these patterns are always
blocked by the blacklist and will never produce vault entries:

| Pattern | Reason |
|---------|--------|
| `.ssh` | SSH keys and config — catastrophic if leaked |
| `.config` | App credentials, tokens, personal settings |
| `.env` | Environment files almost always contain secrets |
| `credentials` | Any file with this in the name |
| `passwords` | Any file with this in the name |

The blacklist is checked against the **full file path**, so a file at
`~/Downloads/my-credentials-backup.csv` is also blocked.

### How to add safe folders

Edit the `config.monitored_folders` list in this file's frontmatter:

```yaml
config:
  monitored_folders:
    - ~/Downloads
    - ~/Desktop/work-inbox    # explicit subfolder, not all of Desktop
```

Only add folders that contain external or work-related files. Never add home
directory root (`~`) or system folders.

### Blacklist protection

The blacklist runs **after** folder config. A folder can be in `monitored_folders`
and a file can still be silently skipped if its path matches any ignored pattern.
There is no way to whitelist a blacklisted pattern — safety wins.

---

## Implementation

When this skill is invoked, execute the following Python code using the
available environment.

```python
import sys
from pathlib import Path

# Ensure project root is on the path so watchers package is importable
PROJECT_ROOT = Path.home() / "Desktop/Hackathon/Hackathon0/ai-employee-project"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchers.file_watcher import FileWatcher

# ── Config ────────────────────────────────────────────────────────────────────

VAULT_PATH  = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault"
WATCH_DIR   = Path.home() / "Downloads"

# ── Single-shot scan (no continuous loop) ─────────────────────────────────────

def run():
    print("[file-monitor] Starting single-shot scan...")

    watcher = FileWatcher(vault_path=VAULT_PATH, watch_dir=WATCH_DIR)

    # Seed the watchdog observer, snapshot current Downloads contents,
    # then drain immediately — no sleep, no polling loop.
    watcher.watch_dir.mkdir(parents=True, exist_ok=True)

    from watchdog.observers import Observer
    observer = Observer()
    observer.schedule(watcher._handler, str(watcher.watch_dir), recursive=False)
    observer.start()

    # Snapshot existing files in Downloads (watchdog only fires on NEW events,
    # so we scan the folder directly for a one-shot check).
    from datetime import datetime, timezone
    items = []
    for path in watcher.watch_dir.iterdir():
        if not path.is_file():
            continue
        from watchers.file_watcher import _is_safe
        if not _is_safe(path):
            continue
        try:
            stat = path.stat()
            items.append({
                "path": path,
                "name": path.name,
                "suffix": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "detected_at": datetime.now(tz=timezone.utc),
            })
        except FileNotFoundError:
            pass

    observer.stop()
    observer.join()

    print(f"[file-monitor] {len(items)} eligible file(s) found in {watcher.watch_dir}")

    new_cards = []
    for item in items:
        card_path = watcher.create_action_file(item)
        new_cards.append(card_path)
        print(f"  [new]  Card created: {card_path.name}")

    if new_cards:
        print(f"\n[file-monitor] {len(new_cards)} new inbox card(s) created.")
        print("[file-monitor] Calling update-dashboard to refresh status...")
    else:
        print("[file-monitor] No new files detected.")

    return new_cards


run()
```

---

## Dashboard Integration

After this skill runs, always invoke the `update-dashboard` skill so the
Dashboard.md reflects the latest file count and recent activity. Pass the
number of new cards created as context.

---

## Usage Examples

**Invoke manually:**
> "Check for new files"
> "Monitor downloads"
> "Scan downloads folder"

**Expected output (new file found):**
```
[file-monitor] Starting scan...
[file-monitor] 1 eligible file(s) found in /home/user/Downloads
  [new]  Card created: FILE_20260404_143022_a1b2c3d4_report.pdf.md
[file-monitor] 1 new inbox card(s) created.
[file-monitor] Calling update-dashboard to refresh status...
```

**Expected output (nothing new):**
```
[file-monitor] Starting scan...
[file-monitor] 0 eligible file(s) found in /home/user/Downloads
[file-monitor] No new files detected.
```

**Vault card produced** (`Inbox/FILE_20260404_143022_a1b2c3d4_report.pdf.md`):
```yaml
---
type: file_drop
file_name: report.pdf
file_size: "1.2 MB (1258291 bytes)"
file_path: /home/user/Downloads/report.pdf
extension: .pdf
detected_at: "2026-04-04 14:30:22"
status: pending
priority: normal
---
```

---

## Dependencies

- `watchdog` — filesystem event monitoring (install via `pip install watchdog`)
- Standard library only beyond that: `os`, `re`, `hashlib`, `datetime`, `pathlib`
