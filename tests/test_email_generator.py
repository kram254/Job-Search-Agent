from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.outreach.email_generator import EmailGenerator, _pick_proof_points, _build_prompt

PROFILE = {
    "personal_details": {"name": "EMMANUEL M NDALIRO", "email": "markorlando45@gmail.com"},
    "professional_profiles": {
        "linkedin": "https://www.linkedin.com/in/mark-imanuel-501771124/",
        "github": "https://github.com/kram254/",
    },
    "narrative": {
        "professional_summary": "AI/ML engineer specialising in agentic systems, LLMOps, and production-grade RAG architectures.",
        "exit_story": "Moving deeper on the infrastructure layer.",
        "positioning": "The engineer who bridges prototype and production in agentic AI",
    },
    "proof_points": [
        {"metric": "90% reduction in manual processing time", "context": "multi-agent workflow automation", "archetype": "agentic_automation"},
        {"metric": "p95 latency reduced from 2s to 380ms", "context": "LLM inference optimization with caching", "archetype": "ai_platform_llmops"},
        {"metric": "Shipped AI POC in 2 weeks", "context": "rapid prototyping for enterprise client", "archetype": "ai_forward_deployed"},
    ],
    "projects": ["Multi-agent RAG pipeline with HITL", "LLMOps monitoring dashboard"],
}

JOB_META = {
    "title": "Senior Backend Engineer – Build AI Agents",
    "company": "Salesforge",
    "description": (
        "At Salesforge, we're creating autonomous AI agents that can find prospects, "
        "generate highly personalized outreach, run conversations, and book meetings "
        "without human involvement. You will design and ship multi-agent pipelines "
        "that operate at scale. Strong Python or Golang required. Experience with LLM "
        "orchestration, agent frameworks, and agentic AI systems is essential."
    ),
    "location": "Remote – Worldwide",
    "url": "https://remoteok.com/remote-jobs/remote-senior-backend-engineer-build-ai-agents-salesforge-1131292",
    "date_posted": "2026-04-23",
}

CONTACT = {
    "name": "Alex Rivera",
    "email": "alex@salesforge.ai",
    "title": "Head of Engineering",
    "confidence": 85,
    "domain": "salesforge.ai",
}

EVALUATION = {
    "archetype": "agentic_automation",
    "matched_skills": ["python", "langchain", "fastapi", "docker"],
    "missing_skills": ["go"],
    "quality_gate": {"final_score": 90, "passes": True, "total_penalty": 10},
}

INTEL = {
    "stack": ["python", "langchain", "fastapi", "docker", "kubernetes"],
    "seniority_years": None,
    "location_type": "fully_remote",
    "salary_range": None,
    "urgency": "normal",
}


def test_proof_point_selection():
    pts = _pick_proof_points(PROFILE, "agentic_automation")
    assert len(pts) > 0
    assert any("multi-agent" in p["context"] for p in pts)
    print("  proof point selection: PASS")


def test_prompt_building():
    prompt = _build_prompt(
        profile=PROFILE,
        job_meta=JOB_META,
        contact=CONTACT,
        archetype="agentic_automation",
        matched_skills=["python", "langchain"],
        missing_skills=["go"],
        quality_score=90,
    )
    assert "Salesforge" in prompt
    assert "90% reduction" in prompt
    assert "Alex Rivera" in prompt or "Hi Alex," in prompt or "Alex" in prompt
    assert "agentic_automation" in prompt
    print("  prompt building: PASS")


def test_parse_response_with_subject():
    gen = EmailGenerator(llm_client=None)
    raw = """SUBJECT: Agentic systems engineer – interested in the Salesforge role

Hi Alex,

I build autonomous AI agents for a living — multi-agent orchestration, RAG pipelines, production inference. Cut manual workflow time by 90% on my last project.

I saw Salesforge is building agents that find, qualify, and close without human intervention. That's exactly the problem space I'm in.

Open for a 20-minute call this week?

Emmanuel Ndaliro
https://github.com/kram254/
"""
    subject, body = gen._parse_response(raw)
    assert "Salesforge" in subject or "Agentic" in subject
    assert "Hi Alex" in body
    assert "Emmanuel" in body
    word_count = len(body.split())
    assert word_count <= 175, f"Body too long: {word_count} words"
    print(f"  parse response: PASS  subject='{subject}'  words={word_count}")


def test_generate_without_llm():
    gen = EmailGenerator(llm_client=None)
    result = gen.generate(profile=PROFILE, job_meta=JOB_META, contact=CONTACT)
    assert "subject" in result
    assert "body" in result
    assert result["archetype"] == "agentic_automation"
    print(f"  generate (no LLM): PASS  subject='{result['subject']}'")


def run_all():
    print("\n=== Email Generator Tests ===")
    test_proof_point_selection()
    test_prompt_building()
    test_parse_response_with_subject()
    test_generate_without_llm()
    print("=== ALL TESTS PASSED ===\n")


if __name__ == "__main__":
    run_all()
