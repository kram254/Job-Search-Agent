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

    def launch(self, headless: bool = None):
        if headless is not None:
            self.headless = headless
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def navigate(self, url: str):
        if self.page:
            self.page.goto(url, wait_until="networkidle")

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
