import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict


class PatternAnalyzer:
    """Conversion rate and rejection pattern analysis across job applications."""

    SCORE_BANDS = [
        (4.5, 5.0, "A+ (4.5-5.0)"),
        (4.0, 4.5, "A (4.0-4.5)"),
        (3.5, 4.0, "B+ (3.5-4.0)"),
        (3.0, 3.5, "B (3.0-3.5)"),
        (0.0, 3.0, "C or below (<3.0)")
    ]

    def __init__(self, sessions_dir: str = "data/sessions",
                 jobs_raw_path: str = "data/jobs_raw.json"):
        self.sessions_dir = Path(sessions_dir)
        self.jobs_raw_path = Path(jobs_raw_path)

    def _load_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        if not self.sessions_dir.exists():
            return sessions
        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            checkpoints = sorted(session_dir.glob("checkpoint_*.json"))
            if checkpoints:
                try:
                    with open(checkpoints[-1]) as f:
                        sessions.append(json.load(f))
                except Exception:
                    pass
        return sessions

    def _load_jobs(self) -> List[Dict[str, Any]]:
        if not self.jobs_raw_path.exists():
            return []
        try:
            with open(self.jobs_raw_path) as f:
                return json.load(f)
        except Exception:
            return []

    def _band_for_score(self, score: float) -> str:
        for lo, hi, label in self.SCORE_BANDS:
            if lo <= score <= hi:
                return label
        return "C or below (<3.0)"

    def conversion_by_score_band(self) -> Dict[str, Any]:
        sessions = self._load_sessions()

        band_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"applied": 0, "responded": 0, "interviewed": 0})

        for session in sessions:
            score = float(session.get("global_score", session.get("score", 0)))
            status = str(session.get("status", "applied")).lower()
            band = self._band_for_score(score)

            band_stats[band]["applied"] += 1
            if status in ("screening", "interview", "offer", "accepted"):
                band_stats[band]["responded"] += 1
            if status in ("interview", "offer", "accepted"):
                band_stats[band]["interviewed"] += 1

        result = {}
        for band, counts in band_stats.items():
            applied = counts["applied"]
            result[band] = {
                "applied": applied,
                "responded": counts["responded"],
                "interviewed": counts["interviewed"],
                "response_rate": round(counts["responded"] / applied, 3) if applied else 0.0,
                "interview_rate": round(counts["interviewed"] / applied, 3) if applied else 0.0
            }
        return result

    def rejection_by_archetype(self) -> Dict[str, Any]:
        sessions = self._load_sessions()

        arch_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "rejected": 0, "progressed": 0})

        for session in sessions:
            archetype = str(session.get("archetype", "unknown"))
            status = str(session.get("status", "")).lower()

            arch_stats[archetype]["total"] += 1
            if status in ("rejected", "ghosted"):
                arch_stats[archetype]["rejected"] += 1
            elif status in ("screening", "interview", "offer", "accepted"):
                arch_stats[archetype]["progressed"] += 1

        result = {}
        for arch, counts in arch_stats.items():
            total = counts["total"]
            result[arch] = {
                "total": total,
                "rejected": counts["rejected"],
                "progressed": counts["progressed"],
                "rejection_rate": round(counts["rejected"] / total, 3) if total else 0.0,
                "progression_rate": round(counts["progressed"] / total, 3) if total else 0.0
            }
        return result

    def top_companies_by_response(self, limit: int = 10) -> List[Dict[str, Any]]:
        sessions = self._load_sessions()

        company_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"applied": 0, "responded": 0})

        for session in sessions:
            company = str(session.get("company", "unknown"))
            status = str(session.get("status", "")).lower()
            company_stats[company]["applied"] += 1
            if status in ("screening", "interview", "offer", "accepted"):
                company_stats[company]["responded"] += 1

        ranked = []
        for company, counts in company_stats.items():
            applied = counts["applied"]
            ranked.append({
                "company": company,
                "applied": applied,
                "responded": counts["responded"],
                "response_rate": round(counts["responded"] / applied, 3) if applied else 0.0
            })

        ranked.sort(key=lambda x: x["response_rate"], reverse=True)
        return ranked[:limit]

    def score_vs_outcome_correlation(self) -> Dict[str, Any]:
        sessions = self._load_sessions()
        if not sessions:
            return {"correlation": None, "data_points": 0}

        scores = []
        outcomes = []
        outcome_map = {"discovered": 0, "queued": 0, "applied": 1, "screening": 2,
                       "interview": 3, "offer": 4, "accepted": 5, "rejected": -1, "ghosted": -1}

        for session in sessions:
            score = float(session.get("global_score", session.get("score", 0)))
            status = str(session.get("status", "applied")).lower()
            outcome = outcome_map.get(status, 1)
            scores.append(score)
            outcomes.append(outcome)

        if len(scores) < 2:
            return {"correlation": None, "data_points": len(scores)}

        n = len(scores)
        mean_s = sum(scores) / n
        mean_o = sum(outcomes) / n
        cov = sum((s - mean_s) * (o - mean_o) for s, o in zip(scores, outcomes)) / n
        std_s = (sum((s - mean_s) ** 2 for s in scores) / n) ** 0.5
        std_o = (sum((o - mean_o) ** 2 for o in outcomes) / n) ** 0.5

        correlation = cov / (std_s * std_o) if std_s > 0 and std_o > 0 else 0.0

        return {
            "correlation": round(correlation, 3),
            "data_points": n,
            "interpretation": (
                "strong positive" if correlation > 0.6
                else "moderate positive" if correlation > 0.3
                else "weak/no correlation" if correlation > -0.1
                else "negative correlation"
            )
        }

    def overview(self) -> Dict[str, Any]:
        sessions = self._load_sessions()
        total = len(sessions)

        status_counts: Dict[str, int] = defaultdict(int)
        for session in sessions:
            status = str(session.get("status", "applied")).lower()
            status_counts[status] += 1

        avg_score = 0.0
        if sessions:
            scores = [float(s.get("global_score", s.get("score", 0))) for s in sessions]
            avg_score = round(sum(scores) / len(scores), 2)

        return {
            "total_applications": total,
            "avg_global_score": avg_score,
            "by_status": dict(status_counts),
            "response_rate": round(
                sum(1 for s in sessions if str(s.get("status", "")).lower() in
                    ("screening", "interview", "offer", "accepted")) / max(total, 1), 3
            ),
            "interview_rate": round(
                sum(1 for s in sessions if str(s.get("status", "")).lower() in
                    ("interview", "offer", "accepted")) / max(total, 1), 3
            )
        }
