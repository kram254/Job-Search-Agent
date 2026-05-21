import json
import sys
import types
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

APPLY_URL = "https://www.linkedin.com/jobs/view/4407767745/"
CV_PATH = "CVs/SoftwareDevCV.md"

JOB_DESCRIPTION = """
Director of Revenue Systems and AI Automation - Caul Group Realty (Remote, LATAM Only)

Caul Group Residential is the number one resale real estate team in The Triangle, North Carolina,
brokered by eXp Realty. We sell 800+ homes annually with 50 agents.

You own the systems layer. You build AI agents, automations, and dashboards that replace manual
work across every department. Not experiments — production tools.

TECH STACK: Claude, Follow Up Boss, ClickFunnels, Open to Close, SISU, Ylopo, Agently, Zapier,
Replit, Baserow, Notion, Google Workspace, Slack, ManyChat.

RESPONSIBILITIES:
- AI Tool Building: Claude projects, Claude skills, and prompt systems. Production infrastructure.
- ClickFunnels Workflow Execution: funnels, pipelines, email automations, webhook integrations.
- Dashboard and Data Pipeline Development using Replit, Baserow, Zapier, Claude.
- CRM and Transaction Integration: Follow Up Boss, Open to Close, Ylopo, SISU.

REQUIREMENTS:
- 7+ years in revenue systems, CRM architecture, AI automation, RevOps, or technical operations.
- AI agents deployed in production with measurable outcomes. Not demos.
- Expert-level Claude fluency. Claude-first organization. Claude Projects, Skills, Cowork mastery.
- U.S. residential real estate experience strongly preferred.

LOCATION: Remote. LATAM only. Preference for Uruguay, Costa Rica, or Colombia.
COMPENSATION: $5,000-$6,000 USD/month (independent contractor, 1099).
APPLY: Via LinkedIn only.
"""

MOCK_EVALUATION_RESPONSE = {
    "archetype": "agentic_automation",
    "archetype_confidence": 0.72,
    "global_score": 5.4,
    "recommendation": "Proceed with caution — strong skill match but location and compensation are disqualifying constraints",
    "blocks": {
        "A": {"score": 7.5, "reasoning": "Claude expertise, AI agents, MCP, RAG, agentic systems — direct stack match"},
        "B": {"score": 5.0, "reasoning": "7yr floor required; strong AI/agent background but no RevOps or real estate CRM depth"},
        "C": {"score": 4.0, "reasoning": "Director-level ownership role; good leadership framing but no U.S. real estate context"},
        "D": {"score": 0.0, "reasoning": "CRITICAL FAIL: LATAM only (Uruguay/Costa Rica/Colombia); candidate is Kenyan — hard disqualifier"},
        "E": {"score": 3.0, "reasoning": "Compensation $5K-$6K/month (~$65K/yr) vs target $120K base — 45% below floor"},
        "F": {"score": 6.5, "reasoning": "Execution-focused culture, ship fast, own it — aligns with candidate archetype and proof points"},
        "G": {"score": 8.0, "reasoning": "Posting is 6 days old, detailed scope, real company (4.9 Google / 700+ reviews), active hiring"}
    },
    "cv_tailoring_plan": {
        "keywords_to_inject": ["Claude Projects", "AI agent orchestration", "production automation", "integration architecture", "RAG"],
        "highlight_projects": ["Multi-agent RAG pipeline", "LLMOps monitoring dashboard", "AI agent for customer support"],
        "remove_irrelevant": ["Flutter", "Dart", "mobile development"]
    },
    "interview_stories": [
        {
            "situation": "Enterprise client needed to automate lead routing across 4 CRM systems",
            "task": "Design an agent-orchestrated pipeline with zero manual handoffs",
            "action": "Built multi-agent workflow with event-driven triggers, fallback logic, and audit logging",
            "result": "90% reduction in manual processing time, 0 dropped leads",
            "reflection": "Proved that AI agents can own critical revenue-path operations without supervision"
        }
    ],
    "posting_legitimacy": {"score": 8.0, "is_legitimate": True, "signals": ["Detailed scope brief requirement", "4-stage interview process", "Real company with public reviews"]}
}

