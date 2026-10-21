"""Tests for the bulk-apply fixes: browser lazy-launch + URL resolution."""
from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.browser.playwright_wrapper import BrowserWrapper


class TestBrowserLazyLaunch:

    def setup_method(self, method):
        # thread-local state persists on the pytest thread between tests —
        # clear it so each test starts from a fresh launch state
        if hasattr(BrowserWrapper._tls, "state"):
            BrowserWrapper._tls.state = {
                "playwright": None, "browser": None,
                "context": None, "page": None,
            }

    def test_ensure_launched_is_idempotent(self):
        w = BrowserWrapper(headless=True)
        calls = {"n": 0}

        def fake_launch(headless=None, storage_state_path=None):
            calls["n"] += 1
            w.page = object()  # mark launched (this thread's TLS state)

        w.launch = fake_launch
        w.ensure_launched()
        w.ensure_launched()
        w.ensure_launched()
        assert calls["n"] == 1, "launch should run exactly once per thread"

    def test_navigate_does_not_hit_none_page(self):
        w = BrowserWrapper(headless=True)
        navigated = {"url": None}

        def fake_launch(headless=None, storage_state_path=None):
            class FakePage:
                def goto(self, url, **kw):
                    navigated["url"] = url
            w.page = FakePage()

        w.launch = fake_launch
        w.navigate("https://example.com/job")
        assert navigated["url"] == "https://example.com/job"
    def test_thread_local_isolation(self):
        """Each thread gets its own launch state (sync-API-in-asyncio fix)."""
        w = BrowserWrapper(headless=True)
        results = {}

        def set_marker(tag):
            w.launch = lambda **kw: None
            w.page = tag
            results[tag] = w.page

        threads = [threading.Thread(target=set_marker, args=(f"t{i}",)) for i in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert results == {"t0": "t0", "t1": "t1"}
        # main thread's TLS is separate and was never launched in THIS test
        assert w.page is None


# ---------- frontend URL resolver (logic mirror in python for the test) ----------

def resolve_job_url(job: dict) -> str:
    for key in ("url", "applyUrl", "apply_url", "link"):
        v = (job or {}).get(key)
        if isinstance(v, str) and v.strip().startswith("http"):
            return v.strip()
    return ""


class TestResolveJobUrl:

    def test_linkedin_link_field(self):
        assert resolve_job_url({"link": "https://linkedin.com/jobs/x", "url": ""}) \
            == "https://linkedin.com/jobs/x"

    def test_empty_url_falls_through(self):
        # the old JS code used ?? which does NOT skip empty strings
        assert resolve_job_url({"url": "", "applyUrl": "https://x/1"}) == "https://x/1"

    def test_whitespace_only_url_skipped(self):
        assert resolve_job_url({"url": "   ", "apply_url": "https://x/2"}) == "https://x/2"

    def test_none_job_safe(self):
        assert resolve_job_url(None) == ""
        assert resolve_job_url({}) == ""

    def test_priority_order(self):
        assert resolve_job_url({"url": "https://a", "applyUrl": "https://b"}) == "https://a"
