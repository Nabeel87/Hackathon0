# AI Employee - Bronze Tier

An autonomous AI employee system that monitors files and email, processes tasks,
and keeps a live dashboard — all driven by Claude agent skills.

## What is Bronze Tier?

Bronze is the minimal viable AI Employee. It handles two core jobs:

1. **File Monitor** — watches `~/Downloads` for new files and logs activity
2. **Gmail Monitor** — scans your inbox for priority keywords and surfaces action items

Everything is routed through a vault folder (`AI_Employee_Vault/`) that acts as
the employee's working memory.

## Folder Structure

```
ai-employee-project/       ← this repo (agent skills & config)
├── pyproject.toml
├── .gitignore
├── README.md
└── main.py

AI_Employee_Vault/         ← live working memory (separate from repo)
├── Dashboard.md           ← system status & recent activity
├── Company_Handbook.md    ← rules & policies the AI follows
├── Inbox/                 ← new items drop here
├── Needs_Action/          ← items requiring follow-up
└── Done/                  ← completed items
```

## Setup Instructions

> Full guide coming after skills are created.

Placeholder steps:

1. Clone this repo and `cd ai-employee-project`
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -e .`
4. Add Google OAuth `credentials.json` to the project root (not committed)
5. Run the agent skills via Claude Code

## Skills (coming soon)

- `file-monitor` — watchdog-based file watcher for Downloads
- `gmail-monitor` — Gmail API scanner for priority keywords
- `inbox-processor` — moves vault items through Inbox → Needs_Action → Done
- `dashboard-updater` — rewrites Dashboard.md with current system status
