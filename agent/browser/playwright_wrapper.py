import os
from pathlib import Path
from playwright.sync_api import sync_playwright

class BrowserWrapper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.session_dir = None
        self._storage_state_path: str = None

    def launch(self, headless: bool = None, storage_state_path: str = None):
        if headless is not None:
            self.headless = headless
        if storage_state_path:
            self._storage_state_path = storage_state_path
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        ctx_kwargs = {}
        if self._storage_state_path and Path(self._storage_state_path).exists():
            ctx_kwargs["storage_state"] = self._storage_state_path
        self.context = self.browser.new_context(**ctx_kwargs)
        self.page = self.context.new_page()

    def navigate(self, url: str):
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
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
