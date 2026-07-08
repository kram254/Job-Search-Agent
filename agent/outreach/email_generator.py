from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("email_generator")

_ARCHETYPE_PROOF_MAP: Dict[str, str] = {
    "agentic_automation":    "agentic_automation",
    "ai_platform_llmops":    "ai_platform_llmops",
    "ai_forward_deployed":   "ai_forward_deployed",
    "technical_ai_pm":       "ai_forward_deployed",
    "ai_solutions_architect":"ai_platform_llmops",
    "ai_transformation":     "agentic_automation",
    "unknown":               "agentic_automation",
}

_EMAIL_SYSTEM = (
    "You are a cold-outreach specialist writing on behalf of a senior AI/ML engineer. "
    "Your emails are concise (under 160 words body), highly specific to the role, "
    "technically credible, and end with a single low-friction ask. "
    "Never use hollow phrases like 'I would love to', 'I am passionate about', "
    "'I believe I would be a great fit', or 'please find my resume attached'. "
    "Write in first person, direct voice."
)


def _pick_proof_points(profile: Dict[str, Any], archetype: str) -> List[Dict[str, Any]]:
    proof_points: List[Dict[str, Any]] = profile.get("proof_points", [])
    target_archetype = _ARCHETYPE_PROOF_MAP.get(archetype, "agentic_automation")
    matched = [p for p in proof_points if p.get("archetype") == target_archetype]
    if not matched:
        matched = proof_points
    return matched[:2]


def _build_prompt(
    profile: Dict[str, Any],
    job_meta: Dict[str, Any],
    contact: Optional[Dict[str, Any]],
    archetype: str,
    matched_skills: List[str],
    missing_skills: List[str],
    quality_score: int,
) -> str:
    name = profile["personal_details"]["name"].title()
    github = profile["professional_profiles"].get("github", "")
    linkedin = profile["professional_profiles"].get("linkedin", "")
    summary = profile["narrative"]["professional_summary"]
    positioning = profile["narrative"]["positioning"]
    proof_points = _pick_proof_points(profile, archetype)

    company = job_meta.get("company", "the company")
    title = job_meta.get("title", "the role")
    jd_snippet = (job_meta.get("description", ""))[:600]

    recipient_name = (contact or {}).get("name", "")
    recipient_title = (contact or {}).get("title", "")

    proof_text = ""
    for pp in proof_points:
        proof_text += f"- {pp['metric']} ({pp['context']})\n"

    skills_text = ", ".join(matched_skills[:6]) if matched_skills else "AI/ML stack"

    _generic_titles = {"hiring", "hr", "human resources", "talent", "recruiter",
                       "jobs", "careers", "team", "hello", "info", "contact"}
    first_name = recipient_name.split()[0] if recipient_name else ""
    if first_name and first_name.lower() not in _generic_titles:
        salutation = f"Hi {first_name},"
    else:
        salutation = f"Hi {company} team,"

    prompt = f"""Write a cold outreach email for this situation:

SENDER: {name}
POSITIONING: {positioning}
SUMMARY: {summary}
RELEVANT PROOF POINTS:
{proof_text.strip()}
MATCHED SKILLS: {skills_text}

TARGET ROLE: {title} at {company}
JD EXCERPT: {jd_snippet}
ARCHETYPE: {archetype}
QUALITY SCORE: {quality_score}/100

RECIPIENT: {recipient_name or 'Hiring team'} ({recipient_title or 'unspecified'})
SALUTATION: {salutation}

INSTRUCTIONS:
- Start with the salutation
- Body: 3 short paragraphs. First: why this specific role caught attention (reference something concrete from the JD). Second: most relevant proof point (use the specific metric). Third: direct ask — a 20-minute call this week or next.
- Subject line on the first line, formatted as: SUBJECT: <your subject here>
- Separate subject from body with a blank line
- Sign off as: {name}
- GitHub: {github}
- LinkedIn: {linkedin}
- Keep body under 160 words
- Do not use bullet lists in the email body
"""
    return prompt


