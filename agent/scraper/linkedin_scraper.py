from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent.mcp_server import _handle_score_job_fit, _handle_extract_lead_intel

logger = logging.getLogger("linkedin_scraper")

_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={keywords}&location={location}&f_WT=2&start={start}"
)
_JOB_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_ID_RE = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_TITLE_RE = re.compile(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*(.*?)\s*</h3>', re.S)
_COMPANY_RE = re.compile(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*<a[^>]*>\s*(.*?)\s*</a>', re.S)
_LOCATION_RE = re.compile(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*(.*?)\s*</span>', re.S)
_DETAIL_TITLE_RE = re.compile(r'<h2[^>]*class="[^"]*top-card-layout__title[^"]*"[^>]*>\s*(.*?)\s*</h2>', re.S)
_DETAIL_COMPANY_RE = re.compile(r'<a[^>]*class="[^"]*topcard__org-name-link[^"]*"[^>]*>\s*(.*?)\s*</a>', re.S)
_DETAIL_DESC_RE = re.compile(
    r'<div[^>]*class="[^"]*description__text[^"]*"[^>]*>(.*?)</div>\s*</section>',
    re.S,
)
_TAG_RE = re.compile(r'<[^>]+>')


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html).strip()


def _parse_card(html_fragment: str) -> Optional[Dict[str, Any]]:
    id_m = _ID_RE.search(html_fragment)
    if not id_m:
        return None
    job_id = id_m.group(1)
    title_m = _TITLE_RE.search(html_fragment)
    company_m = _COMPANY_RE.search(html_fragment)
    location_m = _LOCATION_RE.search(html_fragment)
    return {
        "id":       job_id,
        "title":    _strip_tags(title_m.group(1)) if title_m else "",
        "company":  _strip_tags(company_m.group(1)) if company_m else "",
        "location": _strip_tags(location_m.group(1)) if location_m else "Remote",
        "url":      f"https://www.linkedin.com/jobs/view/{job_id}/",
        "source":   "linkedin",
    }


def _fetch_detail(job_id: str) -> Optional[str]:
    url = _JOB_DETAIL_URL.format(job_id=job_id)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            desc_m = _DETAIL_DESC_RE.search(resp.text)
            if desc_m:
                return _strip_tags(desc_m.group(1))
    except Exception as e:
        logger.debug(f"Detail fetch failed {job_id}: {e}")
    return None


def fetch_linkedin(
    keywords: str = "AI engineer machine learning",
    location: str = "Worldwide",
    candidate_skills: Optional[List[str]] = None,
    max_pages: int = 2,
    min_score: int = 50,
    max_detail_fetches: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Scrape + score LinkedIn job cards.

    Worker-timeout fix: detail fetch + 2 LLM calls per card made /discover
    exceed gunicorn's worker timeout when many cards are found (20 cards x
    ~10s fallback chain each). max_detail_fetches caps how many cards get the
    expensive full scoring path; the rest keep their card-level data and a
    neutral score so they still flow into the feed. Default cap 6 (env
    LINKEDIN_MAX_DETAILS overrides). None/0 => no cap (old behavior).
    """
    if max_detail_fetches is None:
        try:
            max_detail_fetches = int(os.environ.get("LINKEDIN_MAX_DETAILS", "6"))
        except ValueError:
            max_detail_fetches = 6
    if max_detail_fetches == 0:
        max_detail_fetches = None  # explicit no-cap

    cards: List[Dict[str, Any]] = []
    for page in range(max_pages):
        url = _SEARCH_URL.format(
            keywords=quote_plus(keywords),
            location=quote_plus(location),
            start=page * 25,
        )
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"LinkedIn page {page} returned {resp.status_code}")
                break
            html = resp.text
        except Exception as e:
            logger.error(f"LinkedIn fetch error page {page}: {e}")
            break

        fragments = html.split('data-entity-urn="urn:li:jobPosting:')
        for frag in fragments[1:]:
            card = _parse_card('data-entity-urn="urn:li:jobPosting:' + frag)
            if card:
                cards.append(card)
        time.sleep(1.0)

    logger.info(f"LinkedIn: {len(cards)} cards found")

    scored: List[Dict[str, Any]] = []
    detail_budget = max_detail_fetches  # worker-timeout fix: cap the expensive path
    for card in cards:
        if detail_budget is None or detail_budget > 0:
            description = _fetch_detail(card["id"]) or ""
            if detail_budget is not None:
                detail_budget -= 1
        else:
            description = ""
            card["score"] = 50
            card["passes"] = True
            card["score_capped"] = True  # marked: not fully scored (budget)
            scored.append(card)
            continue
        card["description"] = description
        card["date_posted"] = ""
        if not description:
            card["score"] = 50
            card["passes"] = True
            scored.append(card)
            continue
        try:
            fit_params: Dict[str, Any] = {"job_description": description}
            if candidate_skills:
                fit_params["candidate_skills"] = candidate_skills
            fit = _handle_score_job_fit(fit_params)
            intel = _handle_extract_lead_intel({"job_description": description})
            qg = fit.get("quality_gate", {})
            card["score"]          = qg.get("final_score", 50)
            card["passes"]         = qg.get("passes", True)
            card["match_ratio"]    = fit.get("match_ratio", 0.0)
            card["matched_skills"] = fit.get("matched_skills", [])
            card["missing_skills"] = fit.get("missing_skills", [])
            card["location_type"]  = intel.get("location_type", "unspecified")
            card["salary_range"]   = intel.get("salary_range")
        except Exception as e:
            logger.warning(f"Scoring failed {card['id']}: {e}")
            card["score"] = 50
            card["passes"] = True
        scored.append(card)
        time.sleep(0.1)

    passing = [
        j for j in scored
        if j.get("passes", True) and j.get("match_ratio", 0) > 0
    ]
    passing.sort(key=lambda j: (j.get("score", 0), j.get("match_ratio", 0)), reverse=True)
    return passing
