---
name: process-inbox
description: "Processes task files from Inbox and routes them appropriately"
triggers:
  - process inbox
  - check inbox
  - triage tasks
  - what's in inbox
config:
  vault_root: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault
  inbox_dir: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Inbox
  needs_action_dir: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Needs_Action
  done_dir: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Done
---

# Skill: process-inbox

Scans the vault `Inbox/` folder, parses the frontmatter of each task card,
applies routing rules to decide the destination, moves the file, and updates
Dashboard.md for every move. Produces a triage summary at the end.

---

## Routing Rules

### type: file_drop

| Condition | Destination |
|-----------|-------------|
| Extension in documents/PDFs (`.pdf`, `.doc`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`, `.xls`) | `Needs_Action/` |
| Extension in images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`) | `Needs_Action/` |
| Extension in archives (`.zip`, `.tar`, `.gz`, `.rar`, `.7z`) | `Needs_Action/` |
| Extension in executables (`.exe`, `.msi`, `.dmg`, `.pkg`, `.sh`) | `Needs_Action/` |
| Extension is `.tmp`, `.temp`, `.bak`, or filename contains `test` / `temp` / `delete` | `Done/` (auto-discard) |
| Any other extension | `Needs_Action/` (safe default) |

### type: email

| Condition | Destination |
|-----------|-------------|
| `priority: high` | `Needs_Action/` |
| Subject or snippet contains `urgent` or `asap` | `Needs_Action/` |
| Subject or snippet contains `invoice` or `payment` | `Needs_Action/` |
| Anything else | `Needs_Action/` (all emails need human review) |

> Emails always go to `Needs_Action/`. No email is auto-discarded to `Done/`
> without a human making that call.

---

## Implementation

```python
import shutil
import re
from datetime import datetime
from pathlib import Path

import frontmatter  # python-frontmatter

# ── Config ────────────────────────────────────────────────────────────────────

VAULT_ROOT      = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault"
INBOX_DIR       = VAULT_ROOT / "Inbox"
NEEDS_ACTION_DIR = VAULT_ROOT / "Needs_Action"
DONE_DIR        = VAULT_ROOT / "Done"

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx", ".xls"}
IMAGE_EXTENSIONS    = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ARCHIVE_EXTENSIONS  = {".zip", ".tar", ".gz", ".rar", ".7z"}
EXEC_EXTENSIONS     = {".exe", ".msi", ".dmg", ".pkg", ".sh"}
DISCARD_EXTENSIONS  = {".tmp", ".temp", ".bak"}
DISCARD_NAME_HINTS  = ["test", "temp", "delete"]

# ── Dashboard integration ─────────────────────────────────────────────────────
# These functions mirror update-dashboard's API so this skill can call them
# directly without spawning a subprocess. In a full agent loop, Claude will
# invoke the update-dashboard skill after each move instead.

DASHBOARD_PATH = VAULT_ROOT / "Dashboard.md"

def _dashboard_read() -> str:
    return DASHBOARD_PATH.read_text(encoding="utf-8")

def _dashboard_write(content: str) -> None:
    tmp = DASHBOARD_PATH.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(DASHBOARD_PATH)

def _stamp(content: str) -> str:
    return re.sub(
        r"_Last updated:.*?_",
        f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        content, count=1,
    )

def _log_activity(message: str) -> None:
    content = _dashboard_read()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"- `{now}` — {message}"

    header = "## Recent Activity"
    match = re.search(re.escape(header), content)
    if not match:
        return
    start = match.end()
    next_h = re.search(r"^#{1,2} ", content[start:], re.MULTILINE)
    end = start + next_h.start() if next_h else len(content)

    existing = [
        line for line in content[start:end].splitlines()
        if line.strip().startswith("- `")
    ]
    entries = ([new_entry] + existing)[:20]
    new_section = "\n\n" + "\n".join(entries) + "\n\n"
    content = content[:start] + new_section + content[end:]
    _dashboard_write(_stamp(content))

