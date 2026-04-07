"""
watchers/whatsapp_watcher.py

Silver Tier — WhatsApp Web watcher using Playwright browser automation.

Monitors WhatsApp Web for unread messages matching priority keywords.
Creates WHATSAPP_*.md task cards in the Obsidian vault.

Session is persisted to .credentials/whatsapp_session/ so QR scan is
only required once. Subsequent runs reload the saved browser state.

Usage
-----
Standalone:
    python watchers/whatsapp_watcher.py
    python watchers/whatsapp_watcher.py --vault ~/AI_Employee_Vault --headless

Via orchestrator:
    from watchers.whatsapp_watcher import WhatsAppWatcher
    watcher = WhatsAppWatcher(vault_path=..., headless=True)
    watcher.run()

Dependencies
------------
    playwright (install with: pip install playwright && playwright install chromium)
"""

import re
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from watchers.base_watcher import BaseWatcher
from helpers.dashboard_updater import update_activity, update_component_status, update_stats

# ── Config ────────────────────────────────────────────────────────────────────

KEYWORDS = [
    "urgent", "asap", "client", "payment", "meeting",
    "invoice", "deadline", "action required", "follow up",
    "important", "review", "confirm", "approve",
]

DEFAULT_SESSION_DIR = (
    Path.home()
    / "Desktop/Hackathon/Hackathon0/ai-employee-project/.credentials/whatsapp_session"
)

WHATSAPP_URL = "https://web.whatsapp.com"

# How long to wait for WhatsApp Web to load after navigating (ms)
PAGE_LOAD_TIMEOUT = 60_000

# Selector for unread chat list items in WhatsApp Web
# WhatsApp Web renders unread counts as a span inside the chat row.
# These selectors target the unread badge that appears on chat rows.
UNREAD_CHAT_SELECTOR = 'div[role="listitem"]:has(span[aria-label*="unread"])'
CONTACT_NAME_SELECTOR = 'span[title]'
MESSAGE_PREVIEW_SELECTOR = 'div[class*="last-msg"] span, span[class*="last-message"]'
TIMESTAMP_SELECTOR = 'div[class*="last-msg-timestamp"], span[class*="yvgt"]'


# ── WhatsAppWatcher ───────────────────────────────────────────────────────────

