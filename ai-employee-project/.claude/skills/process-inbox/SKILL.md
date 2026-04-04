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

Scans all task cards in `Vault/Inbox/`, reads each card's frontmatter, applies
routing rules to decide the destination, moves the file, and updates the
dashboard when complete.

---

## Purpose

- Clears the Inbox by routing every pending card to the right vault folder
- Applies consistent business rules so nothing is misrouted or missed
- Distinguishes between items that need human action (`Needs_Action/`) and items that can be auto-closed (`Done/`)
- Keeps vault folder counts accurate by syncing Dashboard.md after every run
- Serves as the central triage step in the vault pipeline

---

## Process

1. List all `.md` files in `Vault/Inbox/`
2. If the inbox is empty, log "Inbox is empty" and stop
3. For each card, parse its YAML frontmatter to read `type`, `priority`, `subject`, `extension`, and `file_name`
4. Apply the routing rules below to determine destination: `Needs_Action/` or `Done/`
5. Move the file to the destination folder — if a filename conflict exists, append `_1`, `_2`, etc.
6. After all cards are processed, invoke `update-dashboard` to log activity and resync all vault counts

---

## Routing Rules

### type: file

| Condition | Destination |
|-----------|-------------|
| Extension `.pdf .doc .docx .txt .md .csv .xlsx .xls` | `Needs_Action/` |
| Extension `.png .jpg .jpeg .gif .webp .svg` | `Needs_Action/` |
| Extension `.zip .tar .gz .rar .7z` | `Needs_Action/` |
| Extension `.exe .msi .dmg .pkg .sh` | `Needs_Action/` — flag for manual review |
| Extension `.tmp .temp .bak` | `Done/` — auto-discard |
| Filename contains `test`, `temp`, or `delete` | `Done/` — auto-discard |
| Any other extension | `Needs_Action/` — safe default |

### type: email

All emails always go to `Needs_Action/` — no email is ever auto-discarded.

| Condition | Destination |
|-----------|-------------|
| `priority: high` | `Needs_Action/` |
| Subject contains `urgent` or `asap` | `Needs_Action/` |
| Subject contains `invoice` or `payment` | `Needs_Action/` |
| Anything else | `Needs_Action/` |

### Unknown type

Any card with a missing or unrecognised `type` field → `Needs_Action/` for manual triage.

---

## Usage Examples

> "Process inbox"
> "Triage my tasks"
> "What's in the inbox?"
> "Route inbox cards"

**Mixed inbox:**
```
[process-inbox] Found 3 card(s) in Inbox.

  [needs_action] EMAIL_20260405_143055_1a2b3c4d_Invoice_for_April.md
                 reason: financial keyword in subject
  [needs_action] FILE_20260405_150000_ab12cd34_report_pdf.md
                 reason: document (.pdf)
  [done]         FILE_20260405_151000_ef56gh78_temp_test_tmp.md
                 reason: auto-discarded (temp extension: .tmp)

──────────────────────────────────────────────────
[process-inbox] Processed 3 file(s)
  Moved to Needs_Action : 2
  Moved to Done         : 1
──────────────────────────────────────────────────
[process-inbox] Dashboard updated.
```

**Empty inbox:**
```
[process-inbox] Inbox is empty — nothing to process.
```

**Parse error:**
```
  [error] FILE_20260405_corrupt.md: frontmatter parse error — leaving in Inbox
```

---

## Dependencies

- `Vault/Inbox/` — source folder; must exist
- `Vault/Needs_Action/` — created automatically if missing
- `Vault/Done/` — created automatically if missing
- `python-frontmatter` Python package — used to parse YAML frontmatter from each card
- `update-dashboard` skill — must be invoked after this skill completes

---

## Notes

- If a card's frontmatter cannot be parsed, leave it in `Inbox/`, log the error, and continue — do not abort the entire run
- If a file move fails (permissions, disk full), log the error and continue with remaining cards
- Never auto-discard emails — a human must decide when an email card moves to `Done/`
- Run `update-dashboard` Operation D (full resync) after this skill — not individual +1/-1 updates — to guarantee folder count accuracy
- Cards in `Needs_Action/` remain there until a human manually moves them to `Done/`
