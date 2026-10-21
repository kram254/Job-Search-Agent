import logging
import os
import subprocess  # noqa: F401 - used in _install_browsers_if_missing
import sys  # noqa: F401 - used in _install_browsers_if_missing
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger("playwright_wrapper")

class BrowserWrapper:
    # Thread-local launch state (bulk-apply fix #2): Playwright sync objects
    # are thread-bound; a single shared instance crashed with "Playwright
    # Sync API inside the asyncio loop" when request threads / the scan's
    # asyncio loop interleaved. Each thread now gets its own lazily-launched
    # browser, stored in thread-local storage.
    _tls = threading.local()
    _install_lock = threading.Lock()  # single-flight browser install
    _install_attempted = False  # class-level: once per process

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.session_dir = None
        self._storage_state_path: str = None
        self._launch_lock = threading.Lock()

    # --- thread-local accessors --------------------------------------- #
    @property
    def _state(self) -> dict:
        if not hasattr(BrowserWrapper._tls, "state"):
            BrowserWrapper._tls.state = {
                "playwright": None, "browser": None,
                "context": None, "page": None,
            }
        return BrowserWrapper._tls.state

    @property
    def playwright(self):
        return self._state.get("playwright")

    @playwright.setter
    def playwright(self, value):
        self._state["playwright"] = value

    @property
    def browser(self):
        return self._state.get("browser")

    @browser.setter
    def browser(self, value):
        self._state["browser"] = value

    @property
    def context(self):
        return self._state.get("context")

    @context.setter
    def context(self, value):
        self._state["context"] = value

    @property
    def page(self):
        return self._state.get("page")

    @page.setter
    def page(self, value):
        self._state["page"] = value

    def ensure_launched(self, headless: bool = None, storage_state_path: str = None):
        """Lazy-launch guard: web-request threads call navigate()/page before
        launch() ever runs, hitting 'NoneType has no attribute goto'.
        Idempotent — safe to call anywhere, per-thread."""
        if self.page is not None:
            return
        with self._launch_lock:
            if self.page is not None:  # double-checked under lock
                return
            self.launch(headless=headless, storage_state_path=storage_state_path)

    @property
    def current_page(self):
        """Page accessor that guarantees a launched session."""
        self.ensure_launched()
        return self.page

    def launch(self, headless: bool = None, storage_state_path: str = None):
        if headless is not None:
            self.headless = headless
        if storage_state_path:
            self._storage_state_path = storage_state_path
        self._install_browsers_if_missing()
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=self.headless)
        except Exception as e:
            # Browser-binary self-heal: the running service may lack the
            # browser at the default path (Render retrofits neither env vars
            # nor startCommand on existing services). Install on the spot,
            # then retry once.
            msg = str(e)
            if "Executable doesn't exist" in msg or "headless shell" in msg or "EACCES" in msg or "Failed to launch" in msg:
                logger.warning("[BrowserWrapper] browser binary missing - self-healing via playwright install chromium")
                self._install_browsers_if_missing(force=True)
                self.browser = self.playwright.chromium.launch(headless=self.headless)
            else:
                raise
        ctx_kwargs = {}
        if self._storage_state_path and Path(self._storage_state_path).exists():
            ctx_kwargs["storage_state"] = self._storage_state_path
        self.context = self.browser.new_context(**ctx_kwargs)
        self.page = self.context.new_page()

    @staticmethod
    def _install_browsers_if_missing(force: bool = False) -> None:
        """Run 'playwright install chromium' when no browser cache exists
        (or when force=True after a failed launch). Idempotent, ~60s first
        run, no-op afterwards. (Browser-binary self-heal fix.)"""
        import subprocess
        cache_candidates = [
            os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
            os.path.expanduser("~/.cache/ms-playwright"),
        ]
        has_browser = any(
            path and os.path.isdir(path) and any("chromium" in d.lower() for d in os.listdir(path))
            for path in cache_candidates if os.path.isdir(path)
        )
        if has_browser and not force:
            return
        # process-wide single-flight: concurrent installs race with
        # ETXTBSY (spawn on a binary being written). A lock + completed
        # flag makes exactly one install per process; others wait.
        with BrowserWrapper._install_lock:
            if getattr(BrowserWrapper, "_install_attempted", False) and not force:
                return
            BrowserWrapper._install_attempted = True
            try:
                logger.warning("[BrowserWrapper] installing chromium browsers...")
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    timeout=600, check=False,
                    capture_output=True,
                )
                logger.warning("[BrowserWrapper] playwright install finished")
            except Exception as e:
                logger.warning(f"[BrowserWrapper] playwright install failed: {e}")

    def navigate(self, url: str):
        self.ensure_launched()  # bulk-apply fix: never None when navigating
        if self.page:
            self.page.goto(url, wait_until="networkidle")

    def save_storage_state(self, path: str = None) -> None:
        target = path or self._storage_state_path
        if target and self.context:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            self.context.storage_state(path=target)

    def close(self):
        if self._storage_state_path and self.context:
            try:
                self.save_storage_state()
            except Exception:
                pass
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
        # clear THIS thread's state so the next call relaunches cleanly
        BrowserWrapper._tls.state = {
            "playwright": None, "browser": None,
            "context": None, "page": None,
        }
