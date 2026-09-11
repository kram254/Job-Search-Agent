from __future__ import annotations

import os
import re
import logging
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger("contact_lookup")

PRIORITY_TITLES: List[str] = [
    "founder",
    "co-founder",
    "chief executive",
    "ceo",
    "chief technology",
    "cto",
    "head of engineering",
    "vp of engineering",
    "vp engineering",
    "engineering manager",
    "recruiter",
    "talent",
    "hr",
    "human resources",
]

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"


def _title_priority(title: str) -> int:
    title_lower = title.lower()
    for rank, pattern in enumerate(PRIORITY_TITLES):
        if pattern in title_lower:
            return rank
    return len(PRIORITY_TITLES)


def _extract_domain(company_or_url: str) -> str:
    company_or_url = company_or_url.strip()
    url_match = re.search(r"https?://(?:www\.)?([^/\s]+)", company_or_url)
    if url_match:
        return url_match.group(1)
    company_or_url = re.sub(r"\s+", "", company_or_url.lower())
    company_or_url = re.sub(r"[^a-z0-9\-.]", "", company_or_url)
    if "." not in company_or_url:
        company_or_url = f"{company_or_url}.com"
    return company_or_url


class ContactLookup:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("HUNTER_API_KEY", "")

    def lookup(self, company_or_domain: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("[ContactLookup] HUNTER_API_KEY not set – skipping lookup")
            return None

        domain = _extract_domain(company_or_domain)
        logger.debug(f"[ContactLookup] Querying Hunter for domain: {domain}")

        try:
            resp = requests.get(
                HUNTER_DOMAIN_SEARCH_URL,
                params={"domain": domain, "api_key": self.api_key, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[ContactLookup] Hunter API error for {domain}: {e}")
            return None

        emails: List[Dict[str, Any]] = data.get("data", {}).get("emails", [])
        if not emails:
            logger.debug(f"[ContactLookup] No emails found for {domain}")
            return None

        verified = [e for e in emails if e.get("verification", {}).get("status") == "valid"]
        candidates = verified if verified else emails

        best = min(
            candidates,
            key=lambda e: _title_priority(e.get("position", "") or ""),
        )

        return {
            "domain":     domain,
            "name":       f"{best.get('first_name', '')} {best.get('last_name', '')}".strip(),
            "email":      best.get("value", ""),
            "title":      best.get("position", ""),
            "confidence": best.get("confidence", 0),
            "linkedin":   best.get("linkedin", ""),
        }

    def lookup_all(self, company_or_domain: str,
                   limit: int = 10) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []

        domain = _extract_domain(company_or_domain)
        try:
            resp = requests.get(
                HUNTER_DOMAIN_SEARCH_URL,
                params={"domain": domain, "api_key": self.api_key, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[ContactLookup] Hunter API error for {domain}: {e}")
            return []

        emails = data.get("data", {}).get("emails", [])
        results = []
        for e in emails:
            results.append({
                "domain":     domain,
                "name":       f"{e.get('first_name', '')} {e.get('last_name', '')}".strip(),
                "email":      e.get("value", ""),
                "title":      e.get("position", ""),
                "confidence": e.get("confidence", 0),
                "linkedin":   e.get("linkedin", ""),
                "priority":   _title_priority(e.get("position", "") or ""),
            })
        results.sort(key=lambda x: x["priority"])
        return results

    # ---------------------------------------------------------------------- #
    # JobRight-parity Phase 5 — alumni signal & insider search links
    # (ADDITIVE methods only — existing lookup/lookup_all untouched)
    # ---------------------------------------------------------------------- #

    @staticmethod
    def build_insider_search_links(company: str,
                                   candidate_education: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate ready-to-click insider search URLs for a target company.

        JobRight's 'insider connections' parity: alumni + hiring-manager searches
        keyed off the candidate's own education (from candidate_profile.education)
        and the target company.
        """
        slug = re.sub(r"\s+", "-", (company or "").strip().lower())
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        linkedin_base = f"https://www.linkedin.com/search/results/people/?keywords={slug}"

        alumni_links: List[Dict[str, str]] = []
        for ed in (candidate_education or []):
            school = str((ed or {}).get("institution", "") or "").strip()
            if not school:
                continue
            school_q = requests.utils.quote(f"{school}")
            alumni_links.append({
                "school": school,
                "url": (
                    "https://www.linkedin.com/search/results/people/"
                    f"?keywords={requests.utils.quote(company)}%20{school_q}"
                    f"&schoolFilter={requests.utils.quote(school)}"
                ),
            })

        return {
            "company": company,
            "hiring_managers": (
                f"{linkedin_base}%20(recruiter%20OR%20%22hiring%20manager%22)"
            ),
            "engineers_at_company": (
                f"{linkedin_base}%20(engineer%20OR%20developer%20OR%20%22engineering%22)"
            ),
            "alumni": alumni_links,
        }

    def find_insiders(self, company_or_domain: str,
                      candidate_education: Optional[List[Dict[str, Any]]] = None,
                      limit: int = 5) -> Dict[str, Any]:
        """Combined insider discovery: verified contacts (Hunter, if configured)
        plus alumni/hiring-manager search links. Never raises — outreach flows
        degrade gracefully."""
        result: Dict[str, Any] = {
            "company": company_or_domain,
            "contacts": [],
            "search_links": self.build_insider_search_links(company_or_domain, candidate_education),
            "hunter_configured": bool(self.api_key),
        }
        try:
            result["contacts"] = self.lookup_all(company_or_domain, limit=limit)
        except Exception as e:
            logger.warning(f"[ContactLookup] find_insiders lookup failed: {e}")
        return result
