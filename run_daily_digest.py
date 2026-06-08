from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent.digest.daily_digest import DailyDigest

CANDIDATE_PROFILE = json.load(open("data/candidate_profile.json"))

candidate_skills = (
    CANDIDATE_PROFILE.get("skills", {}).get("primary", []) +
    CANDIDATE_PROFILE.get("skills", {}).get("secondary", [])
)


def separator(title: str = "") -> None:
    width = 70
    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "─" * pad + f" {title} " + "─" * pad)
    else:
        print("\n" + "─" * width)


def run() -> None:
    print("\n" + "═" * 70)
    print("  DAILY JOB DIGEST – AI/ML Lead Generation")
    print("═" * 70)

    digest = DailyDigest(
        candidate_skills=candidate_skills,
        linkedin_keywords="AI engineer LLM machine learning agentic",
        linkedin_location="Worldwide",
        top_n=5,
        output_dir="output",
    )

    result = digest.run()

    separator("SOURCES")
    print(f"  RemoteOK listings scored : {result['remoteok_count']}")
    print(f"  LinkedIn listings scored : {result['linkedin_count']}")

    separator("TOP 5 LEADS")
    for i, job in enumerate(result["top_jobs"], 1):
        title   = job.get("title", "?")
        company = job.get("company", "?")
        score   = job.get("score", "?")
        ratio   = job.get("match_ratio", 0)
        url     = job.get("url", "")
        matched = ", ".join(job.get("matched_skills", [])[:5]) or "—"
        salary  = job.get("salary_range") or "undisclosed"
        print(f"\n  #{i}  {title} @ {company}")
        print(f"      Score: {score}/100  |  Match: {ratio:.0%}  |  Salary: {salary}")
        print(f"      Skills matched: {matched}")
        print(f"      URL: {url}")

    separator("NOTIFICATIONS")
    notifs = result["notifications"]
    print(f"  Telegram  : {'✅ sent' if notifs['telegram']  else '⚠️  skipped (no credentials)'}")
    print(f"  WhatsApp  : {'✅ sent' if notifs['whatsapp']  else '⚠️  skipped (no credentials)'}")
    print(f"  Email     : {'✅ sent' if notifs['email']     else '⚠️  skipped (no credentials)'}")

    separator("OUTPUT")
    print(f"  Digest saved : {result['saved_to']}")
    print()


if __name__ == "__main__":
    run()
