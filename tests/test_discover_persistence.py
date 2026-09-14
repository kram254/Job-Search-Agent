"""Regression test: Discover-scraped jobs must land in jobs_raw.json.

Reproduces the user-reported bug: scraping found jobs but the dashboard's
Total Jobs stayed at 25 because the /discover route never persisted results.
The fix makes /discover merge scraped jobs into jobs_raw.json (mirroring what
/scan does via export_to_jobs_raw).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class FakeDigest:
    """Stands in for DailyDigest — returns scraped jobs WITHOUT persisting,
    exactly like the real one (it only writes output/digest_*.json)."""

    def __init__(self, *args, **kwargs):
        pass

    def run(self):
        return {
            "date": "Mon 14 Sep 2026",
            "remoteok_count": 2,
            "linkedin_count": 1,
            "top_jobs": [
                {"title": "AI Engineer", "company": "RemoteCo", "url": "https://remoteok.com/x", "score": 88},
            ],
            "all_jobs": [
                {"title": "AI Engineer", "company": "RemoteCo", "url": "https://remoteok.com/x", "score": 88},
                {"title": "LLM Dev", "company": "PromptCo", "url": "https://remoteok.com/y", "score": 76},
                {"title": "ML Eng", "company": "LinkCo", "url": "https://linkedin.com/z", "score": 71},
            ],
            "saved_to": "/tmp/digest.json",
            "notifications": {"telegram": False, "email": False},
        }


def test_discover_persists_scraped_jobs_to_feed():
    with tempfile.TemporaryDirectory() as td:
        # isolate data dirs so the test never touches real data files
        jobs_path = os.path.join(td, "jobs_raw.json")
        with open(jobs_path, "w") as f:
            json.dump([{"id": "1", "title": "Seed", "company": "SeedCo", "url": "https://seed/1", "score": 50}], f)

        import agent.app as flask_app
        flask_app.JOBS_RAW = __import__("pathlib").Path(jobs_path)
        flask_app.orchestrator = None  # force re-init
        with patch.object(flask_app, "JOBS_RAW", __import__("pathlib").Path(jobs_path)), \
             patch("agent.app.get_orchestrator") as mock_orch:
            orch = MagicMock()
            orch.candidate_profile = {"skills": {"primary": [], "secondary": []}}
            mock_orch.return_value = orch
            with patch("agent.digest.daily_digest.DailyDigest", FakeDigest):
                client = flask_app.app.test_client()
                resp = client.post("/discover", json={"top_n": 1})

        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        # additive response keys present
        assert body["persisted"]["added"] == 3
        assert body["total_in_feed"] == 4

        # THE REGRESSION: scraped jobs now physically in jobs_raw.json
        with open(jobs_path) as f:
            feed = json.load(f)
        urls = {j.get("url") for j in feed}
        assert "https://remoteok.com/x" in urls
        assert "https://remoteok.com/y" in urls
        assert "https://linkedin.com/z" in urls
        assert len(feed) == 4  # 1 seed + 3 scraped

        # new ids continue after the max existing numeric id
        new_ids = [int(j["id"]) for j in feed if j["id"] != "1"]
        assert all(i >= 2 for i in new_ids)


def test_discover_persistence_dedupes_by_url():
    with tempfile.TemporaryDirectory() as td:
        jobs_path = os.path.join(td, "jobs_raw.json")
        with open(jobs_path, "w") as f:
            json.dump([{"id": "1", "title": "Seed", "company": "SeedCo", "url": "https://remoteok.com/x"}], f)

        import agent.app as flask_app
        with patch.object(flask_app, "JOBS_RAW", __import__("pathlib").Path(jobs_path)), \
             patch("agent.app.get_orchestrator") as mock_orch:
            orch = MagicMock()
            orch.candidate_profile = {"skills": {"primary": [], "secondary": []}}
            mock_orch.return_value = orch
            with patch("agent.digest.daily_digest.DailyDigest", FakeDigest):
                client = flask_app.app.test_client()
                resp = client.post("/discover", json={"top_n": 1})

        assert resp.status_code == 200
        body = resp.get_json()
        # 3 scraped, but one url already in feed -> only 2 added
        assert body["persisted"]["added"] == 2
        with open(jobs_path) as f:
            feed = json.load(f)
        assert len(feed) == 3


def test_discover_survives_persistence_failure():
    """If persistence somehow fails, discover's own response is untouched."""
    with tempfile.TemporaryDirectory() as td:
        import agent.app as flask_app
        with patch.object(flask_app, "JOBS_RAW", __import__("pathlib").Path("/nonexistent/dir/jobs_raw.json")), \
             patch("agent.app.get_orchestrator") as mock_orch:
            orch = MagicMock()
            orch.candidate_profile = {"skills": {"primary": [], "secondary": []}}
            mock_orch.return_value = orch
            with patch("agent.digest.daily_digest.DailyDigest", FakeDigest):
                client = flask_app.app.test_client()
                resp = client.post("/discover", json={"top_n": 1})

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["remoteok_count"] == 2  # discovery result intact
        assert body["persisted"]["added"] == 0  # persistence no-opped safely
