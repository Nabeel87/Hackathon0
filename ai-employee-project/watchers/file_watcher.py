import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

from watchers.base_watcher import BaseWatcher

# ── Security blacklist ────────────────────────────────────────────────────────

BLACKLIST_PATTERNS = [
    r"\.ssh",
    r"\.config",
    r"\.env",
    r"credentials",
    r"passwords?",
    r"secret",
    r"private[_\-]?key",
    r"id_rsa",
    r"\.pem",
    r"\.p12",
    r"\.pfx",
]

_BLACKLIST_RE = re.compile("|".join(BLACKLIST_PATTERNS), re.IGNORECASE)


def _is_safe(path: Path) -> bool:
    """Return False if the file should be ignored for privacy/security reasons."""
    name = path.name
    # Hidden files (Unix-style dot files)
    if name.startswith("."):
        return False
    # Temp/lock files
    if name.startswith("~") or name.endswith(".tmp") or name.endswith(".part"):
        return False
    # Blacklisted name patterns
    if _BLACKLIST_RE.search(str(path)):
        return False
    return True


# ── Watchdog event handler ────────────────────────────────────────────────────

class _NewFileHandler(FileSystemEventHandler):
    """Collects newly created file paths into a thread-safe list."""

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._queue: list[Path] = []

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_safe(path):
            with self._lock:
                self._queue.append(path)

    def drain(self) -> list[Path]:
        """Return and clear all queued paths."""
        with self._lock:
            items, self._queue = self._queue, []
        return items


# ── FileWatcher ───────────────────────────────────────────────────────────────

class FileWatcher(BaseWatcher):
    """Watches ~/Downloads for new files and creates vault action cards."""

    def __init__(
        self,
        vault_path: str | Path,
        watch_dir: str | Path | None = None,
        check_interval: int = 30,
    ):
        super().__init__(vault_path, check_interval)
        self.watch_dir = Path(watch_dir) if watch_dir else Path.home() / "Downloads"
        self._handler = _NewFileHandler()
        self._observer = Observer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(self.watch_dir), recursive=False)
        self._observer.start()
        self.logger.info(f"Watching directory: {self.watch_dir}")
        try:
            super().run()
        finally:
            self._observer.stop()
            self._observer.join()
            self.logger.info("Watchdog observer stopped.")

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list[dict]:
        """Drain queued new-file events and return metadata dicts."""
        paths = self._handler.drain()
        items = []
        for path in paths:
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
                self.logger.warning(f"File disappeared before stat: {path}")
        return items

    def create_action_file(self, item: dict) -> Path:
        """Write a FILE_*.md card to vault Inbox/ and return its path."""
        vault_inbox = self.vault_path / "Inbox"
        vault_inbox.mkdir(parents=True, exist_ok=True)

        dt: datetime = item["detected_at"]
        ts_slug = dt.strftime("%Y%m%d_%H%M%S")
        name_slug = _safe_slug(item["name"])
        card_name = f"FILE_{ts_slug}_{name_slug}.md"
        card_path = vault_inbox / card_name

        size_kb = item["size_bytes"] / 1024
        received_iso = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        file_type = item["suffix"] or "unknown"
        priority = _infer_priority(item["name"], item["suffix"])
        actions = _suggested_actions(item["suffix"])

        card_path.write_text(
            f"""---
type: file
name: "{item['name']}"
path: "{item['path']}"
size_kb: {size_kb:.1f}
file_type: "{file_type}"
detected: "{received_iso}"
priority: {priority}
status: pending
---

# New File: {item['name']}

**Path:** `{item['path']}`
**Size:** {size_kb:.1f} KB
**Type:** {file_type}
**Detected:** {received_iso}
**Priority:** {priority}

---

## Suggested Actions

{actions}

---

## Notes

_Add context here as you process this file._
""",
            encoding="utf-8",
        )
        return card_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip()
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len]


def _infer_priority(name: str, suffix: str) -> str:
    high_suffixes = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip", ".exe", ".dmg"}
    if suffix in high_suffixes:
        return "high"
    urgent_words = re.compile(r"urgent|invoice|contract|payment|asap", re.IGNORECASE)
    if urgent_words.search(name):
        return "high"
    return "normal"


def _suggested_actions(suffix: str) -> str:
    actions = {
        ".pdf": (
            "- [ ] Open and review PDF contents\n"
            "- [ ] Check sender/source legitimacy\n"
            "- [ ] File in appropriate project folder\n"
            "- [ ] Extract key data if needed"
        ),
        ".docx": (
            "- [ ] Review document contents\n"
            "- [ ] Check for tracked changes or comments\n"
            "- [ ] Save to project folder"
        ),
        ".xlsx": (
            "- [ ] Open spreadsheet and review data\n"
            "- [ ] Validate formulas and values\n"
            "- [ ] Archive or import as needed"
        ),
        ".zip": (
            "- [ ] Scan archive before extracting\n"
            "- [ ] Extract to a sandboxed folder\n"
            "- [ ] Review contents"
        ),
        ".exe": (
            "- [ ] **Do not run without verifying source**\n"
            "- [ ] Scan with antivirus\n"
            "- [ ] Confirm legitimacy before executing"
        ),
    }
    return actions.get(suffix, (
        "- [ ] Review the file\n"
        "- [ ] Determine if action is needed\n"
        "- [ ] Archive or delete when resolved"
    ))


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    vault = Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault"
    watch = Path.home() / "Downloads"

    if len(sys.argv) > 1:
        watch = Path(sys.argv[1])
    if len(sys.argv) > 2:
        vault = Path(sys.argv[2])

    watcher = FileWatcher(vault_path=vault, watch_dir=watch, check_interval=30)
    try:
        watcher.run()
    except KeyboardInterrupt:
        watcher.stop()
