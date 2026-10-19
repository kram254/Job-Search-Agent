"""Tests for the Oct 19 fixes: description sanitization, discover ID sync,
and the LinkedIn detail-budget (worker timeout fix)."""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.app import sanitize_job_description


class TestSanitizeJobDescription:

    def test_strips_html_tags_to_readable_text(self):
        raw = "<p><strong>About the Role:</strong></p><p>Deliver fun lessons.</p><ul><li>Teach Python</li><li>Grade fast</li></ul>"
        out = sanitize_job_description(raw)
        assert "<" not in out and ">" not in out
        assert "About the Role:" in out
        assert "- Teach Python" in out
        assert "Grade fast" in out

    def test_fixes_mojibake(self):
        raw = "Are youÃ¢ a passionate programmerÃÂ who loves codingÃ¢ and games?"
        out = sanitize_job_description(raw)
        assert "Ã" not in out and "Â" not in out
        assert "Are you" in out and "passionate programmer" in out

    def test_decodes_entities(self):
        out = sanitize_job_description("Java &amp; Python &lt;senior&gt; &nbsp; role")
        assert "Java & Python" in out
        assert "<senior>" in out
        assert "&amp;" not in out

    def test_preserves_line_structure(self):
        raw = "<p>Line one.</p><p>Line two.</p>"
        out = sanitize_job_description(raw)
        assert "Line one." in out.split("\n")
        assert "Line two." in out.split("\n")

    def test_removes_inline_styles(self):
        raw = '<p style="min-height: 1.7em;">styled text</p>'
        out = sanitize_job_description(raw)
        assert "min-height" not in out
        assert "styled text" in out

    def test_empty_and_none_safe(self):
        assert sanitize_job_description("") == ""
        assert sanitize_job_description(None) == ""


class TestDiscoverIdSync:
    """The 404 fix: scraped job ids must survive into the feed so Discover
    page links resolve."""

    def _fake_result(self):
        return {
            "date": "x", "remoteok_count": 1, "linkedin_count": 0,
            "top_jobs": [{
                "id": "1137534", "title": "APAC Python", "company": "Kodland",
                "url": "https://remoteok.com/l/1137534", "score": 92,
            }],
            "all_jobs": [{
                "id": "1137534", "title": "APAC Python", "company": "Kodland",
                "url": "https://remoteok.com/l/1137534", "score": 92,
                "description": "<p>Teach Python</p>",
            }],
            "saved_to": "/tmp/d.json", "notifications": {},
        }

    def test_scraped_id_persists_as_feed_id(self, tmp_path, monkeypatch):
        import agent.app as flask_app
        from pathlib import Path
        jobs_path = tmp_path / "jobs_raw.json"
        jobs_path.write_text(json.dumps([
            {"id": "4380364969", "title": "Seed", "url": "https://seed/1"}
        ]))
        monkeypatch.setattr(flask_app, "JOBS_RAW", jobs_path)
        with patch("agent.app.get_orchestrator") as mo:
            orch = mo.return_value
            orch.candidate_profile = {"skills": {"primary": [], "secondary": []}}
            with patch("agent.digest.daily_digest.DailyDigest") as MD:
                MD.return_value.run.return_value = self._fake_result()
                client = flask_app.app.test_client()
                resp = client.post("/discover", json={"top_n": 1})
        assert resp.status_code == 200
        body = resp.get_json()
        # the top_job's id must be the feed id so the Details link resolves
        assert body["top_jobs"][0]["id"] == "1137534"
        assert body["top_jobs"][0]["in_feed"] is True
        feed = json.loads(jobs_path.read_text())
        assert feed[-1]["id"] == "1137534"
        # description was sanitized on the way in
        assert "<p>" not in feed[-1]["description"]

    def test_existing_job_annotated_with_feed_id(self, tmp_path, monkeypatch):
        """Second discovery of the same job: link must point at the EXISTING id."""
        import agent.app as flask_app
        jobs_path = tmp_path / "jobs_raw.json"
        jobs_path.write_text(json.dumps([
            {"id": "999888777", "title": "APAC Python", "url": "https://remoteok.com/l/1137534"}
        ]))
        monkeypatch.setattr(flask_app, "JOBS_RAW", jobs_path)
        with patch("agent.app.get_orchestrator") as mo:
            mo.return_value.candidate_profile = {"skills": {"primary": [], "secondary": []}}
            with patch("agent.digest.daily_digest.DailyDigest") as MD:
                MD.return_value.run.return_value = self._fake_result()
                client = flask_app.app.test_client()
                resp = client.post("/discover", json={"top_n": 1})
        body = resp.get_json()
        assert body["persisted"]["added"] == 0
        assert body["top_jobs"][0]["id"] == "999888777"  # the feed's id
        assert body["top_jobs"][0]["in_feed"] is True


class TestLinkedInDetailBudget:

    def test_default_budget_caps_expensive_path(self):
        from agent.scraper.linkedin_scraper import fetch_linkedin
        import agent.scraper.linkedin_scraper as mod
        # monkeypatch network + scoring to count calls
        calls = {"detail": 0}
        monkey = pytest.MonkeyPatch()
        monkey.setattr(mod, "_HEADERS", {})
        monkey.setattr(mod.requests, "get", lambda *a, **k: _fake_search_response())
        monkey.setattr(mod, "_fetch_detail", lambda job_id: calls.__setitem__("detail", calls["detail"] + 1) or "desc")
        monkey.setattr(mod, "_handle_score_job_fit", lambda p: {"quality_gate": {"final_score": 80, "passes": True}, "match_ratio": 0.5, "matched_skills": []})
        monkey.setattr(mod, "_handle_extract_lead_intel", lambda p: {})
        try:
            fetch_linkedin(keywords="x", max_pages=1, max_detail_fetches=2)
        finally:
            monkey.undo()
        assert calls["detail"] == 2, "detail budget not enforced"

    def test_env_var_sets_budget(self, monkeypatch):
        monkeypatch.setenv("LINKEDIN_MAX_DETAILS", "3")
        from agent.scraper.linkedin_scraper import fetch_linkedin
        import agent.scraper.linkedin_scraper as mod
        calls = {"detail": 0}
        monkeypatch.setattr(mod, "_HEADERS", {})
        monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _fake_search_response())
        monkeypatch.setattr(mod, "_fetch_detail", lambda job_id: calls.__setitem__("detail", calls["detail"] + 1) or "desc")
        monkeypatch.setattr(mod, "_handle_score_job_fit", lambda p: {"quality_gate": {"final_score": 80, "passes": True}, "match_ratio": 0.5, "matched_skills": []})
        monkeypatch.setattr(mod, "_handle_extract_lead_intel", lambda p: {})
        fetch_linkedin(keywords="x", max_pages=1)
        assert calls["detail"] == 3


def _fake_search_response():
    """Minimal fake LinkedIn search page with 5 job cards."""
    cards = "".join(
        f'data-entity-urn="urn:li:jobPosting:11111{i}"'
        f'<div class="base-search-card">Job {i}</div>'
        for i in range(5)
    )
    resp = type("R", (), {})()
    resp.status_code = 200
    resp.text = f"<html>{cards}</html>"
    return resp