class WhatsAppWatcher(BaseWatcher):
    """
    Polls WhatsApp Web for unread messages matching priority keywords.
    Uses Playwright with persistent browser context (session saved to disk).
    """

    def __init__(
        self,
        vault_path: str | Path,
        session_dir: str | Path | None = None,
        check_interval: int = 60,
        headless: bool = False,
        keywords: list[str] | None = None,
    ):
        super().__init__(vault_path, check_interval)
        self.session_dir  = Path(session_dir) if session_dir else DEFAULT_SESSION_DIR
        self.headless     = headless
        self.keywords     = [kw.lower() for kw in (keywords or KEYWORDS)]
        self._seen_ids: set[str] = set()

        # Playwright objects — initialised lazily on first check
        self._playwright  = None
        self._browser     = None
        self._page        = None

    # ── Playwright lifecycle ──────────────────────────────────────────────────

    def _start_browser(self) -> None:
        """Launch Playwright with a persistent context so session is preserved."""
        from playwright.sync_api import sync_playwright

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Session dir: {self.session_dir}")
        self.logger.info(f"Headless: {self.headless}")

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.session_dir),
            headless=self.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 900},
        )

        # Reuse existing page or open a new one
        pages = self._browser.pages
        self._page = pages[0] if pages else self._browser.new_page()

    def _ensure_browser(self) -> None:
        """Start browser if not already running."""
        if self._browser is None or self._page is None:
            self._start_browser()

    def _load_whatsapp(self) -> bool:
        """
        Navigate to WhatsApp Web if not already there.
        Returns True when the chat list is visible (logged in).
        Returns False if QR code is shown (first-time auth required).
        """
        current_url = self._page.url
        if "web.whatsapp.com" not in current_url:
            self.logger.info("Navigating to WhatsApp Web...")
            self._page.goto(WHATSAPP_URL, timeout=PAGE_LOAD_TIMEOUT)

        # Wait for either the chat list (logged in) or QR code (needs scan)
        try:
            self._page.wait_for_selector(
                'div[id="pane-side"], canvas[aria-label="Scan me!"]',
                timeout=PAGE_LOAD_TIMEOUT,
            )
        except Exception:
            self.logger.warning("Timeout waiting for WhatsApp Web to load.")
            return False

        if self._page.query_selector('canvas[aria-label="Scan me!"]'):
            self.logger.warning(
                "WhatsApp Web requires QR scan. "
                "Open a visible browser window and scan the QR code. "
                "Session will be saved for future runs."
            )
            # Wait up to 2 minutes for user to scan
            try:
                self._page.wait_for_selector(
                    'div[id="pane-side"]',
                    timeout=120_000,
                )
                self.logger.info("QR scan successful — session saved.")
            except Exception:
                self.logger.error("QR scan timed out. Stopping watcher.")
                return False

        return True

    def _close_browser(self) -> None:
        """Close browser and Playwright cleanly."""
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._browser   = None
        self._page      = None
        self._playwright = None

    # ── BaseWatcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list[dict]:
        """Scan WhatsApp Web for unread messages matching keywords."""
        try:
            self._ensure_browser()
        except Exception as exc:
            self.logger.error(f"Browser startup failed: {exc}")
            return []

        if not self._load_whatsapp():
            return []

        try:
            return self._scrape_unread_chats()
        except Exception as exc:
            self.logger.error(f"Scrape failed: {exc}", exc_info=True)
            # Browser may be in bad state — reset it
            self._close_browser()
            return []

    def _scrape_unread_chats(self) -> list[dict]:
        """Extract unread chats from the WhatsApp Web sidebar."""
        items = []

        # Wait briefly for the sidebar to settle
        self._page.wait_for_timeout(2000)

        # Try primary unread selector; fall back to scanning all chats
        chat_rows = self._page.query_selector_all(UNREAD_CHAT_SELECTOR)
        if not chat_rows:
            # Fallback: look for any span containing an unread count number
            chat_rows = self._page.query_selector_all(
                'div[role="listitem"]:has(span[aria-label])'
            )

        self.logger.info(f"Found {len(chat_rows)} candidate chat row(s).")

        for row in chat_rows:
            try:
                item = self._extract_chat_item(row)
                if item is None:
                    continue

                # Dedup
                uid = item["uid"]
                if uid in self._seen_ids or _already_logged(uid, self.vault_path):
                    continue

                # Keyword filter
                if not _matches_keywords(item["message_preview"], self.keywords):
                    self.logger.debug(f"Skipped (no keyword match): {item['contact']}")
                    continue

                self._seen_ids.add(uid)
                items.append(item)
                self.logger.info(f"New message from {item['contact']}: {item['message_preview'][:60]}")

            except Exception as exc:
                self.logger.warning(f"Failed to parse chat row: {exc}")

        return items

    def _extract_chat_item(self, row) -> dict | None:
        """Extract contact, preview, and timestamp from a chat row element."""
        # Contact name
        name_el = row.query_selector(CONTACT_NAME_SELECTOR)
        contact = name_el.get_attribute("title") if name_el else None
        if not contact:
            # Try inner text of the name span
            name_el = row.query_selector('span[dir="auto"]')
            contact = name_el.inner_text().strip() if name_el else "Unknown"

        contact = contact.strip() or "Unknown"

        # Message preview
        preview_el = row.query_selector(MESSAGE_PREVIEW_SELECTOR)
        if not preview_el:
            preview_el = row.query_selector('span[class*="message-text"]')
        preview = preview_el.inner_text().strip() if preview_el else ""

        # Skip rows with no message content
        if not preview:
            return None

        # Timestamp
        ts_el = row.query_selector(TIMESTAMP_SELECTOR)
        ts_text = ts_el.inner_text().strip() if ts_el else ""
        received_iso = _parse_wa_timestamp(ts_text)

        # Unique ID: contact + preview hash (stable within a session)
        uid = _make_uid(contact, preview)

        return {
            "uid":             uid,
            "contact":         contact,
            "message_preview": preview[:300],
            "received":        received_iso,
            "timestamp_raw":   ts_text,
        }

    def create_action_file(self, item: dict) -> Path:
        """Write a WHATSAPP_*.md card to vault Inbox/ or Needs_Action/."""
        priority = _infer_priority(item["message_preview"], self.keywords)
        folder   = "Needs_Action" if priority == "high" else "Inbox"
        target   = self.vault_path / folder
        target.mkdir(parents=True, exist_ok=True)

        ts_slug   = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = _safe_slug(item["contact"])
        card_name = f"WHATSAPP_{ts_slug}_{safe_name}.md"
        card_path = target / card_name

        def yml(v: str) -> str:
            return v.replace('"', '\\"')

        card_path.write_text(
            f"""---
type: whatsapp
from: "{yml(item['contact'])}"
message_preview: "{yml(item['message_preview'][:200])}"
received: "{item['received']}"
priority: {priority}
status: pending
uid: "{item['uid']}"
---

# WhatsApp: {item['contact']}

**From:** {item['contact']}
**Received:** {item['received']}
**Priority:** {priority}

---

## Message Preview

> {item['message_preview']}

---

## Suggested Actions

- [ ] Open WhatsApp and read the full message
- [ ] Determine if a reply is needed
- [ ] Log outcome in Notes below

---

## Notes

_Add context here as you process this message._
""",
            encoding="utf-8",
        )

        return card_path

    def post_cycle(self, created_count: int) -> None:
        """Update dashboard after new messages are detected."""
        try:
            update_activity(
                self.vault_path,
                f"WhatsApp Monitor: {created_count} new message(s) detected",
            )
            update_component_status(self.vault_path, "WhatsApp Monitor", "online")
            update_stats(
                self.vault_path, "emails_checked", created_count, operation="increment"
            )
        except Exception as exc:
            self.logger.warning(f"Dashboard update failed: {exc}")

    def stop(self) -> None:
        """Stop the watcher and close the browser."""
        super().stop()
        self._close_browser()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _matches_keywords(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears in the text (case-insensitive)."""
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _infer_priority(text: str, keywords: list[str]) -> str:
    """Return 'high' if urgent keywords found, else 'normal'."""
    urgent = {"urgent", "asap", "deadline", "action required"}
    lower  = text.lower()
    if any(kw in lower for kw in urgent):
        return "high"
    return "normal"


def _parse_wa_timestamp(ts_text: str) -> str:
    """
    Convert WhatsApp Web timestamp to ISO 8601.
    WhatsApp shows: "HH:MM", "Yesterday", or "DD/MM/YYYY".
    Falls back to current time if format is unrecognised.
    """
    now = datetime.now()
    if not ts_text:
        return now.strftime("%Y-%m-%d %H:%M:%S")

    # Time only (today): "14:35"
    match = re.match(r"^(\d{1,2}):(\d{2})$", ts_text)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        return now.replace(hour=h, minute=m, second=0, microsecond=0).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    # "Yesterday"
    if ts_text.lower() == "yesterday":
        from datetime import timedelta
        yesterday = now - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d 00:00:00")

    # Date: "07/04/2026" or "4/7/26"
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(ts_text, fmt).strftime("%Y-%m-%d 00:00:00")
        except ValueError:
            continue

    return now.strftime("%Y-%m-%d %H:%M:%S")


def _make_uid(contact: str, preview: str) -> str:
    """Stable unique ID from contact + first 80 chars of preview."""
    raw = f"{contact}::{preview[:80]}"
    return re.sub(r"[^\w]", "_", raw)[:80]


def _safe_slug(text: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip()
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len] or "unknown"


def _already_logged(uid: str, vault_path: Path) -> bool:
    """Return True if a card containing this uid already exists in the vault."""
    for folder in ("Inbox", "Needs_Action", "Done"):
        d = vault_path / folder
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix == ".md" and f.name.startswith("WHATSAPP_"):
                try:
                    if uid in f.read_text(encoding="utf-8"):
                        return True
                except OSError:
                    continue
    return False


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="whatsapp_watcher",
        description="Silver Tier — WhatsApp Web monitor.",
    )
    parser.add_argument(
        "--vault",
        default=str(
            Path.home() / "Desktop/Hackathon/Hackathon0/AI_Employee_Vault"
        ),
        help="Path to the Obsidian vault root",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Poll interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (requires prior session save)",
    )
    parser.add_argument(
        "--session-dir",
        default=None,
        help="Path to save/load browser session (default: .credentials/whatsapp_session/)",
    )
    args = parser.parse_args()

    watcher = WhatsAppWatcher(
        vault_path   = Path(args.vault),
        session_dir  = args.session_dir,
        check_interval = args.interval,
        headless     = args.headless,
    )
    watcher.run()
