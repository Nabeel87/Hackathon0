---
name: update-dashboard
description: "Updates Dashboard.md with activities and stats"
triggers:
  - update dashboard
  - refresh dashboard
  - log activity
  - update stats
config:
  dashboard_path: ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Dashboard.md
  max_activity_entries: 20
---

# Skill: update-dashboard

Reads `Dashboard.md` from the vault, surgically updates the relevant section
(activity log, stats table, or status table), and writes the file back.
No external libraries — pure standard library only.

---

## Implementation

```python
import re
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DASHBOARD_PATH = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Dashboard.md"
MAX_ACTIVITY_ENTRIES = 20

# Valid stat names and their display labels in the Quick Stats table
STAT_LABELS = {
    "files_monitored":        "Files monitored",
    "emails_checked":         "Emails checked",
    "tasks_in_inbox":         "Tasks in Inbox",
    "tasks_in_needs_action":  "Tasks in Needs_Action",
    "tasks_completed":        "Tasks completed",
}

# Valid component names as they appear in the System Status table
VALID_COMPONENTS = [
    "File Monitor",
    "Gmail Monitor",
    "Dashboard Updater",
    "Inbox Processor",
]

# Valid status strings
VALID_STATUSES = [
    "ONLINE",
    "OFFLINE",
    "ERROR",
    "READY",
]

# ── File I/O ──────────────────────────────────────────────────────────────────

def read_dashboard() -> str:
    """Read Dashboard.md and return its full text content."""
    if not DASHBOARD_PATH.exists():
        raise FileNotFoundError(
            f"Dashboard not found at {DASHBOARD_PATH}\n"
            "Ensure the vault was created with Dashboard.md in place."
        )
    return DASHBOARD_PATH.read_text(encoding="utf-8")


def write_dashboard(content: str) -> None:
    """Write updated content back to Dashboard.md atomically."""
    # Write to a temp file first, then replace — avoids partial writes
    tmp = DASHBOARD_PATH.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(DASHBOARD_PATH)


# ── Section finder ────────────────────────────────────────────────────────────

def find_section(content: str, header: str) -> tuple[int, int]:
    """
    Return (start, end) character indices of the content block that
    follows `header` up to (but not including) the next same-level heading.

    Raises ValueError if the section header is not found.
    """
    # Detect heading level from the number of leading #
    level = len(header) - len(header.lstrip("#"))
    pattern = re.escape(header)
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"Section header not found in Dashboard.md: '{header}'")

    start = match.end()

    # Find the next heading of the same or higher level
    next_heading = re.search(r"^#{1," + str(level) + r"} ", content[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content)

    return start, end


# ── a. update_activity ────────────────────────────────────────────────────────

def update_activity(message: str) -> None:
    """
    Prepend a timestamped entry to the Recent Activity section.
    Trims the list to MAX_ACTIVITY_ENTRIES.

    Format: `YYYY-MM-DD HH:MM - message`
    """
    content = read_dashboard()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"- `{now}` — {message}"

    start, end = find_section(content, "## Recent Activity")
    section_text = content[start:end]

    # Collect existing entries (lines starting with "- `")
    existing = [
        line for line in section_text.splitlines()
        if line.strip().startswith("- `")
    ]

    # Prepend new entry and cap at MAX_ACTIVITY_ENTRIES
    entries = [new_entry] + existing
    entries = entries[:MAX_ACTIVITY_ENTRIES]

    new_section = "\n\n" + "\n".join(entries) + "\n\n"
    updated = content[:start] + new_section + content[end:]

    # Stamp the "Last updated" line at the top of the file
    updated = re.sub(
        r"_Last updated:.*?_",
        f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        updated,
        count=1,
    )

    write_dashboard(updated)
    print(f"[update-dashboard] Activity logged: {new_entry}")


# ── b. update_stats ───────────────────────────────────────────────────────────

def update_stats(stat_name: str, operation: str = "+1", value: int = 0) -> None:
    """
    Update a single row in the Quick Stats table.

    Parameters
    ----------
    stat_name : str
        One of the keys in STAT_LABELS.
    operation : str
        "+1"  — increment current value by 1
        "=N"  — set value to N (pass the integer in `value`)
    value : int
        Used when operation is "=N".

    Examples
    --------
    update_stats("files_monitored", "+1")
    update_stats("tasks_completed", "=", value=5)
    """
    if stat_name not in STAT_LABELS:
        raise ValueError(
            f"Unknown stat '{stat_name}'. Valid stats: {list(STAT_LABELS.keys())}"
        )

    label = STAT_LABELS[stat_name]
    content = read_dashboard()

    # Match the table row for this stat:  | Label text   | current_value |
    row_pattern = re.compile(
        r"(\|\s*" + re.escape(label) + r"\s*\|\s*)(\d+)(\s*\|)",
        re.IGNORECASE,
    )
    match = row_pattern.search(content)
    if not match:
        raise ValueError(
            f"Could not find stat row for '{label}' in Dashboard.md.\n"
            "Check that the Quick Stats table uses the expected label text."
        )

    current = int(match.group(2))

    if operation == "+1":
        new_value = current + 1
    elif operation.startswith("=") or operation == "=":
        new_value = value
    else:
        raise ValueError(f"Unknown operation '{operation}'. Use '+1' or '='.")

    updated_row = match.group(1) + str(new_value) + match.group(3)
    updated = content[: match.start()] + updated_row + content[match.end() :]

    # Stamp last-updated
    updated = re.sub(
        r"_Last updated:.*?_",
        f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        updated,
        count=1,
    )

    write_dashboard(updated)
    print(f"[update-dashboard] Stat updated: {label} {current} → {new_value}")


