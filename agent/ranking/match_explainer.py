"""JobRight-parity Phase 1 — Match Score explanation.

NEW MODULE (additive only). Produces a human-readable, deterministic breakdown of
why a job scored the way it did: skill-by-skill alignment, experience/seniority
comparison, gaps ("areas to review before applying") and highlights.

It NEVER re-scores a job and NEVER mutates anything — it only explains, using the
existing taxonomy in agent/ranking/taxonomy.py. The numeric score shown to the user
remains whatever the existing pipeline (quality_gate / evaluator) produced.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set

try:
    from .taxonomy import TECH_TAXONOMY, resolve_canonical, get_category
except ImportError:  # pragma: no cover - direct script execution
    from agent.ranking.taxonomy import TECH_TAXONOMY, resolve_canonical, get_category


SENIORITY_LEVELS = ["intern", "junior", "mid", "senior", "lead", "principal"]

SENIORITY_TITLE_HINTS = [
    ("principal", ["principal", "distinguished"]),
    ("staff",     ["staff"]),
    ("lead",      ["tech lead", "team lead", " lead", "head of"]),
    ("senior",    ["senior", "sr.", "sr "]),
    ("junior",    ["junior", "jr.", "jr ", "entry level", "entry-level", "graduate", "intern"]),
]

JD_YEARS_PATTERN = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*\+?\s*)?years?(?:\s+of)?\s+(?:professional\s+|relevant\s+|hands-on\s+)?experience", re.IGNORECASE)
SUMMARY_YEARS_PATTERN = re.compile(r"(\d{1,2})\s*\+?\s*years?", re.IGNORECASE)


class MatchExplainer:
    """Explains a job's fit for the candidate using the shared tech taxonomy."""

    def __init__(self, candidate_profile: Dict[str, Any], job: Dict[str, Any],
                 base_score: Optional[float] = None):
        self.profile = candidate_profile or {}
        self.job = job or {}
        self.base_score = base_score if base_score is not None else float(
            job.get("score", 0) or 0
        )

    # ---------- inputs ----------

    def _job_description(self) -> str:
        for key in ("description", "descriptionText", "description_html", "descriptionHtml"):
            text = self.job.get(key, "")
            if text:
                # strip basic html tags for token matching
                return re.sub(r"<[^>]+>", " ", str(text))
        return ""

    def _candidate_skills(self) -> Set[str]:
        skills_section = self.profile.get("skills", {}) or {}
        raw = list(skills_section.get("primary", []) or []) + list(skills_section.get("secondary", []) or [])
        resolved: Set[str] = set()
        for term in raw:
            canonical = resolve_canonical(str(term))
            if canonical:
                resolved.add(canonical)
            else:
                resolved.add(str(term).strip().lower())
        return {s for s in resolved if s}

    def _jd_skills(self, description: str) -> Set[str]:
        """Every taxonomy skill (canonical or alias) mentioned in the job description."""
        text = description.lower()
        found: Set[str] = set()
        for canonical, (aliases, _cat) in TECH_TAXONOMY.items():
            # word-boundary match on canonical names so "c" doesn't match every
            # word, "angular" doesn't match "rectangular", and "c" doesn't match
            # the c in "c++"/"c#" (those belong to the cpp/csharp aliases)
            if re.search(r"\b" + re.escape(canonical) + r"\b(?![\s]*[+#])", text) \
                    or ("_" in canonical and canonical.replace("_", " ") in text) \
                    or ("_" in canonical and canonical.replace("_", "-") in text):
                found.add(canonical)
                continue
            # aliases get word boundaries too ("ng" must not match "rectangular")
            for alias in aliases:
                if re.search(r"\b" + re.escape(alias) + r"\b", text):
                    found.add(canonical)
                    break
        return found

    def _candidate_years(self) -> Optional[int]:
        # 1) explicit override if the profile ever grows a years field
        for key in ("years_of_experience", "years_experience", "experience_years"):
            val = self.profile.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return int(val)
        # 2) stated in the professional summary ("... 5+ years ...")
        summary = str((self.profile.get("narrative", {}) or {}).get("professional_summary", "") or "")
        m = SUMMARY_YEARS_PATTERN.search(summary)
        if m:
            return int(m.group(1))
        # 3) fall back to years since graduation
        education = self.profile.get("education", []) or []
        years: List[int] = []
        for ed in education if isinstance(education, list) else []:
            span = str((ed or {}).get("years", "") or "")
            found = re.findall(r"(?:19|20)\d{2}", span)
            for part in found:
                years.append(int(part))
        if years:
            end_year = max(years)
            current = datetime.now(timezone.utc).year
            return max(0, current - end_year)
        return None

    def _jd_years(self, description: str) -> Optional[int]:
        matches = JD_YEARS_PATTERN.findall(description)
        if not matches:
            return None
        try:
            return max(int(m) for m in matches)
        except (TypeError, ValueError):
            return None

    def _jd_seniority(self) -> str:
        level_field = str(self.job.get("seniorityLevel", "") or "").lower()
        if level_field and level_field not in ("not applicable", "unknown", "n/a"):
            if "senior" in level_field:
                return "senior"
            if "junior" in level_field or "entry" in level_field:
                return "junior"
            if "mid" in level_field or "intermediate" in level_field:
                return "mid"
            if "lead" in level_field or "principal" in level_field or "staff" in level_field:
                return "lead"
        title = str(self.job.get("title", "") or "").lower()
        for level, hints in SENIORITY_TITLE_HINTS:
            if any(h in title for h in hints):
                return level
        return "mid"

    # ---------- sections ----------

    def _skills_breakdown(self, description: str) -> Dict[str, Any]:
        candidate = self._candidate_skills()
        jd = self._jd_skills(description)
        matched = sorted(jd & candidate)
        missing = sorted(jd - candidate)
        ratio = (len(matched) / len(jd)) if jd else 0.0

        categories: Dict[str, int] = {}
        for skill in matched:
            cat = get_category(skill)
            if cat:
                categories[cat] = categories.get(cat, 0) + 1

        # friendly display names: swap underscores for spaces
        return {
            "matched": [s.replace("_", " ") for s in matched],
            "missing": [s.replace("_", " ") for s in missing],
            "match_ratio": round(ratio, 2),
            "jd_skill_count": len(jd),
            "categories_covered": categories,
        }

    def _experience_breakdown(self, description: str) -> Dict[str, Any]:
        jd_years = self._jd_years(description)
        cand_years = self._candidate_years()
        if jd_years is None or cand_years is None:
            return {
                "jd_years": jd_years,
                "candidate_years": cand_years,
                "delta": None,
                "status": "unknown",
                "note": "Not enough information to compare years of experience.",
            }
        delta = cand_years - jd_years
        if delta >= 0:
            status = "meets"
            note = f"Your ~{cand_years}yr of experience meets the ~{jd_years}yr requirement."
        else:
            status = "below"
            note = f"The role asks for ~{jd_years}yr; your profile suggests ~{cand_years}yr. Consider addressing this gap."
        return {
            "jd_years": jd_years,
            "candidate_years": cand_years,
            "delta": delta,
            "status": status,
            "note": note,
        }

    def _seniority_breakdown(self) -> Dict[str, Any]:
        jd_level = self._jd_seniority()
        # candidate level is inferred from their strongest signal: profile has no
        # explicit level, so mirror the JD comparator used by quality_gate
        return {
            "jd_level": jd_level,
            "aligned": jd_level in ("mid", "senior", "lead", "staff", "principal"),
            "note": f"Posting reads as a {jd_level}-level role.",
        }

    def _areas_to_review(self, skills: Dict[str, Any], experience: Dict[str, Any]) -> List[str]:
        review: List[str] = []
        high_value_missing = [s for s in skills["missing"] if s in ("python", "llm", "rag", "ai_agents", "docker", "aws", "kubernetes", "sql", "react", "typescript")]
        if high_value_missing:
            review.append("Requirements mention skills not in your profile: " + ", ".join(high_value_missing[:5]) + ".")
        if skills["jd_skill_count"] == 0:
            review.append("The description is thin on technical requirements — verify the posting before applying.")
        if experience.get("status") == "below":
            review.append(experience.get("note", "Experience gap — be ready to address it."))
        if experience.get("status") == "unknown":
            review.append("Could not compare years of experience — double-check the requirement manually.")
        if not review:
            review.append("No red flags detected — skills and experience look aligned.")
        return review

    def _highlights(self, skills: Dict[str, Any], experience: Dict[str, Any]) -> List[str]:
        highlights: List[str] = []
        if skills["matched"]:
            highlights.append("You match " + str(len(skills["matched"])) + " requested skills: " + ", ".join(skills["matched"][:6]) + ".")
        top_cats = sorted(skills["categories_covered"].items(), key=lambda kv: kv[1], reverse=True)
        if top_cats:
            highlights.append("Strongest coverage areas: " + ", ".join(c for c, _ in top_cats[:3]) + ".")
        if experience.get("status") == "meets":
            highlights.append(experience.get("note", ""))
        remote = self.job.get("location", "")
        if remote and "remote" in str(remote).lower():
            highlights.append("Remote-friendly location: " + str(remote) + ".")
        return [h for h in highlights if h]

    def _summary_line(self, skills: Dict[str, Any], experience: Dict[str, Any]) -> str:
        ratio_pct = int(skills["match_ratio"] * 100)
        if skills["jd_skill_count"] == 0:
            base = "This posting lists few detectable skills, so treat the score with care."
        else:
            base = f"Your profile covers about {ratio_pct}% of the detectable skill requirements."
        if experience.get("status") == "meets":
            base += " Experience requirement appears met."
        elif experience.get("status") == "below":
            base += " There is an experience gap to address in your application."
        return base

    # ---------- public API ----------

    def explain(self) -> Dict[str, Any]:
        description = self._job_description()
        skills = self._skills_breakdown(description)
        experience = self._experience_breakdown(description)
        seniority = self._seniority_breakdown()
        return {
            "job_id": self.job.get("id", ""),
            "title": self.job.get("title", ""),
            "company": self.job.get("companyName", self.job.get("company", "")),
            "base_score": round(self.base_score, 1),
            "skills": skills,
            "experience": experience,
            "seniority": seniority,
            "areas_to_review": self._areas_to_review(skills, experience),
            "highlights": self._highlights(skills, experience),
            "summary": self._summary_line(skills, experience),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def explain_match(candidate_profile: Dict[str, Any], job: Dict[str, Any],
                  base_score: Optional[float] = None) -> Dict[str, Any]:
    """Convenience wrapper used by the /jobs/<id>/match-explanation route."""
    return MatchExplainer(candidate_profile, job, base_score).explain()