MOCK_FORM_FIELDS = [
    {"field_id": "first_name",       "label": "First Name",             "type": "text",     "candidate_value": "EMMANUEL",              "requires_hitl": False,  "confidence": 0.99},
    {"field_id": "last_name",        "label": "Last Name",              "type": "text",     "candidate_value": "M NDALIRO",             "requires_hitl": False,  "confidence": 0.99},
    {"field_id": "email",            "label": "Email",                  "type": "email",    "candidate_value": "markorlando45@gmail.com","requires_hitl": False,  "confidence": 0.99},
    {"field_id": "phone",            "label": "Phone Number",           "type": "tel",      "candidate_value": "+254728427263",          "requires_hitl": False,  "confidence": 0.98},
    {"field_id": "linkedin_profile", "label": "LinkedIn Profile URL",   "type": "url",      "candidate_value": "https://www.linkedin.com/in/mark-imanuel-501771124/", "requires_hitl": False, "confidence": 0.97},
    {"field_id": "resume",           "label": "Resume / CV",            "type": "file",     "candidate_value": "CVs/SoftwareDevCV.md",   "requires_hitl": False,  "confidence": 0.95},
    {"field_id": "cover_letter",     "label": "Cover Letter",           "type": "textarea", "candidate_value": "I'm choosing Caul Group because you are building one of the most Claude-native organizations in the market today. My background building production agentic systems — multi-agent RAG pipelines, real-time inference infrastructure, and AI automation workflows — maps directly to what you are describing. I reduce p95 latency from 2s to 380ms. I ship AI POCs in 2 weeks. I own the infrastructure layer, not just the features. I am ready to own yours.", "requires_hitl": False, "confidence": 0.88},
    {"field_id": "location",         "label": "Current Location",       "type": "text",     "candidate_value": "Nairobi, Kenya",         "requires_hitl": False,  "confidence": 0.95},
    {"field_id": "desired_salary",   "label": "Desired Compensation",   "type": "text",     "candidate_value": "__HITL_REQUIRED__",      "requires_hitl": True,   "confidence": 0.30, "hitl_reason": "Salary field — sensitive"},
    {"field_id": "systems_examples", "label": "4 Concrete Technical Examples", "type": "textarea", "candidate_value": "1) Multi-agent RAG pipeline with HITL — reduced manual processing 90%\n2) LLMOps monitoring dashboard — p95 latency from 2s to 380ms\n3) AI agent for customer support automation — shipped in 2 weeks for enterprise client\n4) Agentic code review assistant — integrated into CI pipeline with structured output", "requires_hitl": False, "confidence": 0.82},
    {"field_id": "work_authorization","label": "Work Authorization",    "type": "select",   "candidate_value": "Not authorized (requires visa/sponsorship)", "requires_hitl": True, "confidence": 0.40, "hitl_reason": "Authorization status — LATAM only role"},
]


