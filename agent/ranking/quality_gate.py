from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

try:
    from .taxonomy import RED_FLAGS
except ImportError:
    from agent.ranking.taxonomy import RED_FLAGS

STALE_THRESHOLD_DAYS = 30
THIN_THRESHOLD_WORDS = 80
MAX_RED_FLAG_PENALTY = 45
GATE_FAIL_THRESHOLD = 50

PENALTIES = {
    "stale":           35,
    "thin":            18,
    "missing_company":  8,
    "red_flag":        16,
    "wrong_seniority": 38,
}


class QualityGate:

    def evaluate(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        description = listing_data.get("description", "")
        title       = listing_data.get("title", "")
        company     = listing_data.get("company", "")
        posted_date = listing_data.get("datePosted", listing_data.get("date_posted", ""))

        penalties: List[Dict[str, Any]] = []
        total_penalty = 0

        if self._is_stale(posted_date):
            total_penalty += PENALTIES["stale"]
            penalties.append({"reason": "stale", "penalty": PENALTIES["stale"]})

        word_count = len(description.split())
        if word_count < THIN_THRESHOLD_WORDS:
            total_penalty += PENALTIES["thin"]
            penalties.append({"reason": "thin_description", "penalty": PENALTIES["thin"], "words": word_count})

        if not company or len(company.strip()) < 2:
            total_penalty += PENALTIES["missing_company"]
            penalties.append({"reason": "missing_company", "penalty": PENALTIES["missing_company"]})

        text_lower = (description + " " + title).lower()
        rf_applied = 0
        for flag in RED_FLAGS:
            if flag in text_lower:
                delta = min(PENALTIES["red_flag"], MAX_RED_FLAG_PENALTY - rf_applied)
                if delta > 0:
                    rf_applied += delta
                    penalties.append({"reason": f"red_flag:{flag}", "penalty": delta})
        total_penalty += rf_applied

        final_score = max(0, 100 - total_penalty)
        passes = total_penalty < GATE_FAIL_THRESHOLD

        return {
            "base_score":    100,
            "final_score":   final_score,
            "total_penalty": total_penalty,
            "penalties":     penalties,
            "passes":        passes,
        }

    def evaluate_seniority_mismatch(self, jd_years_required: int,
                                     candidate_years: int,
                                     jd_level: str) -> Dict[str, Any]:
        penalty = 0
        mismatch_reason = ""

        if jd_level == "senior" and candidate_years < jd_years_required - 2:
            penalty = PENALTIES["wrong_seniority"]
            mismatch_reason = f"senior role needs {jd_years_required}yr, candidate has {candidate_years}yr"
        elif jd_level == "junior" and candidate_years > jd_years_required + 4:
            penalty = PENALTIES["wrong_seniority"] // 2
            mismatch_reason = f"overqualified for junior role"

        return {
            "penalty": penalty,
            "reason":  mismatch_reason,
            "passes":  penalty == 0,
        }

    @staticmethod
    def _is_stale(posted_date: str) -> bool:
        if not posted_date:
            return False
        try:
            cleaned = posted_date.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - dt
            return age.days > STALE_THRESHOLD_DAYS
        except Exception:
            return False

    @staticmethod
    def extract_years_required(jd_text: str) -> int:
        patterns = [
            r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
            r"(\d+)\+?\s*yrs?\s+(?:of\s+)?experience",
            r"experience[:\s]+(\d+)\+?\s*years?",
        ]
        for pattern in patterns:
            match = re.search(pattern, jd_text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0
