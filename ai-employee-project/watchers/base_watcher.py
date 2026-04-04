import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


def _setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class BaseWatcher(ABC):
    """Abstract base class for all watchers."""

    def __init__(self, vault_path: str | Path, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.check_interval = check_interval
        self.logger = _setup_logger(self.__class__.__name__)
        self._running = False

    @abstractmethod
    def check_for_updates(self) -> list[dict]:
        """Check the source for new items. Returns a list of item dicts."""
        ...

    @abstractmethod
    def create_action_file(self, item: dict) -> Path:
        """Write a vault action/task file for the given item. Returns the file path."""
        ...

    def run(self) -> None:
        """Main polling loop. Runs until interrupted or stop() is called."""
        self.logger.info(f"Starting {self.__class__.__name__} (interval={self.check_interval}s, vault={self.vault_path})")
        self._running = True

        while self._running:
            try:
                items = self.check_for_updates()
                self.logger.info(f"{len(items)} new item(s) found.")

                for item in items:
                    try:
                        path = self.create_action_file(item)
                        self.logger.info(f"Action file created: {path.name}")
                    except Exception as e:
                        self.logger.error(f"Failed to create action file for item {item}: {e}")

            except Exception as e:
                self.logger.error(f"Error during check_for_updates: {e}")

            self.logger.info(f"Next check in {self.check_interval}s...")
            time.sleep(self.check_interval)

        self.logger.info(f"{self.__class__.__name__} stopped.")

    def stop(self) -> None:
        """Signal the run loop to exit after the current iteration."""
        self._running = False
        self.logger.info("Stop signal received.")