class EmailGenerator:

    def __init__(self, llm_client=None):
        self._llm = llm_client
        if self._llm is None:
            try:
                from agent.llm.llm_client import LLMClient
                self._llm = LLMClient()
            except Exception as e:
                logger.warning(f"LLMClient unavailable: {e}")

    def generate(
        self,
        profile: Dict[str, Any],
        job_meta: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None,
        evaluation: Optional[Dict[str, Any]] = None,
        intel: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        archetype = "agentic_automation"
        matched_skills: List[str] = []
        missing_skills: List[str] = []
        quality_score = 80

        if evaluation:
            archetype = evaluation.get("archetype", archetype)
            matched_skills = evaluation.get("matched_skills", [])
            missing_skills = evaluation.get("missing_skills", [])
            qg = evaluation.get("quality_gate", {})
            quality_score = qg.get("final_score", quality_score)

        if intel:
            if not matched_skills:
                matched_skills = intel.get("stack", [])[:6]

        prompt = _build_prompt(
            profile=profile,
            job_meta=job_meta,
            contact=contact,
            archetype=archetype,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            quality_score=quality_score,
        )

        if self._llm is None:
            return {
                "subject": f"Re: {job_meta.get('title', 'Role')} – Emmanuel Ndaliro",
                "body": "[LLMClient unavailable – email not generated]",
                "contact": contact,
                "word_count": 0,
                "archetype": archetype,
            }

        try:
            raw = self._llm.complete_for_step(
                "generator",
                prompt,
                system=_EMAIL_SYSTEM,
                max_tokens=512,
                temperature=0.4,
            )
        except Exception as e:
            logger.error(f"EmailGenerator LLM call failed: {e}")
            return {
                "subject": f"Re: {job_meta.get('title', 'Role')} – Emmanuel Ndaliro",
                "body": f"[Generation failed: {e}]",
                "contact": contact,
                "word_count": 0,
                "archetype": archetype,
            }

        if not raw:
            raw = self._build_template(profile, job_meta, contact, archetype, matched_skills)

        subject, body = self._parse_response(raw)
        word_count = len(body.split())

        return {
            "subject":       subject,
            "body":          body,
            "raw":           raw,
            "contact":       contact,
            "word_count":    word_count,
            "archetype":     archetype,
            "matched_skills": matched_skills,
        }

    @staticmethod
    def _build_template(
        profile: Dict[str, Any],
        job_meta: Dict[str, Any],
        contact: Optional[Dict[str, Any]],
        archetype: str,
        matched_skills: List[str],
    ) -> str:
        name = profile.get("personal_details", {}).get("name", "Emmanuel Ndaliro").title()
        github = profile.get("professional_profiles", {}).get("github", "")
        linkedin = profile.get("professional_profiles", {}).get("linkedin", "")
        company = job_meta.get("company", "your team")
        title = job_meta.get("title", "this role")
        skills_text = ", ".join(matched_skills[:4]) if matched_skills else "AI/ML systems"
        proof_points = profile.get("proof_points", [])
        proof = proof_points[0] if proof_points else {"metric": "90% reduction in processing time", "context": "agentic automation"}
        recipient_name = (contact or {}).get("name", "")
        first_name = recipient_name.split()[0] if recipient_name else ""
        salutation = f"Hi {first_name}," if first_name else f"Hi {company} team,"

        return f"""SUBJECT: {title} – {name} | {skills_text}

{salutation}

I came across the {title} opening at {company} and wanted to reach out directly.

I'm an AI/ML engineer focused on {archetype.replace('_', ' ')} — I've achieved {proof['metric']} through {proof['context']}.

My relevant background: {skills_text}. I build systems that ship to production, not just demos.

Would you be open to a 15-minute call this week? Happy to share specific work samples relevant to what you're building.

{name}
{github}
{linkedin}"""

    @staticmethod
    def _parse_response(raw: str) -> tuple:
        if not raw:
            return "Application", ""
        lines = raw.strip().splitlines()
        subject = ""
        body_lines = []
        found_subject = False

        for i, line in enumerate(lines):
            if line.upper().startswith("SUBJECT:"):
                subject = line[len("SUBJECT:"):].strip()
                found_subject = True
                body_lines = lines[i + 1:]
                break

        if not found_subject:
            body_lines = lines

        while body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]

        body = "\n".join(body_lines).strip()

        if not subject:
            subject = body_lines[0][:80] if body_lines else "Application"
            body = "\n".join(body_lines[1:]).strip()

        return subject, body