def _update_stat(stat_label: str, operation: str, value: int = 0) -> None:
    content = _dashboard_read()
    pattern = re.compile(
        r"(\|\s*" + re.escape(stat_label) + r"\s*\|\s*)(\d+)(\s*\|)",
        re.IGNORECASE,
    )
    match = pattern.search(content)
    if not match:
        return
    current = int(match.group(2))
    new_val = (current + 1) if operation == "+1" else (current - 1) if operation == "-1" else value
    new_val = max(0, new_val)  # never go below 0
    updated_row = match.group(1) + str(new_val) + match.group(3)
    content = content[:match.start()] + updated_row + content[match.end():]
    _dashboard_write(_stamp(content))

# ── Routing logic ─────────────────────────────────────────────────────────────

def route_file_drop(post: frontmatter.Post, file_path: Path) -> tuple[Path, str]:
    """
    Decide destination for a file_drop task card.
    Returns (destination_dir, reason_string).
    """
    ext = post.get("extension", "").lower()
    file_name = post.get("file_name", file_path.name).lower()

    # Auto-discard: temp/test files
    if ext in DISCARD_EXTENSIONS:
        return DONE_DIR, f"auto-discarded (temp extension: {ext})"
    if any(hint in file_name for hint in DISCARD_NAME_HINTS):
        return DONE_DIR, f"auto-discarded (name hint match: {file_name})"

    # Everything else goes to Needs_Action
    if ext in DOCUMENT_EXTENSIONS:
        reason = f"document ({ext})"
    elif ext in IMAGE_EXTENSIONS:
        reason = f"image ({ext})"
    elif ext in ARCHIVE_EXTENSIONS:
        reason = f"archive ({ext})"
    elif ext in EXEC_EXTENSIONS:
        reason = f"executable ({ext}) — requires manual review"
    else:
        reason = f"unknown type ({ext}) — safe default"

    return NEEDS_ACTION_DIR, reason


def route_email(post: frontmatter.Post) -> tuple[Path, str]:
    """
    Decide destination for an email task card.
    All emails go to Needs_Action — reason string explains why.
    """
    priority = str(post.get("priority", "normal")).lower()
    subject  = str(post.get("subject", "")).lower()

    if priority == "high":
        return NEEDS_ACTION_DIR, "high priority email"
    if any(kw in subject for kw in ["urgent", "asap"]):
        return NEEDS_ACTION_DIR, f"urgent keyword in subject"
    if any(kw in subject for kw in ["invoice", "payment"]):
        return NEEDS_ACTION_DIR, f"financial keyword in subject"
    return NEEDS_ACTION_DIR, "standard review required"


def route(post: frontmatter.Post, file_path: Path) -> tuple[Path, str]:
    """Dispatch to the correct routing function based on task type."""
    task_type = str(post.get("type", "unknown")).lower()
    if task_type == "file_drop":
        return route_file_drop(post, file_path)
    if task_type == "email":
        return route_email(post)
    # Unknown type — send to Needs_Action for human triage
    return NEEDS_ACTION_DIR, f"unknown type '{task_type}' — manual triage"


# ── Move & update ─────────────────────────────────────────────────────────────

def move_card(file_path: Path, destination: Path) -> Path:
    """
    Move a vault card to destination folder.
    Appends a numeric suffix if a file with the same name already exists.
    """
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / file_path.name

    if target.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        i = 1
        while target.exists():
            target = destination / f"{stem}_{i}{suffix}"
            i += 1

    shutil.move(str(file_path), str(target))
    return target


