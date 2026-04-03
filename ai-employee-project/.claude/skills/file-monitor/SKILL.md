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
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

MONITORED_FOLDERS = [
    Path.home() / "Downloads",
]

IGNORED_PATTERNS = [
    ".ssh", ".config", ".env", "credentials", "passwords",
]

VAULT_INBOX = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Inbox"

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_blacklisted(file_path: Path) -> bool:
    """Return True if any ignored pattern appears in the full path string."""
    path_str = str(file_path).lower()
    return any(pattern.lower() in path_str for pattern in IGNORED_PATTERNS)


def human_readable_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def suggested_actions(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    actions_map = {
        ("pdf",): [
            "- [ ] Review document contents",
            "- [ ] File in appropriate project folder",
            "- [ ] Check if signature or response required",
        ],
        ("csv", "xlsx", "xls"): [
            "- [ ] Check data source and validity",
            "- [ ] Import to relevant tool or database",
            "- [ ] Archive after processing",
        ],
        ("zip", "tar", "gz", "rar", "7z"): [
            "- [ ] Scan archive contents before extracting",
            "- [ ] Extract to dedicated folder",
            "- [ ] Verify expected files are present",
        ],
        ("png", "jpg", "jpeg", "gif", "webp"): [
            "- [ ] Identify image purpose",
            "- [ ] Move to media library if permanent",
        ],
        ("docx", "doc", "txt", "md"): [
            "- [ ] Read and summarise if needed",
            "- [ ] File in appropriate project folder",
        ],
        ("exe", "msi", "dmg", "pkg"): [
            "- [ ] Verify source and checksum before running",
            "- [ ] Check VirusTotal if origin is unknown",
            "- [ ] Install only if intentional download",
        ],
    }
    for extensions, actions in actions_map.items():
        if ext in extensions:
            return "\n".join(actions)
    return "- [ ] Review file and determine next action"


def scan_folder(folder: Path) -> list[Path]:
    """Return all files in folder (non-recursive, non-hidden, non-blacklisted)."""
    if not folder.exists():
        print(f"[file-monitor] Folder not found, skipping: {folder}")
        return []
    return [
        f for f in folder.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and not is_blacklisted(f)
    ]


def already_logged(file_path: Path) -> bool:
    """Check if a vault Inbox entry already exists for this file path."""
    if not VAULT_INBOX.exists():
        return False
    fingerprint = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
    return any(fingerprint in f.name for f in VAULT_INBOX.iterdir())


def create_inbox_card(file_path: Path) -> Path:
    """Write a markdown task card to the vault Inbox and return its path."""
    stat = file_path.stat()
    now = datetime.now()
    timestamp_slug = now.strftime("%Y%m%d_%H%M%S")
    detected_at = now.strftime("%Y-%m-%d %H:%M:%S")
    fingerprint = hashlib.md5(str(file_path).encode()).hexdigest()[:8]

    safe_name = re.sub(r"[^\w\-.]", "_", file_path.name)
    card_name = f"FILE_{timestamp_slug}_{fingerprint}_{safe_name}.md"
    card_path = VAULT_INBOX / card_name

    VAULT_INBOX.mkdir(parents=True, exist_ok=True)

    size_bytes = stat.st_size
    size_human = human_readable_size(size_bytes)
    extension = file_path.suffix or "none"
    actions = suggested_actions(extension)

    card_content = f"""---
type: file_drop
file_name: {file_path.name}
file_size: "{size_human} ({size_bytes} bytes)"
file_path: {file_path}
extension: {extension}
detected_at: "{detected_at}"
status: pending
priority: normal
---

# File Detected: {file_path.name}

**Detected at:** {detected_at}
**Location:** `{file_path}`
**Size:** {size_human}
**Type:** `{extension}`

---

## Suggested Actions

{actions}

---

## Notes

_Add context here as you process this file._
"""

    card_path.write_text(card_content, encoding="utf-8")
    return card_path


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("[file-monitor] Starting scan...")
    new_cards = []

    for folder in MONITORED_FOLDERS:
        files = scan_folder(folder)
        print(f"[file-monitor] {len(files)} eligible file(s) found in {folder}")

        for file_path in files:
            if already_logged(file_path):
                print(f"  [skip] Already logged: {file_path.name}")
                continue

            card_path = create_inbox_card(file_path)
            new_cards.append(card_path)
            print(f"  [new]  Card created: {card_path.name}")

    if new_cards:
        print(f"\n[file-monitor] {len(new_cards)} new inbox card(s) created.")
        print("[file-monitor] Calling update-dashboard to refresh status...")
        # Trigger the update-dashboard skill after writing cards
        # (Claude will invoke it as a follow-up skill call)
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
