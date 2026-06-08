from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.mcp_server import _handle_score_job_fit, _handle_extract_lead_intel

logger = logging.getLogger("remoteok_scraper")

REMOTEOK_API = "https://remoteok.com/api"
AI_TAGS_EXACT = {
    "python", "machine-learning", "ai", "nlp", "llm", "deep-learning",
    "data-science", "backend", "engineer", "ml", "machine learning",
    "artificial intelligence", "large language model", "data science",
    "ai agents", "rag", "langchain", "mlops", "vector",
}
_STRONG_TITLE_WORDS = {
    "engineer", "developer", "scientist", "architect", "ml",
    "ai", "machine learning", "backend", "data", "llm", "nlp",
}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobSearchAgent/1.0)",
    "Accept": "application/json",
}


def _tag_matches(job: Dict[str, Any]) -> bool:
    import re as _re
    tags = {t.lower() for t in (job.get("tags") or [])}
    title = (job.get("position") or "").lower()
    if tags & AI_TAGS_EXACT:
        return True
    for word in _STRONG_TITLE_WORDS:
        pattern = r'(?<![a-z])' + _re.escape(word) + r'(?![a-z])'
        if _re.search(pattern, title):
            return True
    return False


def _to_listing(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":          str(job.get("id", "")),
        "title":       job.get("position", ""),
        "company":     job.get("company", ""),
        "location":    job.get("location", "Remote"),
        "url":         job.get("url", f"https://remoteok.com/l/{job.get('id', '')}"),
        "description": job.get("description", ""),
        "date_posted": job.get("date", ""),
        "source":      "remoteok",
        "tags":        job.get("tags") or [],
    }


def fetch_remoteok(
    candidate_skills: Optional[List[str]] = None,
    max_results: int = 30,
    min_score: int = 50,
) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(REMOTEOK_API, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        logger.error(f"RemoteOK fetch failed: {e}")
        return []

    jobs = [j for j in raw if isinstance(j, dict) and j.get("id")]
    ai_jobs = [j for j in jobs if _tag_matches(j)]
    logger.info(f"RemoteOK: {len(jobs)} total, {len(ai_jobs)} AI/ML matched")

    scored: List[Dict[str, Any]] = []
    for job in ai_jobs[:max_results]:
        listing = _to_listing(job)
        description = listing["description"]
        if not description:
            continue
        try:
            fit_params: Dict[str, Any] = {"job_description": description}
            if candidate_skills:
                fit_params["candidate_skills"] = candidate_skills
            fit = _handle_score_job_fit(fit_params)
            intel = _handle_extract_lead_intel({"job_description": description})
            qg = fit.get("quality_gate", {})
            listing["score"]          = qg.get("final_score", 50)
            listing["passes"]         = qg.get("passes", True)
            listing["match_ratio"]    = fit.get("match_ratio", 0.0)
            listing["matched_skills"] = fit.get("matched_skills", [])
            listing["missing_skills"] = fit.get("missing_skills", [])
            listing["location_type"]  = intel.get("location_type", "unspecified")
            listing["salary_range"]   = intel.get("salary_range")
        except Exception as e:
            logger.warning(f"Scoring failed for {listing['id']}: {e}")
            listing["score"] = 50
            listing["passes"] = True
        scored.append(listing)
        time.sleep(0.05)

    passing = [
        j for j in scored
        if j.get("passes", True) and j.get("match_ratio", 0) > 0
    ]
    passing.sort(key=lambda j: (j.get("score", 0), j.get("match_ratio", 0)), reverse=True)
    return passing
