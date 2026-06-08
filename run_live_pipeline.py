from __future__ import annotations

import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent.ranking.quality_gate import QualityGate
from agent.ranking.feedback_ranker import FeedbackRanker
from agent.mcp_server import (
    _handle_score_job_fit,
    _handle_evaluate_lead_quality,
    _handle_extract_lead_intel,
)
from agent.outreach.email_generator import EmailGenerator, _build_prompt, _EMAIL_SYSTEM

JOB_URL = "https://remoteok.com/remote-jobs/remote-senior-backend-engineer-build-ai-agents-salesforge-1131292"

JOB_META = {
    "id":          "salesforge-ai-agents-001",
    "title":       "Senior Backend Engineer – Build AI Agents",
    "company":     "Salesforge",
    "location":    "Remote – Worldwide",
    "url":         JOB_URL,
    "source":      "remoteok",
    "date_posted": "2026-04-23",
    "description": textwrap.dedent("""
        Senior Backend Engineer – Build AI Agents at Salesforge
        Remote – Worldwide · Full-time · Posted April 2026

        Most sales tools help you send emails. We're building something different.
        At Salesforge, we're creating autonomous AI agents that can:
        - Find the right prospects
        - Generate highly personalized outreach
        - Run conversations
        - And book meetings
        All without human involvement.

        What you'll do:
        - Design and implement multi-agent orchestration systems that operate at scale
        - Build reliable, fault-tolerant backend services powering agent workflows
        - Work closely with ML engineers on prompt pipelines and LLM integration
        - Own the full backend lifecycle from architecture to production deployment
        - Improve agent reasoning, tool use, and memory systems over time

        Requirements:
        - 4+ years of backend engineering experience with Python or Golang
        - Experience designing autonomous or agentic AI systems
        - Familiarity with LLM orchestration frameworks (LangChain, LlamaIndex, or similar)
        - Strong grasp of distributed systems, message queues, and async processing
        - Experience with Docker, Kubernetes, and cloud infra (AWS/GCP)
        - Comfort owning systems end-to-end, from design to on-call

        Nice to have:
        - Prior work on multi-agent frameworks (A2A, CrewAI, AutoGen)
        - Experience with RAG pipelines and vector databases
        - Background in sales tech or outbound automation

        Compensation: equity + competitive salary (undisclosed, estimated $80–150k)
        Benefits: unlimited PTO, async-first, distributed team, learning budget
    """).strip(),
}

CANDIDATE_PROFILE = json.load(open("data/candidate_profile.json"))

CONTACT = {
    "name":       "hiring team",
    "email":      "jobs@salesforge.ai",
    "title":      "Hiring",
    "confidence": 0,
    "domain":     "salesforge.ai",
    "note":       "Hunter.io lookup skipped (no API key in env) — using fallback",
}


def separator(title: str = ""):
    width = 70
    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "─" * pad + f" {title} " + "─" * pad)
    else:
        print("\n" + "─" * width)


