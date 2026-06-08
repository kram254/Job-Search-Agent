from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.scraper.remoteok_scraper import fetch_remoteok
from agent.scraper.linkedin_scraper import fetch_linkedin
from agent.digest.notifier import TelegramNotifier, WhatsAppNotifier, EmailNotifier

logger = logging.getLogger("daily_digest")


def _merge_and_rank(
    remoteok_jobs: List[Dict[str, Any]],
    linkedin_jobs: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    seen_keys: set = set()
    merged: List[Dict[str, Any]] = []
    for job in remoteok_jobs + linkedin_jobs:
        key = (job.get("title", "").lower(), job.get("company", "").lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(job)
    merged.sort(key=lambda j: j.get("score", 0), reverse=True)
    return merged[:top_n]


def _save_digest(jobs: List[Dict[str, Any]], output_dir: str = "output") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"digest_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)
    return path


class DailyDigest:

    def __init__(
        self,
        candidate_skills: Optional[List[str]] = None,
        linkedin_keywords: str = "AI engineer LLM machine learning",
        linkedin_location: str = "Worldwide",
        top_n: int = 5,
        output_dir: str = "output",
        telegram_notifier: Optional[TelegramNotifier] = None,
        whatsapp_notifier: Optional[WhatsAppNotifier] = None,
        email_notifier: Optional[EmailNotifier] = None,
    ):
        self._skills    = candidate_skills or []
        self._li_kw     = linkedin_keywords
        self._li_loc    = linkedin_location
        self._top_n     = top_n
        self._output    = output_dir
        self._telegram  = telegram_notifier  or TelegramNotifier()
        self._whatsapp  = whatsapp_notifier  or WhatsAppNotifier()
        self._email     = email_notifier     or EmailNotifier()

    def run(self) -> Dict[str, Any]:
        logger.info("DailyDigest: fetching RemoteOK...")
        remoteok_jobs = fetch_remoteok(
            candidate_skills=self._skills,
            max_results=30,
        )
        logger.info(f"DailyDigest: RemoteOK returned {len(remoteok_jobs)} scored listings")

        logger.info("DailyDigest: fetching LinkedIn...")
        linkedin_jobs = fetch_linkedin(
            keywords=self._li_kw,
            location=self._li_loc,
            candidate_skills=self._skills,
            max_pages=2,
        )
        logger.info(f"DailyDigest: LinkedIn returned {len(linkedin_jobs)} scored listings")

        top_jobs = _merge_and_rank(remoteok_jobs, linkedin_jobs, top_n=self._top_n)
        saved_path = _save_digest(top_jobs, self._output)
        logger.info(f"DailyDigest: top {len(top_jobs)} saved to {saved_path}")

        date_str = datetime.utcnow().strftime("%a %d %b %Y")
        intro = f"Top {len(top_jobs)} AI/ML Job Leads — {date_str}"

        telegram_ok  = self._telegram.send(top_jobs, intro=intro)
        whatsapp_ok  = self._whatsapp.send(top_jobs, intro=intro)
        email_ok     = self._email.send(
            top_jobs,
            intro=intro,
            subject=f"Daily AI/ML Job Digest – {date_str}",
        )

        return {
            "date":           date_str,
            "remoteok_count": len(remoteok_jobs),
            "linkedin_count": len(linkedin_jobs),
            "top_jobs":       top_jobs,
            "saved_to":       saved_path,
            "notifications": {
                "telegram":  telegram_ok,
                "whatsapp":  whatsapp_ok,
                "email":     email_ok,
            },
        }