# ── c. update_component_status ────────────────────────────────────────────────

def update_component_status(component: str, status: str, notes: str = "") -> None:
    """
    Update a component row in the System Status table.

    Parameters
    ----------
    component : str
        One of VALID_COMPONENTS (e.g. "File Monitor").
    status : str
        One of VALID_STATUSES: "ONLINE", "OFFLINE", "ERROR", "READY".
    notes : str
        Optional short note to write into the Notes column.

    Status display mapping
    ----------------------
    ONLINE  → ✅ Running
    OFFLINE → ⏸️ Not Running
    ERROR   → ❌ Error
    READY   → ✅ Ready
    """
    if component not in VALID_COMPONENTS:
        raise ValueError(
            f"Unknown component '{component}'. Valid: {VALID_COMPONENTS}"
        )
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Unknown status '{status}'. Valid: {VALID_STATUSES}"
        )

    status_display = {
        "ONLINE":  "✅ Running",
        "OFFLINE": "⏸️ Not Running",
        "ERROR":   "❌ Error",
        "READY":   "✅ Ready",
    }[status]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    note_text = notes if notes else ("—" if status == "OFFLINE" else "OK")

    content = read_dashboard()

    # Match the full row for this component, capturing each pipe-delimited cell
    row_pattern = re.compile(
        r"(\|\s*" + re.escape(component) + r"\s*\|)"   # | Component     |
        r"([^|]+\|)"                                    # | old status    |
        r"([^|]+\|)"                                    # | old last run  |
        r"([^|\n]+\|)",                                 # | old notes     |
        re.IGNORECASE,
    )
    match = row_pattern.search(content)
    if not match:
        raise ValueError(
            f"Could not find row for component '{component}' in Dashboard.md."
        )

    new_row = (
        f"| {component:<16}| {status_display:<8}| {now:<16}| {note_text:<22}|"
    )
    updated = content[: match.start()] + new_row + content[match.end() :]

    # Stamp last-updated
    updated = re.sub(
        r"_Last updated:.*?_",
        f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        updated,
        count=1,
    )

    write_dashboard(updated)
    print(f"[update-dashboard] Status updated: {component} → {status_display} at {now}")


# ── Convenience: full refresh ─────────────────────────────────────────────────

def refresh_vault_counts() -> None:
    """
    Re-count vault folder sizes and sync all task stats to Dashboard.
    Call this after any bulk operation that may have changed multiple counts.
    """
    vault_root = DASHBOARD_PATH.parent
    inbox_count        = sum(1 for f in (vault_root / "Inbox").iterdir()        if f.is_file()) if (vault_root / "Inbox").exists()        else 0
    needs_action_count = sum(1 for f in (vault_root / "Needs_Action").iterdir() if f.is_file()) if (vault_root / "Needs_Action").exists() else 0
    done_count         = sum(1 for f in (vault_root / "Done").iterdir()         if f.is_file()) if (vault_root / "Done").exists()         else 0

    update_stats("tasks_in_inbox",        "=", value=inbox_count)
    update_stats("tasks_in_needs_action", "=", value=needs_action_count)
    update_stats("tasks_completed",       "=", value=done_count)
    print(f"[update-dashboard] Vault counts synced: inbox={inbox_count}, needs_action={needs_action_count}, done={done_count}")


# ── Example usage (uncomment the call you need) ───────────────────────────────

# Log a new activity entry
update_activity("File monitor scanned ~/Downloads — 2 new files detected")

# Increment a stat by 1
# update_stats("files_monitored", "+1")

# Set a stat to an exact value
# update_stats("tasks_completed", "=", value=7)

# Update a component's status row
# update_component_status("File Monitor", "ONLINE")
# update_component_status("Gmail Monitor", "ERROR", notes="Token expired")

# Re-count all vault folders and sync stats
# refresh_vault_counts()
```

---

## How Markdown Parsing Works

This skill never uses a full markdown parser. Instead it uses two targeted
techniques:

### Section finding

`find_section(content, header)` locates a heading string (e.g. `## Recent Activity`)
and returns the character span of everything after it until the next heading
of equal or higher level. Edits are spliced in at that span.

### Table row updates

Table rows are matched with a regex anchored on the row's first cell value:

```
| File Monitor     | ⏸️ Not Running | —        | Watchdog not started   |
  ^^^^^^^^^^^^^^^^^^^
  anchored here
```

The regex captures each pipe-delimited cell individually so they can be
replaced while leaving the rest of the table untouched.

### Atomicity

Writes go to a `.tmp` file first, then `Path.replace()` swaps it in.
This prevents a half-written Dashboard on crash or permission error.

---

## Usage Examples

### Log an activity

```python
update_activity("Gmail monitor found 1 priority email — invoice from vendor")
```
Adds to Recent Activity:
```
- `2026-04-04 14:30` — Gmail monitor found 1 priority email — invoice from vendor
```

### Increment a stat

```python
update_stats("emails_checked", "+1")
```
Changes Quick Stats row:
```
| Emails checked      | 4     |   →   | Emails checked      | 5     |
```

### Set a stat to exact value

```python
update_stats("tasks_completed", "=", value=12)
```

### Mark a component online

```python
update_component_status("File Monitor", "ONLINE")
```
Changes System Status row:
```
| File Monitor     | ✅ Running | 2026-04-04 14:30 | OK                    |
```

### Mark a component with an error

```python
update_component_status("Gmail Monitor", "ERROR", notes="Token expired")
```

### Resync all task counts from vault folders

```python
refresh_vault_counts()
```

---

## Dependencies

None — standard library only: `re`, `datetime`, `pathlib`.