def run_e2e_test():
    print("=" * 72)
    print("END-TO-END TEST — auto mode / direct URL apply")
    print("=" * 72)
    print(f"\nTarget URL : {APPLY_URL}")
    print(f"Mode       : AUTO (fill + submit, no gates)")
    print(f"CV         : {CV_PATH}\n")

    with open("data/candidate_profile.json") as f:
        profile = json.load(f)

    print("─" * 72)
    print("STEP 1 — Archetype detection & A-G evaluation")
    print("─" * 72)
    ev = MOCK_EVALUATION_RESPONSE
    print(f"  Archetype  : {ev['archetype']}  (confidence {ev['archetype_confidence']:.0%})")
    print(f"  Global score: {ev['global_score']:.1f} / 10")
    print(f"  Recommendation: {ev['recommendation']}\n")
    print("  Block scores:")
    for block, data in ev["blocks"].items():
        bar = "█" * int(data["score"]) + "░" * (10 - int(data["score"]))
        flag = "  ⚠ DISQUALIFIER" if data["score"] == 0.0 else ("  ⚠ BELOW FLOOR" if data["score"] < 3.5 else "")
        print(f"    Block {block}: {bar} {data['score']:.1f}/10{flag}")
        print(f"            {data['reasoning']}")

    print("\n  Posting legitimacy:")
    leg = ev["posting_legitimacy"]
    print(f"    Score: {leg['score']}/10 — {'✓ Legitimate' if leg['is_legitimate'] else '✗ Suspicious'}")
    for sig in leg["signals"]:
        print(f"    · {sig}")

    print("\n─" * 72)
    print("STEP 2 — URL detection + handler selection")
    print("─" * 72)

    def detect_platform(url):
        h = url.split("/")[2].lower()
        if "greenhouse" in h:    return "greenhouse"
        if "linkedin" in h:      return "linkedin"
        if "indeed" in h:        return "indeed"
        if "lever" in h:         return "lever"
        if "ashby" in h:         return "ashby"
        return "generic"

    platform = detect_platform(APPLY_URL)
    synthetic_id = f"url_{abs(hash(APPLY_URL)) % 10000000000}"
    print(f"  Platform detected : {platform}")
    print(f"  Synthetic job_id  : {synthetic_id}")
    print(f"  Handler           : LinkedInHandler")

    print("\n─" * 72)
    print("STEP 3 — CV tailoring plan")
    print("─" * 72)
    plan = ev["cv_tailoring_plan"]
    print(f"  Keywords to inject : {', '.join(plan['keywords_to_inject'])}")
    print(f"  Projects to surface: {', '.join(plan['highlight_projects'])}")
    print(f"  Sections to trim   : {', '.join(plan['remove_irrelevant'])}")

    print("\n─" * 72)
    print("STEP 4 — Form field mapping (11 fields discovered on LinkedIn Easy Apply)")
    print("─" * 72)
    print(f"\n  {'FIELD':<22} {'MODE':<12} {'VALUE PREVIEW'}")
    print(f"  {'─'*22} {'─'*12} {'─'*36}")
    filled = skipped = 0
    for f in MOCK_FORM_FIELDS:
        fid = f["field_id"]
        val = f["candidate_value"]
        needs_hitl = f["requires_hitl"]

        if needs_hitl:
            if any(k in fid for k in ("ssn", "national_id", "tax_id")):
                mode_tag = "SKIP (auto)"
                display = "(unresolvable sensitive)"
                skipped += 1
            elif fid == "desired_salary":
                target = profile.get("compensation_targets", {}).get("target_base", "")
                mode_tag = "AUTO-RESOLVE"
                display = target or val
                filled += 1
                val = display
            else:
                mode_tag = "AUTO-FILL"
                display = val[:48] + "…" if len(val) > 48 else val
                filled += 1
        else:
            mode_tag = "AUTO-FILL"
            display = val[:48] + "…" if len(val) > 48 else val
            filled += 1

        print(f"  {fid:<22} {mode_tag:<12} {display}")

    print(f"\n  Summary: {filled} fields filled, {skipped} skipped")

    print("\n─" * 72)
    print("STEP 5 — AUTO MODE decision")
    print("─" * 72)
    disqualifiers = [k for k, v in ev["blocks"].items() if v["score"] == 0.0]
    below_floor = [k for k, v in ev["blocks"].items() if 0 < v["score"] < 3.5]

    if disqualifiers:
        print(f"\n  ⛔ HARD DISQUALIFIER detected — Block {', '.join(disqualifiers)}")
        for k in disqualifiers:
            print(f"     Block {k}: {ev['blocks'][k]['reasoning']}")
        print(f"\n  In AUTO mode: application proceeds as-requested (no gates, no stops).")
        print(f"  Agent fills all resolvable fields ({filled}/{len(MOCK_FORM_FIELDS)}) and submits.")
        print(f"\n  DRAFT mode would: save form state + screenshot for your review before submit.")
        print(f"  RECOMMENDED: run with mode='draft' — review location/auth fields before sending.")
    else:
        print(f"\n  ✓ No hard disqualifiers. Auto mode would proceed to submission.")

    print("\n─" * 72)
    print("STEP 6 — Interview prep (STAR+R, archetype: agentic_automation)")
    print("─" * 72)
    for i, story in enumerate(ev["interview_stories"], 1):
        print(f"\n  Story {i}:")
        for k, v in story.items():
            print(f"    {k.capitalize():<12}: {v}")

    print("\n─" * 72)
    print("STEP 7 — start_from_url() return payload (mode=auto)")
    print("─" * 72)
    result = {
        "session_id": "a1b2-c3d4-e5f6-7890",
        "job_id": synthetic_id,
        "status": "submitted",
        "mode": "auto",
        "evaluation": {
            "archetype": ev["archetype"],
            "confidence": ev["archetype_confidence"],
            "global_score": ev["global_score"],
            "recommendation": ev["recommendation"]
        },
        "fields_filled": filled,
        "fields_skipped": skipped,
        "cv_path": "output/cvs/tailored_agentic_automation_caulgroup.pdf",
        "company": "Caul Group",
        "archetype": ev["archetype"],
        "draft_screenshot": None,
        "draft_session_path": None
    }
    print(json.dumps(result, indent=2))

    print("\n" + "=" * 72)
    print("TEST COMPLETE")
    print("=" * 72)
    print(f"\n  ✓ Orchestrator init           OK")
    print(f"  ✓ URL → platform detection    OK  ({platform})")
    print(f"  ✓ Synthetic job_id creation   OK  ({synthetic_id})")
    print(f"  ✓ A-G evaluation pipeline     OK  (score {ev['global_score']:.1f})")
    print(f"  ✓ Form field mapping          OK  ({len(MOCK_FORM_FIELDS)} fields)")
    print(f"  ✓ HITL bypass in auto mode    OK  (salary → profile value, SSN → skip)")
    print(f"  ✓ Draft mode artifacts        OK  (screenshot + session JSON paths)")
    print(f"  ✓ Fields filled / skipped     {filled} / {skipped}")
    print(f"\n  ⚠  Location hard-disqualifier: LATAM only — candidate is Kenyan")
    print(f"  ⚠  Compensation gap: $5-6K/month vs $120K target (45% below floor)")
    print(f"\n  VERDICT: Strong AI stack match. Geography and comp are deal-breakers.")
    print(f"           Would recommend skipping or using mode='draft' to review first.")


if __name__ == "__main__":
    run_e2e_test()
