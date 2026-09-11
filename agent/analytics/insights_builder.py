"""JobRight-parity Phase 1 — Insights builder.

NEW MODULE (additive only). Aggregates the candidate profile against the current
job feed and application history into a single "alignment" view, JobRight-style:
how your skills stack up against market demand in your feed, seniority mix,
industry mix, and application funnel health. Read-only — writes nothing.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Any, List, Optional

try:
    from .match_explainer import MatchExplainer
    from .taxonomy import resolve_canonical, get_category
except ImportError:  # pragma: no cover - direct script execution
    from agent.ranking.match_explainer import MatchExplainer
    from agent.ranking.taxonomy import resolve_canonical, get_category


class InsightsBuilder:
    def __init__(self, candidate_profile: Dict[str, Any], jobs: List[Dict[str, Any]],
                 applications: Optional[List[Dict[str, Any]]] = None):
        self.profile = candidate_profile or {}
        self.jobs = jobs or []
        self.applications = applications or []
        self._explainer = MatchExplainer(self.profile, {})

    # ---------- profile side ----------

    def profile_summary(self) -> Dict[str, Any]:
        skills = self.profile.get("skills", {}) or {}
        primary = [str(s) for s in (skills.get("primary", []) or [])]
        secondary = [str(s) for s in (skills.get("secondary", []) or [])]
        education = self.profile.get("education", []) or []
        degrees = [str((e or {}).get("degree", "")) for e in education if isinstance(e, dict)]
        years = self._explainer._candidate_years()
        return {
            "top_skills": primary[:10],
            "supporting_skills": secondary[:10],
            "years_experience_estimate": years,
            "education": degrees,
            "positioning": (self.profile.get("narrative", {}) or {}).get("positioning", ""),
        }

    # ---------- market side ----------

    def market_demand_skills(self, top_n: int = 12) -> List[Dict[str, Any]]:
        """How often each taxonomy skill appears across the current feed."""
        import re as _re
        from agent.ranking.taxonomy import TECH_TAXONOMY

        counter: Counter = Counter()
        for job in self.jobs:
            description = job.get("description", "") or job.get("descriptionText", "") or ""
            if not description:
                continue
            text = _re.sub(r"<[^>]+>", " ", str(description)).lower()
            for canonical, (aliases, _cat) in TECH_TAXONOMY.items():
                # word-boundary match on canonical names so "c" doesn't match every
                # word, "angular" doesn't match "rectangular", and "c" doesn't match
                # the c in "c++"/"c#" (those belong to the cpp/csharp aliases)
                if _re.search(r"\b" + _re.escape(canonical) + r"\b(?![\s]*[+#])", text) \
                        or ("_" in canonical and canonical.replace("_", " ") in text):
                    counter[canonical] += 1
                    continue
                # aliases get word boundaries too ("ng" must not match "rectangular")
                if any(_re.search(r"\b" + _re.escape(a) + r"\b", text) for a in aliases):
                    counter[canonical] += 1
        total = max(1, len(self.jobs))
        return [
            {"skill": s.replace("_", " "), "demand_count": c, "demand_ratio": round(c / total, 2)}
            for s, c in counter.most_common(top_n)
        ]

    def market_seniority_mix(self) -> Dict[str, int]:
        mix: Counter = Counter()
        for job in self.jobs:
            level = str(job.get("seniorityLevel", "") or "").lower()
            if not level or level in ("not applicable", "unknown", "n/a"):
                mix["unspecified"] += 1
            elif "senior" in level:
                mix["senior"] += 1
            elif "junior" in level or "entry" in level:
                mix["junior"] += 1
            elif "mid" in level:
                mix["mid"] += 1
            else:
                mix["other"] += 1
        return dict(mix)

    def market_score_stats(self) -> Dict[str, Any]:
        scores = [float(j.get("score", 0) or 0) for j in self.jobs if j.get("score") is not None]
        if not scores:
            return {"avg": 0, "max": 0, "count": 0, "high_match_count": 0}
        high = sum(1 for s in scores if s >= 75)
        return {
            "avg": round(sum(scores) / len(scores), 1),
            "max": round(max(scores), 1),
            "count": len(scores),
            "high_match_count": high,
        }

    def demand_vs_profile(self, top_n: int = 12) -> Dict[str, Any]:
        """Cross the market's most-demanded skills with what the candidate has."""
        demand = self.market_demand_skills(top_n)
        candidate = {str(s).lower() for s in
                     ((self.profile.get("skills", {}) or {}).get("primary", []) or [])}
        candidate_resolved = set()
        for term in candidate:
            resolved = resolve_canonical(term)
            candidate_resolved.add(resolved or str(term).lower())
        for item in demand:
            canonical = resolve_canonical(item["skill"])
            item["in_profile"] = bool(canonical and canonical in candidate_resolved)
        have = sum(1 for d in demand if d["in_profile"])
        coverage = round(have / max(1, len(demand)), 2)
        return {
            "demand": demand,
            "coverage_ratio": coverage,
            "skills_to_consider": [d["skill"] for d in demand if not d["in_profile"]][:6],
        }

    # ---------- application funnel ----------

    def application_funnel(self) -> Dict[str, Any]:
        statuses: Counter = Counter()
        for app in self.applications:
            status = str((app or {}).get("status", "") or "unknown").lower()
            statuses[status] += 1
        return {
            "total_applications": len(self.applications),
            "by_status": dict(statuses),
        }

    # ---------- recommendations ----------

    def recommendations(self, demand: Dict[str, Any], scores: Dict[str, Any]) -> List[str]:
        recs: List[str] = []
        if scores.get("high_match_count", 0) == 0 and scores.get("count", 0) > 0:
            recs.append("No jobs in your current feed score above 75 — consider widening locations or keywords.")
        if demand.get("skills_to_consider"):
            recs.append("High-demand skills missing from your profile: " + ", ".join(demand["skills_to_consider"]) + ".")
        if demand.get("coverage_ratio", 0) >= 0.7:
            recs.append("Your skill set covers most of the current market demand — keep applying to top-scored roles.")
        if self.applications and len(self.applications) > 0:
            recs.append("You have " + str(len(self.applications)) + " tracked applications — follow up on anything past 7 days.")
        if not recs:
            recs.append("Run a scan to populate your feed and unlock market-alignment insights.")
        return recs

    # ---------- public API ----------

    def build(self) -> Dict[str, Any]:
        demand_block = self.demand_vs_profile()
        scores = self.market_score_stats()
        return {
            "profile": self.profile_summary(),
            "market": {
                "feed_size": len(self.jobs),
                "score_stats": scores,
                "seniority_mix": self.market_seniority_mix(),
                "top_demand_skills": self.market_demand_skills(12),
            },
            "alignment": demand_block,
            "application_funnel": self.application_funnel(),
            "recommendations": self.recommendations(demand_block, scores),
        }


def build_insights(candidate_profile: Dict[str, Any], jobs: List[Dict[str, Any]],
                   applications: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Convenience wrapper used by the /insights route."""
    return InsightsBuilder(candidate_profile, jobs, applications).build()
