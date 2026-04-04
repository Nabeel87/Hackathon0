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

Reads `Dashboard.md` from the vault, updates the relevant section (activity log,
stats table, or status table), and writes the file back. No external libraries needed.

---

## What This Skill Does

1. Reads `Dashboard.md` from the vault
2. Applies one or more of the three update operations below
3. Stamps the `_Last updated:_` line at the top of the file
4. Writes the file back atomically (via a `.tmp` swap)

---

## How to Run

The dashboard has three update operations. Use whichever apply after a skill runs:

### Operation A — Log an activity entry

Add a timestamped line to the `## Recent Activity` section. Keeps the 20 most recent entries.

**When to use:** After any skill completes — file scan, email check, inbox processing.

**Format:** `- \`YYYY-MM-DD HH:MM\` — <message>`

**Example messages:**
- `"File monitor scanned ~/Downloads — 2 new files detected"`
- `"Gmail monitor found 1 priority email — invoice from vendor"`
- `"process-inbox moved 3 cards → Needs_Action"`

---

### Operation B — Update a stat counter

Update a single row in the `## Quick Stats` table by incrementing (`+1`), decrementing (`-1`), or setting to an exact value.

**Valid stat names and their table labels:**

| Stat name | Table label |
|-----------|-------------|
| `files_monitored` | Files monitored |
| `emails_checked` | Emails checked |
| `tasks_in_inbox` | Tasks in Inbox |
| `tasks_in_needs_action` | Tasks in Needs_Action |
| `tasks_completed` | Tasks completed |

**When to use:**
- After `file-monitor` runs → increment `files_monitored` by count of new cards
- After `gmail-monitor` runs → increment `emails_checked` by count of new cards
- After `process-inbox` moves cards → decrement `tasks_in_inbox`, increment destination counter

---

### Operation C — Update a component status row

Update a row in the `## System Status` table with a new status, last-run time, and optional note.

**Valid components:** `File Monitor`, `Gmail Monitor`, `Dashboard Updater`, `Inbox Processor`

**Valid statuses and their display values:**

| Status | Displayed as |
|--------|-------------|
| `ONLINE` | ✅ Running |
| `OFFLINE` | ⏸️ Not Running |
| `ERROR` | ❌ Error |
| `READY` | ✅ Ready |

**When to use:** After any watcher starts, stops, or errors.

---

### Operation D — Resync vault counts (full refresh)

Count files in `Inbox/`, `Needs_Action/`, and `Done/` folders and set the corresponding stats to exact values. Use after any bulk operation.

**Steps:**
1. Count `.md` files in `Vault/Inbox/`
2. Count `.md` files in `Vault/Needs_Action/`
3. Count `.md` files in `Vault/Done/`
4. Set `tasks_in_inbox`, `tasks_in_needs_action`, `tasks_completed` to those counts

---

## Dashboard File Location

```
~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/Dashboard.md
```

---

## Expected Output

**Activity logged:**
```
[update-dashboard] Activity logged: `2026-04-04 14:30` — Gmail monitor found 1 priority email
```

**Stat updated:**
```
[update-dashboard] Stat updated: Emails checked 4 → 5
```

**Component status updated:**
```
[update-dashboard] Status updated: File Monitor → ✅ Running at 2026-04-04 14:30
```

**Vault counts synced:**
```
[update-dashboard] Vault counts synced: inbox=3, needs_action=5, done=12
```

---

## When to Invoke

This skill should be called at the end of every other skill run:

| Trigger skill | What to update |
|---------------|---------------|
| `file-monitor` | Log activity, increment `files_monitored`, update `File Monitor` status |
| `gmail-monitor` | Log activity, increment `emails_checked`, update `Gmail Monitor` status |
| `process-inbox` | Log activity, resync all vault counts (Operation D) |