def run():
    print("\n" + "═" * 70)
    print("  LIVE PIPELINE RUN – Salesforge AI Agents Engineer")
    print("  " + JOB_URL)
    print("═" * 70)

    separator("1. QUALITY GATE")
    gate = QualityGate()
    gate_result = gate.evaluate(JOB_META)
    print(f"  Base score  : {gate_result['base_score']}")
    print(f"  Final score : {gate_result['final_score']}")
    print(f"  Total penalty: {gate_result['total_penalty']}")
    print(f"  Verdict     : {'✅ PASS' if gate_result['passes'] else '❌ FAIL'}")
    if gate_result["penalties"]:
        for p in gate_result["penalties"]:
            print(f"    penalty  : {p['reason']}  –{p['penalty']}")

    separator("2. EXTRACT LEAD INTEL (MCP)")
    intel = _handle_extract_lead_intel({"job_description": JOB_META["description"]})
    print(f"  Stack detected   : {intel['stack']}")
    print(f"  Seniority years  : {intel['seniority_years']}")
    print(f"  Location type    : {intel['location_type']}")
    print(f"  Salary signal    : {intel['salary_range']}")
    print(f"  Urgency          : {intel['urgency']}")

    separator("3. SCORE JOB FIT (MCP)")
    candidate_skills = (
        CANDIDATE_PROFILE.get("skills", {}).get("primary", []) +
        CANDIDATE_PROFILE.get("skills", {}).get("secondary", [])
    )
    fit = _handle_score_job_fit({
        "job_description": JOB_META["description"],
        "candidate_skills": candidate_skills,
        "title": JOB_META["title"],
    })
    print(f"  JD stack         : {fit['jd_stack']}")
    print(f"  Candidate skills : {fit['candidate_skills']}")
    print(f"  Matched          : {fit['matched_skills']}")
    print(f"  Missing          : {fit['missing_skills']}")
    print(f"  Match ratio      : {fit['match_ratio']:.0%}")
    qg = fit.get("quality_gate", {})
    print(f"  QG verdict       : {'✅ PASS' if qg.get('passes') else '❌ FAIL'}  (score {qg.get('final_score','?')})")

    separator("4. EVALUATE LEAD QUALITY (MCP)")
    lead = _handle_evaluate_lead_quality({"listing": JOB_META})
    print(f"  Quality gate     : {lead['quality_gate'].get('final_score')} / 100")
    print(f"  Feedback delta   : {lead['feedback_delta']:+.3f}  (no prior signals)")
    print(f"  Adjusted score   : {lead['adjusted_score']}")
    print(f"  Verdict          : {'✅ PASS' if lead['verdict'] == 'PASS' else '❌ FAIL'}")

    separator("5. CONTACT LOOKUP")
    hunter_key = os.environ.get("HUNTER_API_KEY", "")
    if hunter_key:
        from agent.outreach.contact_lookup import ContactLookup
        lookup = ContactLookup(api_key=hunter_key)
        found = lookup.lookup("salesforge.ai")
        if found:
            CONTACT.update(found)
            CONTACT.pop("note", None)
            print(f"  Found   : {found['name']} – {found['title']}")
            print(f"  Email   : {found['email']}")
            print(f"  Confidence: {found['confidence']}%")
        else:
            print("  No contact found via Hunter.io")
    else:
        print(f"  Skipped – HUNTER_API_KEY not set")
        print(f"  Contact : {CONTACT['note']}")

    separator("6. EMAIL GENERATION")
    evaluation_ctx = {
        "archetype":      "agentic_automation",
        "matched_skills": fit["matched_skills"],
        "missing_skills": fit["missing_skills"],
        "quality_gate":   gate_result,
    }

    llm_available = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GEMINI_API_KEY")
    )

    gen = EmailGenerator()
    result = gen.generate(
        profile=CANDIDATE_PROFILE,
        job_meta=JOB_META,
        contact=CONTACT,
        evaluation=evaluation_ctx,
        intel=intel,
    )

    if not result["body"] or result["body"].startswith("["):
        print("  LLM API blocked in sandbox – showing constructed prompt + hand-composed email\n")
        prompt = _build_prompt(
            profile=CANDIDATE_PROFILE,
            job_meta=JOB_META,
            contact=CONTACT,
            archetype="agentic_automation",
            matched_skills=fit["matched_skills"],
            missing_skills=fit["missing_skills"],
            quality_score=gate_result["final_score"],
        )
        print("  ── PROMPT THAT WILL BE SENT TO LLM AT RUNTIME ──")
        for line in prompt.splitlines():
            print("  " + line)

        simulated_body = textwrap.dedent("""
            Hi,

            Your agent infrastructure caught my attention — specifically the goal of end-to-end autonomy without human checkpoints at each step. That's the hard part I've been building toward.

            I cut manual processing time by 90% on a multi-agent orchestration project (Python + LangChain), and brought p95 LLM inference latency from 2 s down to 380 ms through caching and batching. Both are in production.

            Would a 20-minute call this week or next work to talk about the agent architecture challenges you're solving?

            Emmanuel Ndaliro
            https://github.com/kram254/
            https://www.linkedin.com/in/mark-imanuel-501771124/
        """).strip()

        result = {
            "subject":        "Agentic engineer – interested in the AI Agents backend role at Salesforge",
            "body":           simulated_body,
            "contact":        CONTACT,
            "word_count":     len(simulated_body.split()),
            "archetype":      "agentic_automation",
            "matched_skills": fit["matched_skills"],
            "simulated":      True,
        }

    print("\n  ── FINAL EMAIL ──\n")
    print(f"  TO      : {result['contact'].get('email', 'jobs@salesforge.ai')}")
    print(f"  SUBJECT : {result['subject']}")
    print(f"  WORDS   : {result['word_count']}")
    print(f"  ARCHETYPE: {result['archetype']}")
    print()
    for line in result["body"].splitlines():
        print("  " + line)

    separator("SUMMARY")
    print(f"  Job         : {JOB_META['title']} @ {JOB_META['company']}")
    print(f"  URL         : {JOB_URL}")
    print(f"  Quality     : {gate_result['final_score']}/100  ({gate_result['total_penalty']} penalty pts)")
    print(f"  Skill match : {fit['match_ratio']:.0%}  ({len(fit['matched_skills'])}/{len(fit['jd_stack'])} skills)")
    print(f"  Archetype   : {evaluation_ctx['archetype']}")
    print(f"  Email ready : {'✅ LLM-generated' if not result.get('simulated') else '⚡ Hand-composed template (LLM generates at runtime with API key)'}")
    print()


if __name__ == "__main__":
    run()
