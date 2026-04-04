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

Scans `Vault/Inbox/`, reads the frontmatter of each task card, routes it to
`Needs_Action/` or `Done/` based on type and content, then updates the dashboard.

---

## What This Skill Does

1. Lists all `.md` files in `Vault/Inbox/`
2. Parses the YAML frontmatter of each card
3. Applies routing rules to decide destination folder
4. Moves the file to `Needs_Action/` or `Done/`
5. Invokes `update-dashboard` after all moves are complete

---

## How to Run

Read each `.md` file in `Vault/Inbox/`, parse its frontmatter, apply the routing
rules below, and move the file using `shutil.move()`. If a filename conflict
exists at the destination, append `_1`, `_2`, etc.

```
Vault root:    ~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault
Inbox:         Vault/Inbox/
Needs_Action:  Vault/Needs_Action/
Done:          Vault/Done/
```

---

## Routing Rules

### type: file

| Condition | Destination |
|-----------|-------------|
| Extension in `.pdf .doc .docx .txt .md .csv .xlsx .xls` | `Needs_Action/` |
| Extension in `.png .jpg .jpeg .gif .webp .svg` | `Needs_Action/` |
| Extension in `.zip .tar .gz .rar .7z` | `Needs_Action/` |
| Extension in `.exe .msi .dmg .pkg .sh` | `Needs_Action/` (flag for manual review) |
| Extension in `.tmp .temp .bak` | `Done/` (auto-discard) |
| Filename contains `test`, `temp`, or `delete` | `Done/` (auto-discard) |
| Any other extension | `Needs_Action/` (safe default) |

### type: email

All emails go to `Needs_Action/` — no email is ever auto-discarded.

| Condition | Destination |
|-----------|-------------|
| `priority: high` | `Needs_Action/` |
| Subject contains `urgent` or `asap` | `Needs_Action/` |
| Subject contains `invoice` or `payment` | `Needs_Action/` |
| Anything else | `Needs_Action/` |

### Unknown type

Any card with an unrecognised or missing `type` field → `Needs_Action/` for manual triage.

---

## Dashboard Updates (after all moves)

After processing all cards, invoke `update-dashboard` to:

1. **Log activity** — `"process-inbox moved N cards → Needs_Action, M → Done"`
2. **Resync vault counts** — recount `Inbox/`, `Needs_Action/`, `Done/` and set exact values for `tasks_in_inbox`, `tasks_in_needs_action`, `tasks_completed`

---

## Expected Output

**Mixed inbox:**
```
[process-inbox] Found 3 card(s) in Inbox.

  [needs_action] EMAIL_20260404_143055_1a2b3c4d_Invoice_for_April.md
                 reason: financial keyword in subject
  [needs_action] FILE_20260404_150000_ab12cd34_report_pdf.md
                 reason: document (.pdf)
  [done]         FILE_20260404_151000_ef56gh78_temp_test_tmp.md
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
  [error] FILE_20260404_corrupt.md: frontmatter parse error — leaving in Inbox
```

---

## Error Handling

- If a card's frontmatter cannot be parsed → leave it in `Inbox/`, log an error, continue with remaining cards
- If a file move fails (permissions, disk full) → log the error, continue
- Never crash the full run because of a single bad card
