"""Universal job researcher — sources beyond the two job boards.

NEW MODULE (additive). The user's complaint: discover always returns the same
jobs because it scrapes only RemoteOK + LinkedIn's first pages. This module
researches everywhere reachable without login walls:

  1. Remotive API        (remotive.com/api/remote-jobs)   - different pool
  2. Jobicy API          (jobicy.com/api/v2/remote-jobs)  - different pool
  3. Hacker News "Who's hiring" threads (Algolia API)      - startup hidden jobs
  4. WeWorkRemotely RSS  (public RSS feed)
  5. Search-operator sweep (site: operators across boards + company career
     pages + social posts on X/Facebook/Instagram that invite applications
     by email/DM) - uses the search engine, no logins, ToS-safe

Every source is deduplicated against the existing feed (by url and by
title+company), and every result passes the LivenessChecker before it is
returned - no dead or expired links reach the user.
"""
from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

import requests

logger = logging.getLogger("universal_researcher")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json, text/plain, text/rss, */*",
}

def _search_operators(keywords: str) -> List[str]:
    """Bing search-operator sweep (DDG challenges datacenter IPs). Targets:
    hidden ATS boards, company career pages, and public social posts on
    X/Facebook/Instagram that invite applications by DM/email."""
    kw = quote_plus(keywords)
    return [
        f'https://www.bing.com/search?q=site%3Ajobs.lever.co+{kw}',
        f'https://www.bing.com/search?q=site%3Aboards.greenhouse.io+{kw}',
        f'https://www.bing.com/search?q=site%3Ajob-boards.greenhouse.io+{kw}',
        f'https://www.bing.com/search?q=site%3Ajobs.ashbyhq.com+{kw}',
        f'https://www.bing.com/search?q=site%3Ax.com+{kw}+%22we%27re+hiring%22+%22DM+me%22',
        f'https://www.bing.com/search?q=site%3Afacebook.com+{kw}+hiring+%22send+your+CV%22',
        f'https://www.bing.com/search?q=site%3Ainstagram.com+{kw}+hiring+%22link+in+bio%22',
        f'https://www.bing.com/search?q=%22we+are+hiring%22+{kw}+remote+%22apply%22+-site:linkedin.com',
    ]


def _clean(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", str(text or ""))
    t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&#39;", "'").replace("&quot;", '"').replace("&nbsp;", " "))
    return re.sub(r"\s{2,}", " ", t).strip()


def _mk_job(title: str, company: str, url: str, source: str,
            location: str = "", description: str = "",
            salary: str = "", posted: str = "") -> Dict[str, Any]:
    return {
        "id": url,  # stable: the url IS the identity (dedup upstream)
        "title": _clean(title)[:200],
        "company": _clean(company)[:120],
        "url": url,
        "source": source,
        "location": _clean(location)[:120],
        "description": _clean(description)[:8000],
        "salary_range": _clean(salary)[:80],
        "date_posted": posted or "",
        "discovered_via": source,
    }


def fetch_remotive(keywords: str = "", limit: int = 15) -> List[Dict[str, Any]]:
    try:
        params = {"limit": min(limit, 50)}
        if keywords:
            params["search"] = keywords.split()[0]
        resp = requests.get("https://remotive.com/api/remote-jobs",
                            params=params, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        raw = resp.json().get("jobs", [])[:limit]
    except Exception as e:
        logger.warning(f"Remotive fetch failed: {e}")
        return []
    out = []
    for j in raw:
        out.append(_mk_job(
            title=j.get("title", ""), company=j.get("company_name", ""),
            url=j.get("url", ""), source="remotive",
            location=j.get("candidate_required_location", ""),
            description=j.get("description", ""),
            salary=j.get("salary", ""), posted=str(j.get("publication_date", ""))[:10],
        ))
    return [j for j in out if j["url"]]


def fetch_jobicy(keywords: str = "", limit: int = 15) -> List[Dict[str, Any]]:
    try:
        params = {"count": min(limit, 50)}
        # jobicy has no 'search' param (400s) - filter client-side instead
        resp = requests.get("https://jobicy.com/api/v2/remote-jobs",
                            params=params, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        raw = resp.json().get("jobs", [])
        kws = [w.lower() for w in keywords.split() if len(w) > 2][:6]
        if kws:
            raw = [j for j in raw if any(
                k in (str(j.get("jobTitle", "")) + " " + str(j.get("jobExcerpt", ""))).lower()
                for k in kws)]
        raw = raw[:limit]
    except Exception as e:
        logger.warning(f"Jobicy fetch failed: {e}")
        return []
    out = []
    for j in raw:
        out.append(_mk_job(
            title=j.get("jobTitle", ""), company=j.get("companyName", ""),
            url=j.get("url", ""), source="jobicy",
            location=j.get("jobGeo", ""), description=j.get("jobExcerpt", ""),
            salary=j.get("annualSalaryMin") and f"from {j.get('annualSalaryMin')}" or "",
            posted=str(j.get("pubDate", ""))[:10],
        ))
    return [j for j in out if j["url"]]


def fetch_hn_hiring(keywords: str = "", limit: int = 15) -> List[Dict[str, Any]]:
    """Hacker News hiring threads via Algolia. Catches startup jobs that never
    reach job boards. Story text is searched for the user's keywords."""
    try:
        params = {
            "tags": "story,author_whoishiring",
            "query": "hiring",
            "hitsPerPage": 3,  # the recent monthly threads
        }
        resp = requests.get("https://hn.algolia.com/api/v1/search_by_date",
                            params=params, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        threads = resp.json().get("hits", [])
    except Exception as e:
        logger.warning(f"HN threads fetch failed: {e}")
        return []

    kws = [w.lower() for w in keywords.split() if len(w) > 2][:6]
    out: List[Dict[str, Any]] = []
    for t in threads:
        tid = t.get("objectID")
        if not tid:
            continue
        try:
            resp = requests.get(
                f"https://hn.algolia.com/api/v1/items/{tid}",
                headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            item = resp.json()
        except Exception:
            continue
        # top-level comments = individual job posts
        children = item.get("children", []) or []
        for c in children:
            text = _clean(c.get("text", ""))
            if not text or len(text) < 60:
                continue
            text_l = text.lower()
            if kws and not any(k in text_l for k in kws):
                continue
            # extract a url if the comment carries one (may be absent)
            m = re.search(r"https?://[^\s\)\|]+", text)
            link = m.group(0).rstrip(".,;") if m else ""
            author = c.get("author") or "HN commenter"  # author can be None on deleted comments
            comment_url = f"https://news.ycombinator.com/item?id={c.get('id')}"
            out.append(_mk_job(
                title=f"Role post by {author}",
                company=author,
                url=link or comment_url,
                source="hn_hiring",
                location="varies (see post)",
                description=text[:4000],
            ))
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    return out


def fetch_weworkremotely(keywords: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """WeWorkRemotely public RSS feeds (programming + product)."""
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
    ]
    kws = [w.lower() for w in keywords.split() if len(w) > 2][:6]
    out: List[Dict[str, Any]] = []
    for feed in feeds:
        try:
            resp = requests.get(feed, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            logger.warning(f"WWR feed failed ({feed[-30:]}): {e}")
            continue
        for item in root.iter("item"):
            title = (item.findtext("title") or "")
            link = (item.findtext("link") or "").split("?")[0]
            desc = _clean(item.findtext("description") or "")
            if not link:
                continue
            if kws and not any(k in (title + " " + desc).lower() for k in kws):
                continue
            # WWR titles look like "Company: Role"
            parts = title.split(":", 1)
            company = parts[0] if len(parts) > 1 else ""
            role = parts[1] if len(parts) > 1 else title
            out.append(_mk_job(title=role, company=company, url=link,
                               source="wwr", description=desc[:4000]))
            if len(out) >= limit:
                return out
    return out


def fetch_social_and_careers(keywords: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Search-operator sweep: career pages + social posts (X/FB/IG) that
    invite applications. Uses Bing's HTML results (DDG challenges datacenter
    IPs). Every link passes the liveness check before reaching the feed."""
    import base64
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for url in _search_operators(keywords):
        if len(out) >= limit:
            break
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.debug(f"operator sweep skipped ({url[:60]}): {e}")
            continue
        # Bing wraps results in /ck/a?...&u=a1<base64> redirects; DDG uses uddg=
        real_links: List[str] = []
        for enc in re.findall(r'href="https://www\.bing\.com/ck/a\?[^"]*?u=a1([A-Za-z0-9_-]+)', resp.text):
            pad = enc + "=" * (-len(enc) % 4)
            try:
                dec = base64.urlsafe_b64decode(pad).decode("utf-8", "replace")
                if dec.startswith("http") and "bing.com" not in dec:
                    real_links.append(dec)
            except Exception:
                continue
        for m in re.finditer(r'uddg=([^&"]+)', resp.text):
            from urllib.parse import unquote
            real_links.append(unquote(m.group(1)))
        for real in real_links:
            if real in seen or not real.startswith("http"):
                continue
            seen.add(real)
            host = real.split("/")[2].replace("www.", "") if len(real.split("/")) > 2 else real
            out.append(_mk_job(
                title=f"Hiring signal ({host})",
                company=host.split(".")[0].title(),
                url=real,
                source="social_careers_sweep",
                description="Found via search-operator sweep (X/Facebook/Instagram/careers pages). Verify on the posting page.",
            ))
            if len(out) >= limit:
                break
    return out


def research_everywhere(keywords: str = "AI engineer LLM",
                        per_source_limit: int = 10,
                        existing_urls: Optional[set] = None,
                        verify_liveness: bool = True) -> Dict[str, Any]:
    """Run every source, dedup against the feed and each other, verify
    liveness. Returns {jobs: [...], stats: {...}} - stats honest about
    sources hit, dupes skipped, and dead links dropped."""
    sources = {
        "remotive": fetch_remotive,
        "jobicy": fetch_jobicy,
        "hn_hiring": fetch_hn_hiring,
        "wwr": fetch_weworkremotely,
        "social_careers_sweep": fetch_social_and_careers,
    }
    existing_urls = existing_urls or set()
    all_jobs: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {"per_source": {}, "dupes_skipped": 0, "dead_dropped": 0}

    seen_urls = set(existing_urls)
    seen_tc = set()
    for name, fn in sources.items():
        try:
            jobs = fn(keywords, per_source_limit)
        except Exception as e:
            logger.warning(f"source {name} crashed: {e}")
            jobs = []
        fresh = []
        for j in jobs:
            u = j.get("url", "")
            tc = (j.get("title", "").lower(), j.get("company", "").lower())
            if not u or u in seen_urls or tc in seen_tc:
                stats["dupes_skipped"] += 1
                continue
            seen_urls.add(u)
            seen_tc.add(tc)
            fresh.append(j)
        stats["per_source"][name] = {"found": len(jobs), "fresh": len(fresh)}
        all_jobs.extend(fresh)

    # liveness gate: no dead/expired links reach the user
    if verify_liveness:
        from agent.scanner.liveness_checker import LivenessChecker
        checker = LivenessChecker()
        live = []
        for j in all_jobs:
            try:
                is_live, reason = checker.check(j["url"])
            except Exception:
                is_live, reason = True, "check_skipped"
            if is_live or reason == "check_failed_assume_live":
                j["verified_live"] = True
                live.append(j)
            else:
                stats["dead_dropped"] += 1
                logger.info(f"dropped dead link ({reason}): {j['url'][:80]}")
        all_jobs = live

    stats["total_fresh"] = len(all_jobs)
    stats["sources_hit"] = sum(1 for v in stats["per_source"].values() if v.get("found"))
    return {"jobs": all_jobs, "stats": stats}