def update_dashboard_for_move(destination: Path, task_name: str, reason: str) -> None:
    """Decrement inbox count, increment destination count, log activity."""
    _update_stat("Tasks in Inbox", "-1")

    if destination == NEEDS_ACTION_DIR:
        _update_stat("Tasks in Needs_Action", "+1")
        dest_label = "Needs_Action"
    else:
        _update_stat("Tasks completed", "+1")
        dest_label = "Done"

    _log_activity(f"process-inbox moved '{task_name}' → {dest_label} ({reason})")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    if not INBOX_DIR.exists():
        print(f"[process-inbox] Inbox folder not found: {INBOX_DIR}")
        return

    cards = [f for f in INBOX_DIR.iterdir() if f.is_file() and f.suffix == ".md"]

    if not cards:
        print("[process-inbox] Inbox is empty — nothing to process.")
        return

    print(f"[process-inbox] Found {len(cards)} card(s) in Inbox.\n")

    moved_to_needs_action = []
    moved_to_done = []
    errors = []

    for card in sorted(cards):
        try:
            post = frontmatter.load(str(card))
        except Exception as e:
            errors.append((card.name, f"frontmatter parse error: {e}"))
            print(f"  [error] {card.name}: {e}")
            continue

        destination, reason = route(post, card)
        dest_label = "Needs_Action" if destination == NEEDS_ACTION_DIR else "Done"

        try:
            final_path = move_card(card, destination)
            update_dashboard_for_move(destination, card.name, reason)

            if destination == NEEDS_ACTION_DIR:
                moved_to_needs_action.append((card.name, reason))
                print(f"  [needs_action] {card.name}")
                print(f"                 reason: {reason}")
            else:
                moved_to_done.append((card.name, reason))
                print(f"  [done]         {card.name}")
                print(f"                 reason: {reason}")

        except Exception as e:
            errors.append((card.name, f"move failed: {e}"))
            print(f"  [error] {card.name}: {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(moved_to_needs_action) + len(moved_to_done)
    print(f"\n{'─' * 50}")
    print(f"[process-inbox] Processed {total} file(s)")
    print(f"  Moved to Needs_Action : {len(moved_to_needs_action)}")
    print(f"  Moved to Done         : {len(moved_to_done)}")
    if errors:
        print(f"  Errors                : {len(errors)}")
        for name, msg in errors:
            print(f"    • {name}: {msg}")
    print(f"{'─' * 50}")
    print("[process-inbox] Dashboard updated. Run update-dashboard to verify.")

    return {
        "total": total,
        "needs_action": moved_to_needs_action,
        "done": moved_to_done,
        "errors": errors,
    }


run()
```

---

## Dashboard Integration

For every file moved this skill calls the embedded dashboard helpers directly
(`_log_activity`, `_update_stat`). These are exact copies of the logic in the
`update-dashboard` skill — kept inline so `process-inbox` can run standalone
without spawning a second skill call per file.

After the full run, Claude should invoke `update-dashboard` → `refresh_vault_counts()`
to do a final hard-sync of all folder counts.

---

## Usage Examples

**Invoke manually:**
> "Process inbox"
> "Check inbox"
> "Triage tasks"
> "What's in inbox"

**Expected output (mixed inbox):**
```
[process-inbox] Found 3 card(s) in Inbox.

  [needs_action] EMAIL_20260404_143055_1a2b3c4d_Invoice_for_April.md
                 reason: financial keyword in subject
  [needs_action] FILE_20260404_150000_ab12cd34_report.pdf.md
                 reason: document (.pdf)
  [done]         FILE_20260404_151000_ef56gh78_temp_test.tmp.md
                 reason: auto-discarded (temp extension: .tmp)

──────────────────────────────────────────────────────
[process-inbox] Processed 3 file(s)
  Moved to Needs_Action : 2
  Moved to Done         : 1
──────────────────────────────────────────────────────
[process-inbox] Dashboard updated. Run update-dashboard to verify.
```

**Expected output (empty inbox):**
```
[process-inbox] Inbox is empty — nothing to process.
```

**Expected output (parse error):**
```
[process-inbox] Found 1 card(s) in Inbox.

  [error] FILE_20260404_corrupt.md: frontmatter parse error: ...

──────────────────────────────────────────────────────
[process-inbox] Processed 0 file(s)
  Moved to Needs_Action : 0
  Moved to Done         : 0
  Errors                : 1
    • FILE_20260404_corrupt.md: frontmatter parse error: ...
──────────────────────────────────────────────────────
```

---

## Dependencies

- `python-frontmatter` — parses YAML frontmatter from markdown task cards
- Standard library only beyond that: `shutil`, `re`, `datetime`, `pathlib`
