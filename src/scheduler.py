import threading
import time
from typing import Optional

from .config import DEFAULT_SETTINGS, load_settings
from .executor import run_execution_cycle


def _scrape_once_safe() -> Optional[dict]:
    try:
        from .login_fincs import scrape_once

        return scrape_once()
    except Exception:
        return None


def run_scheduler(stop_event: threading.Event) -> None:
    """
    Background loop: when settings.running is True, run scraper once then execute trades.
    """
    while not stop_event.is_set():
        settings = load_settings()
        if settings.get("running", False):
            import os

            os.environ["HEADLESS"] = "true" if settings.get("headless_scrape", True) else "false"
            _scrape_once_safe()
            try:
                run_execution_cycle()
            except Exception:
                pass
        poll = max(5, int(settings.get("poll_interval", DEFAULT_SETTINGS["poll_interval"])))
        stop_event.wait(poll)
