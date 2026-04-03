# AI Employee — Bronze Tier

> Autonomous file and email monitoring, automated task creation, and live
> dashboard tracking — all powered by Claude agent skills.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Folder Structure](#folder-structure)
5. [Setup Guide](#setup-guide)
6. [Usage](#usage)
7. [Testing](#testing)
8. [Bronze Tier Checklist](#bronze-tier-checklist)
9. [Troubleshooting](#troubleshooting)
10. [Next Steps — Silver Tier](#next-steps--silver-tier)

---

## Overview

### What is Bronze Tier?

Bronze is the **minimal viable AI Employee**. It is the foundation layer — a
working autonomous agent that monitors two information streams, routes
everything into a structured vault, and keeps a live dashboard up to date.

It does not require a server, a scheduler, or any cloud infrastructure. It
runs on demand inside Claude Code and writes everything to plain markdown
files you can read in Obsidian, VS Code, or any text editor.

### What it does

| Job | How |
|-----|-----|
| File monitoring | Watches `~/Downloads` for new files, creates a task card for each one |
| Email monitoring | Scans Gmail for unread emails matching priority keywords |
| Task routing | Moves cards from Inbox through Needs_Action to Done |
| Dashboard tracking | Keeps a live status + activity log in `Dashboard.md` |

### Agent Skills architecture

Bronze tier is built as **Claude agent skills** — plain markdown files
(`.claude/skills/*/SKILL.md`) that contain a prompt header and embedded
Python code. Claude reads the skill, understands the intent, and executes
the code when you invoke the trigger phrase.

This means:
- No daemon processes running in the background
- No cron jobs or schedulers to configure
- Skills are readable, editable, version-controlled markdown
- Claude decides *when* to chain skills together

---

## Features

- **File system monitoring** — scans `~/Downloads`, creates structured task
  cards with metadata (name, size, extension, timestamp, suggested actions)
- **Gmail monitoring** — read-only Gmail API, filters for `urgent`, `asap`,
  `invoice`, `payment` keywords, never reads full email body
- **Automated task creation** — every detected file or email becomes a
  markdown card with YAML frontmatter in the vault Inbox
- **Dashboard tracking** — live `Dashboard.md` with system status table,
  quick stats, recent activity log, and alerts
- **Privacy-safe defaults** — only `~/Downloads` monitored by default;
  `.ssh`, `.env`, `credentials`, `passwords` permanently blacklisted

---

## Architecture

```
  INPUTS                SKILLS               VAULT
  ──────                ──────               ─────

  ~/Downloads  ──────►  file-monitor   ────► Inbox/
                        (watchdog scan)       FILE_*.md

  Gmail Inbox  ──────►  gmail-monitor  ────► Inbox/
                        (API + keywords)      EMAIL_*.md

                             │
                             ▼
                        process-inbox  ────► Needs_Action/
                        (triage rules)        (pdfs, emails,
                             │                images, archives)
                             │
                             └──────────────► Done/
                                              (temp files,
                                               resolved tasks)

  All skills   ──────►  update-dashboard ──► Dashboard.md
                        (after every run)     (stats + activity)
```

### Data flow detail

1. You say *"check for new files"* → `file-monitor` scans `~/Downloads`
2. Each safe, non-blacklisted file → `FILE_YYYYMMDD_HHMMSS_<hash>_<name>.md`
   written to `Inbox/` with full YAML frontmatter
3. You say *"process inbox"* → `process-inbox` reads each card's frontmatter,
   applies routing rules, moves it to `Needs_Action/` or `Done/`
4. After every skill run → `update-dashboard` rewrites stats and logs activity
5. Open `AI_Employee_Vault/` in Obsidian to see everything in a live view

---

## Folder Structure

```
~/Desktop/Hackathon/Hackathon0/
│
├── ai-employee-project/          ← this repo (code & config)
│   ├── .claude/
│   │   └── skills/
│   │       ├── file-monitor/
│   │       │   └── SKILL.md      ← Downloads scanner
│   │       ├── gmail-monitor/
│   │       │   └── SKILL.md      ← Gmail API scanner
│   │       ├── process-inbox/
│   │       │   └── SKILL.md      ← Inbox triage router
│   │       └── update-dashboard/
│   │           └── SKILL.md      ← Dashboard writer
│   ├── .credentials/             ← OAuth files (git-ignored)
│   │   ├── credentials.json      ← from Google Cloud Console
│   │   └── token.json            ← auto-created on first run
│   ├── .gitignore
│   ├── GMAIL_SETUP.md            ← Gmail API setup guide
│   ├── README.md                 ← this file
│   └── pyproject.toml
│
└── AI_Employee_Vault/            ← live working memory (Obsidian vault)
    ├── Dashboard.md              ← system status & activity log
    ├── Company_Handbook.md       ← rules & policies
    ├── Inbox/                    ← new FILE_*.md and EMAIL_*.md land here
    ├── Needs_Action/             ← items routed here for human follow-up
    └── Done/                     ← resolved items (kept for audit trail)
```

### Key files explained

| File | Purpose |
|------|---------|
| `SKILL.md` (each) | The skill definition — prompt header + Python implementation |
| `Dashboard.md` | Updated automatically after every skill run |
| `Company_Handbook.md` | The AI employee's rules — what to monitor, what to skip |
| `credentials.json` | Your OAuth app identity from Google Cloud Console |
| `token.json` | Your personal Gmail access token — auto-refreshed |

---

## Setup Guide

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- [Claude Code](https://claude.ai/code) CLI
- A Google account (for Gmail monitoring)
- [Obsidian](https://obsidian.md/) (optional, for vault viewing)

---

### Step 1 — Clone and enter the project

```bash
cd ~/Desktop/Hackathon/Hackathon0/ai-employee-project
```

---

### Step 2 — Install dependencies with uv

```bash
uv pip install watchdog python-frontmatter google-api-python-client \
               google-auth-httplib2 google-auth-oauthlib
```

Expected output:
```
Resolved 26 packages in 668ms
Installed 26 packages in 898ms
 + watchdog==6.0.0
 + python-frontmatter==1.1.0
 + google-api-python-client==2.193.0
 ...
```

> **Important:** Always invoke Python skills with `uv run python3` to ensure
> the correct environment is used. Bare `python3` on Windows may point to a
> different interpreter that cannot see uv-installed packages.

---

### Step 3 — Gmail API setup

Follow the detailed guide in [`GMAIL_SETUP.md`](./GMAIL_SETUP.md).

Short version:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project `ai-employee` → enable Gmail API
3. Create OAuth Desktop credentials → download `credentials.json`
4. Move it to `.credentials/credentials.json`
5. First skill run opens a browser for one-time authorisation

> Skip this step if you only want to test file monitoring.

---

### Step 4 — Open the vault in Obsidian (optional)

1. Open Obsidian → **Open folder as vault**
2. Navigate to `~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/`
3. Click **Open**
4. Pin `Dashboard.md` — it updates automatically as skills run

---

## Usage

### Starting Claude Code

```bash
cd ~/Desktop/Hackathon/Hackathon0/ai-employee-project
claude
```

---

### Invoking skills

Each skill responds to natural language trigger phrases.

#### file-monitor

```
check for new files
monitor downloads
scan downloads
```

What happens:
- Scans `~/Downloads` for non-blacklisted files
- Creates `FILE_YYYYMMDD_HHMMSS_<hash>_<name>.md` in `Inbox/`
- Skips files already logged (MD5 fingerprint dedup)
- Updates Dashboard stats

---

#### gmail-monitor

```
check gmail
check my email
scan inbox
monitor email
```

What happens:
- Authenticates with Gmail API (browser prompt on first run only)
- Searches: `is:unread label:inbox ("urgent" OR "asap" OR "invoice" OR "payment")`
- Creates `EMAIL_YYYYMMDD_HHMMSS_<id>_<subject>.md` in `Inbox/`
- Stores sender, subject, 200-char snippet only — never full body

---

#### process-inbox

```
process inbox
check inbox
triage tasks
what's in inbox
```

What happens:
- Reads every `.md` file in `Inbox/`
- Parses YAML frontmatter to determine type and metadata
- Routes by rule:
  - Documents, images, archives, executables → `Needs_Action/`
  - `.tmp`, `.temp`, `.bak`, files named `test`/`temp`/`delete` → `Done/`
  - All emails → `Needs_Action/` (no email auto-discarded)
- Updates Dashboard after each move

---

#### update-dashboard

```
update dashboard
refresh dashboard
log activity
update stats
```

What happens:
- Reads `Dashboard.md`
- Updates System Status table, Quick Stats, or Recent Activity
- Stamps "Last updated" timestamp
- Writes back atomically

---

### Example workflows

**Morning check:**
```
You:    Check my email
Claude: [runs gmail-monitor] Found 2 priority emails. Cards created in Inbox.

You:    Process inbox
Claude: [runs process-inbox] Moved 2 to Needs_Action. Dashboard updated.
```

**End of day file sweep:**
```
You:    Scan downloads
Claude: [runs file-monitor] 5 new files detected. Cards created in Inbox.

You:    Triage tasks
Claude: [runs process-inbox] Moved 4 to Needs_Action, 1 to Done (temp file).

You:    Refresh dashboard
Claude: [runs update-dashboard] Stats synced. Activity logged.
```

**Full autonomous cycle:**
```
You:    Check for new files and emails, then process everything
Claude: [runs file-monitor] → [runs gmail-monitor] → [runs process-inbox]
        → [runs update-dashboard]
        Summary: 7 items processed. 6 in Needs_Action, 1 in Done.
```

---

## Testing

### Quick smoke test

Run this to verify all skills are wired up correctly:

```bash
cd ~/Desktop/Hackathon/Hackathon0/ai-employee-project
claude
```

Then in Claude Code:
```
Check for new files
```

Expected: Claude reads `.claude/skills/file-monitor/SKILL.md`, executes the
scan, and reports cards created (or "no new files" if Downloads is empty).

---

### Full end-to-end test

1. Create a test file:
   ```bash
   touch ~/Downloads/test_invoice.pdf
   ```

2. In Claude Code, run in sequence:
   ```
   Check for new files
   Process inbox
   Update dashboard
   ```

3. Verify:
   - `AI_Employee_Vault/Inbox/` — should be empty
   - `AI_Employee_Vault/Needs_Action/` — should contain `FILE_*test_invoice*`
   - `AI_Employee_Vault/Dashboard.md` — Tasks in Needs_Action should be 1

4. Clean up:
   ```bash
   rm ~/Downloads/test_invoice.pdf
   ```

---

### Expected vault state after a clean test

```
Inbox/          0 files   (all processed)
Needs_Action/   4 files   (invoice, report, photo, archive)
Done/           1 file    (temp file auto-discarded)
```

---

## Bronze Tier Checklist

### Project setup
- [ ] Repository cloned / project folder created
- [ ] `pyproject.toml` configured with correct name and dependencies
- [ ] `.gitignore` in place (covers `.env`, `.credentials/`, `token.json`)
- [ ] All dependencies installed via `uv pip install`

### Skills created
- [ ] `.claude/skills/file-monitor/SKILL.md` — Downloads scanner
- [ ] `.claude/skills/gmail-monitor/SKILL.md` — Gmail API scanner
- [ ] `.claude/skills/process-inbox/SKILL.md` — Inbox triage router
- [ ] `.claude/skills/update-dashboard/SKILL.md` — Dashboard writer

### Vault setup
- [ ] `AI_Employee_Vault/` folder created
- [ ] `Dashboard.md` present with System Status and Quick Stats tables
- [ ] `Company_Handbook.md` present with monitoring rules
- [ ] `Inbox/`, `Needs_Action/`, `Done/` subfolders created
- [ ] Vault opened in Obsidian (optional)

### Gmail setup
- [ ] Google Cloud project created
- [ ] Gmail API enabled
- [ ] OAuth consent screen configured
- [ ] Desktop OAuth credentials created and downloaded
- [ ] `credentials.json` placed in `.credentials/`
- [ ] First-run browser authorisation completed
- [ ] `token.json` confirmed present after first run

### End-to-end verified
- [ ] `file-monitor` detects a test file and creates an Inbox card
- [ ] `gmail-monitor` authenticates and runs without error
- [ ] `process-inbox` routes cards to correct folders
- [ ] `update-dashboard` reflects correct stats and activity

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'frontmatter'`

You are using the wrong Python interpreter. Use `uv run`:

```bash
uv run python3 -c "import frontmatter; print('OK')"
```

If that fails, reinstall:
```bash
uv pip install python-frontmatter
```

---

### `credentials.json not found`

The Gmail credentials file is missing. See [`GMAIL_SETUP.md`](./GMAIL_SETUP.md)
Steps 1–4 to create and download it, then:

```bash
mkdir -p .credentials
mv ~/Downloads/client_secret_*.json .credentials/credentials.json
```

---

### `Token has been expired or revoked`

Delete the old token and re-authorise:

```bash
rm .credentials/token.json
```

Then invoke `gmail-monitor` again — the browser flow will repeat once.

---

### Dashboard stats look wrong after a bulk run

Re-sync from actual folder counts:

```python
# In update-dashboard skill, call:
refresh_vault_counts()
```

Or manually count and set:
```
Update dashboard — set tasks_in_inbox to 0, tasks_in_needs_action to 4
```

---

### Obsidian shows empty vault

Ensure you opened the correct folder:
`~/Desktop/Hackathon/Hackathon0/AI_Employee_Vault/`

Not the project folder. The vault and the project are separate directories.

---

### File cards not being created

Check that `~/Downloads` exists and is accessible:

```bash
ls ~/Downloads | head -5
```

If you are on Windows and `Path.home() / "Downloads"` resolves incorrectly,
check the path printed in skill output and adjust `VAULT_INBOX` in the skill.

---

## Next Steps — Silver Tier

Bronze tier is complete. Silver tier builds on this foundation with:

| Feature | Description |
|---------|-------------|
| **Scheduled monitoring** | Auto-run skills on a cron schedule (no manual invoke) |
| **Calendar integration** | Google Calendar awareness — deadlines surface in dashboard |
| **Smart summarisation** | Claude reads email snippets and writes plain-English summaries |
| **Priority scoring** | Automatic 1–5 priority score on every task card |
| **Slack notifications** | Push alerts to a Slack channel when high-priority items arrive |
| **Multi-folder watching** | Configurable watch list beyond Downloads |
| **Weekly digest** | Auto-generated weekly summary of Done items |

Silver tier turns the on-demand Bronze system into a continuously running
autonomous employee that proactively surfaces what needs your attention.

---

*Built for the AI Employee Hackathon — Bronze Tier complete.*
