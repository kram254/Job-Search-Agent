"""Tests for the JobRight-parity additive modules (Phases 1-5).

New test file only — no existing tests are modified.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from agent.ranking.match_explainer import MatchExplainer, explain_match
from agent.analytics.insights_builder import InsightsBuilder, build_insights
from agent.alerts.alert_engine import AlertEngine


PROFILE = {
    "personal_details": {"name": "Test Candidate"},
    "skills": {"primary": ["Python", "LLMs", "RAG", "Flask"], "secondary": ["Docker"]},
    "education": [{"degree": "BSc Software Engineering", "institution": "Test University", "years": "2015-2019"}],
    "narrative": {"professional_summary": "Engineer with 5 years of experience building AI systems."},
}

JOB = {
    "id": "j1",
    "title": "Senior AI Engineer",
    "companyName": "TestCo",
    "description": "We need 5+ years of experience with Python, LLMs and RAG pipelines. "
                   "Experience with React and Kubernetes is a plus. 5 years experience required.",
    "seniorityLevel": "Senior",
    "score": 82,
}


# ---------- Phase 1: match explainer ----------

class TestMatchExplainer:

    def test_explain_returns_all_sections(self):
        result = explain_match(PROFILE, JOB)
        for key in ("skills", "experience", "seniority", "areas_to_review", "highlights", "summary"):
            assert key in result

    def test_matched_skills_detected(self):
        result = explain_match(PROFILE, JOB)
        assert "python" in result["skills"]["matched"]
        assert "llm" in result["skills"]["matched"]
        assert "rag" in result["skills"]["matched"]

    def test_missing_skills_detected(self):
        result = explain_match(PROFILE, JOB)
        assert "react" in result["skills"]["missing"]
        assert "kubernetes" in result["skills"]["missing"]

    def test_no_substring_false_positives(self):
        # "angular" must not match "rectangular", "c" must not match every word
        tricky_job = dict(JOB, description="Work on rectangular widgets and the c standard. c++ a plus.")
        result = explain_match(PROFILE, tricky_job)
        assert "angular" not in result["skills"]["matched"]

    def test_experience_comparison(self):
        result = explain_match(PROFILE, JOB)
        assert result["experience"]["jd_years"] == 5
        assert result["experience"]["candidate_years"] == 5
        assert result["experience"]["status"] == "meets"

    def test_base_score_preserved_not_rescored(self):
        result = explain_match(PROFILE, JOB, base_score=82)
        assert result["base_score"] == 82


# ---------- Phase 1: insights builder ----------

class TestInsightsBuilder:

    def test_build_returns_all_sections(self):
        result = build_insights(PROFILE, [JOB], applications=[])
        for key in ("profile", "market", "alignment", "application_funnel", "recommendations"):
            assert key in result

    def test_demand_counts_use_word_boundaries(self):
        jobs = [
            dict(JOB),
            dict(JOB, description="Rectangular UI with catastrophic failure modes."),
        ]
        result = build_insights(PROFILE, jobs)
        skills = [d["skill"] for d in result["market"]["top_demand_skills"]]
        assert "angular" not in skills  # would match "rectangular" without boundaries

    def test_demand_flags_missing_profile_skills(self):
        jobs = [dict(JOB, description="Need python and kubernetes and react experience.")]
        result = build_insights(PROFILE, jobs)
        assert "kubernetes" in result["alignment"]["skills_to_consider"]

    def test_empty_feed_produces_safe_recommendation(self):
        result = build_insights(PROFILE, [])
        assert any("scan" in r.lower() for r in result["recommendations"])


# ---------- Phase 2: copilot ----------

class FakeLLM:
    def complete_for_step(self, step, prompt, system="", max_tokens=0, temperature=0.0):
        return "Here is my advice.\nACTION: scan | Run a job scan"


class TestCareerCopilot:

    def _copilot(self, history_dir):
        from agent.copilot.career_copilot import CareerCopilot
        return CareerCopilot(FakeLLM(), history_dir=history_dir)

    def test_chat_roundtrip_persists_history(self):
        with tempfile.TemporaryDirectory() as td:
            copilot = self._copilot(td)
            result = copilot.chat("what should I do?", conversation_id="t1",
                                  candidate_profile=PROFILE, jobs=[JOB], applications=[])
            assert result["reply"].startswith("Here is my advice")
            assert result["actions"] == [{"action_key": "scan", "label": "Run a job scan"}]
            history = copilot.load_history("t1")
            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[1]["role"] == "assistant"

    def test_action_lines_stripped_from_reply(self):
        with tempfile.TemporaryDirectory() as td:
            copilot = self._copilot(td)
            result = copilot.chat("hi", conversation_id="t2", candidate_profile=PROFILE)
            assert "ACTION:" not in result["reply"]

    def test_invalid_action_key_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            from agent.copilot.career_copilot import CareerCopilot

            class BadLLM(FakeLLM):
                def complete_for_step(self, *a, **k):
                    return "text\nACTION: delete_everything | nope"

            copilot = CareerCopilot(BadLLM(), history_dir=td)
            result = copilot.chat("hi", conversation_id="t3", candidate_profile=PROFILE)
            assert result["actions"] == []

    def test_context_pack_contains_live_data(self):
        with tempfile.TemporaryDirectory() as td:
            copilot = self._copilot(td)
            pack = copilot.build_context_pack(PROFILE, [JOB], [{"title": "X", "company": "Y", "status": "submitted"}])
            assert "TestCo" in pack
            assert "submitted" in pack


# ---------- Phase 3: alert engine ----------

class TestAlertEngine:

    def _engine(self, td):
        return AlertEngine(alerts_path=os.path.join(td, "alerts.json"), score_threshold=75)

    def test_alert_created_for_new_high_match(self):
        with tempfile.TemporaryDirectory() as td:
            engine = self._engine(td)
            alerts = engine.evaluate_scan_results([
                {"title": "AI Eng", "company": "Co", "url": "https://x/1", "score": 90}
            ])
            assert len(alerts) == 1
            assert alerts[0]["score"] == 90
            assert engine.unread_count() == 1

    def test_no_alert_below_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            engine = self._engine(td)
            alerts = engine.evaluate_scan_results([
                {"title": "Low", "company": "Co", "url": "https://x/2", "score": 60}
            ])
            assert alerts == []

    def test_duplicate_url_not_re_alerted(self):
        with tempfile.TemporaryDirectory() as td:
            engine = self._engine(td)
            listing = [{"title": "AI Eng", "company": "Co", "url": "https://x/1", "score": 90}]
            assert len(engine.evaluate_scan_results(listing)) == 1
            assert engine.evaluate_scan_results(listing) == []

    def test_mark_read_and_unread_count(self):
        with tempfile.TemporaryDirectory() as td:
            engine = self._engine(td)
            alerts = engine.evaluate_scan_results([
                {"title": "A", "company": "C", "url": "https://x/9", "score": 95}
            ])
            engine.mark_read(alerts[0]["id"])
            assert engine.unread_count() == 0


# ---------- Phase 4: resume parser (merge proposal only — no LLM) ----------

class TestResumeParserMerge:

    def _parser(self, td, profile):
        from agent.services.resume_parser import ResumeParser
        path = os.path.join(td, "profile.json")
        with open(path, "w") as f:
            json.dump(profile, f)
        return ResumeParser(llm_client=None, profile_path=path), path

    def test_propose_merge_detects_skill_changes(self):
        with tempfile.TemporaryDirectory() as td:
            parser, path = self._parser(td, PROFILE)
            parsed = {"skills": {"primary": ["Python", "FastAPI"]}}
            proposal = parser.propose_merge(parsed)
            assert proposal["change_count"] == 1
            change = proposal["changes"][0]
            assert change["key"] == "skills.primary"
            assert change["added"] == ["FastAPI"]
            assert change["removed"] == ["LLMs", "RAG", "Flask"]

    def test_propose_merge_ignores_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            parser, path = self._parser(td, PROFILE)
            proposal = parser.propose_merge({"skills": {"primary": PROFILE["skills"]["primary"]}})
            assert proposal["change_count"] == 0

    def test_apply_merge_writes_backup_and_fills_missing_only(self):
        with tempfile.TemporaryDirectory() as td:
            parser, path = self._parser(td, PROFILE)
            profile_with_phone = dict(PROFILE)
            parsed = {"personal_details": {"name": "Test Candidate", "phone": "+254700000000"}}
            result = parser.apply_merge(parsed, change_keys=["personal_details"])
            assert "personal_details" in result["applied"]
            assert os.path.exists(result["backup_path"])
            with open(path) as f:
                merged = json.load(f)
            # fill-only: existing name untouched, phone added
            assert merged["personal_details"]["name"] == "Test Candidate"
            assert merged["personal_details"]["phone"] == "+254700000000"

    def test_rejects_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as td:
            from agent.services.resume_parser import ResumeParser, ResumeParseError
            parser = ResumeParser(llm_client=None, profile_path=os.path.join(td, "p.json"))
            with pytest.raises(ResumeParseError):
                parser.extract_text("/tmp/x.exe", "x.exe")


# ---------- Phase 5: interviews + insiders ----------

class TestInterviews:

    def test_add_list_update_interview(self):
        from agent.tracker.followup_tracker import FollowUpTracker
        with tempfile.TemporaryDirectory() as td:
            tracker = FollowUpTracker(storage_path=os.path.join(td, "f.json"))
            iv = tracker.add_interview("j9", "Co", "Eng", "2026-12-01T10:00:00", "technical")
            assert iv["record_type"] == "interview"
            assert len(tracker.get_interviews()) == 1
            assert tracker.update_interview_status(iv["id"], "completed")
            assert not tracker.update_interview_status(iv["id"], "bogus")
            # follow-up records and interview records coexist
            tracker.track(job_id="j10", company="C", title="T")
            assert len(tracker.get_interviews()) == 1
            assert len(tracker.all_active()) == 1


class TestInsiderLinks:

    def test_build_insider_search_links(self):
        from agent.outreach.contact_lookup import ContactLookup
        links = ContactLookup.build_insider_search_links(
            "TestCo", [{"institution": "Test University", "years": "2015-2019"}]
        )
        assert "linkedin.com/search" in links["hiring_managers"]
        assert len(links["alumni"]) == 1
        assert "Test%20University" in links["alumni"][0]["url"]

    def test_find_insiders_degrades_without_api_key(self):
        from agent.outreach.contact_lookup import ContactLookup
        result = ContactLookup(api_key="").find_insiders("TestCo")
        assert result["hunter_configured"] is False
        assert result["contacts"] == []
        assert "search_links" in result
