import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


FOLLOWUP_CADENCE_DAYS = [7, 14, 21]

FOLLOWUP_TEMPLATES = {
    7: {
        "subject": "Following up on my application — {title} at {company}",
        "body": (
            "Hi {name},\n\n"
            "I wanted to briefly follow up on my application for the {title} role at {company}. "
            "I remain genuinely excited about this opportunity and believe my background in "
            "{archetype} aligns well with what you're building.\n\n"
            "Happy to provide any additional information. Looking forward to hearing from you.\n\n"
            "Best,\n{candidate_name}"
        )
    },
    14: {
        "subject": "Re: {title} at {company} — still very interested",
        "body": (
            "Hi {name},\n\n"
            "I'm reaching out again regarding the {title} position at {company}. "
            "I've been following your recent work on {recent_news} and it reinforces why "
            "I'm so interested in joining the team.\n\n"
            "I'd welcome a brief conversation at your convenience.\n\n"
            "Best,\n{candidate_name}"
        )
    },
    21: {
        "subject": "Final follow-up: {title} at {company}",
        "body": (
            "Hi {name},\n\n"
            "This will be my final follow-up regarding the {title} role at {company}. "
            "If the timing isn't right or the position has been filled, I completely understand. "
            "I'd still love to stay in touch for future opportunities.\n\n"
            "Thank you for your time.\n\n"
            "Best,\n{candidate_name}"
        )
    }
}


class FollowUpTracker:
    """7/14/21-day follow-up cadence manager for active applications."""

    def __init__(self, storage_path: str = "data/followups.json"):
        self.storage_path = Path(storage_path)
        self.records: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(self.storage_path) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.records, f, indent=2)
        os.replace(tmp, str(self.storage_path))

    def track(self, job_id: str, company: str, title: str, applied_at: Optional[str] = None,
              contact_name: str = "", archetype: str = "", candidate_name: str = "") -> str:
        record_id = f"fu_{job_id}"

        for record in self.records:
            if record.get("job_id") == job_id:
                return record.get("id", record_id)

        applied_dt = datetime.fromisoformat(applied_at) if applied_at else datetime.utcnow()
        followups = []
        for days in FOLLOWUP_CADENCE_DAYS:
            send_date = applied_dt + timedelta(days=days)
            followups.append({
                "day": days,
                "scheduled_date": send_date.isoformat(),
                "sent": False,
                "sent_at": None
            })

        record = {
            "id": record_id,
            "job_id": job_id,
            "company": company,
            "title": title,
            "contact_name": contact_name,
            "candidate_name": candidate_name,
            "archetype": archetype,
            "applied_at": applied_dt.isoformat(),
            "followups": followups,
            "status": "active",
            "created_at": datetime.utcnow().isoformat()
        }
        self.records.append(record)
        self._save()
        return record_id

    def get_due(self, as_of: Optional[str] = None) -> List[Dict[str, Any]]:
        now = datetime.fromisoformat(as_of) if as_of else datetime.utcnow()
        due = []

        for record in self.records:
            if record.get("status") != "active":
                continue
            for fu in record.get("followups", []):
                if fu.get("sent"):
                    continue
                scheduled = datetime.fromisoformat(fu["scheduled_date"])
                if scheduled <= now:
                    due.append({
                        "record_id": record["id"],
                        "job_id": record["job_id"],
                        "company": record["company"],
                        "title": record["title"],
                        "contact_name": record.get("contact_name", ""),
                        "archetype": record.get("archetype", ""),
                        "day": fu["day"],
                        "scheduled_date": fu["scheduled_date"],
                        "template": self.render_template(
                            day=fu["day"],
                            company=record["company"],
                            title=record["title"],
                            contact_name=record.get("contact_name", "Hiring Manager"),
                            candidate_name=record.get("candidate_name", ""),
                            archetype=record.get("archetype", "AI Engineering")
                        )
                    })
        return due

    def mark_sent(self, record_id: str, day: int) -> bool:
        for record in self.records:
            if record.get("id") == record_id:
                for fu in record.get("followups", []):
                    if fu.get("day") == day:
                        fu["sent"] = True
                        fu["sent_at"] = datetime.utcnow().isoformat()
                        self._save()
                        return True
        return False

    def close(self, record_id: str, reason: str = "responded") -> bool:
        for record in self.records:
            if record.get("id") == record_id:
                record["status"] = "closed"
                record["closed_reason"] = reason
                record["closed_at"] = datetime.utcnow().isoformat()
                self._save()
                return True
        return False

    def render_template(self, day: int, company: str, title: str,
                        contact_name: str = "Hiring Manager",
                        candidate_name: str = "",
                        archetype: str = "AI Engineering",
                        recent_news: str = "recent product announcements") -> Dict[str, str]:
        template = FOLLOWUP_TEMPLATES.get(day, FOLLOWUP_TEMPLATES[21])
        return {
            "subject": template["subject"].format(title=title, company=company),
            "body": template["body"].format(
                name=contact_name,
                title=title,
                company=company,
                archetype=archetype,
                candidate_name=candidate_name or "Candidate",
                recent_news=recent_news
            )
        }

    def all_active(self) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get("status") == "active"]

    def stats(self) -> Dict[str, Any]:
        total = len(self.records)
        active = sum(1 for r in self.records if r.get("status") == "active")
        sent_total = sum(
            1 for r in self.records
            for fu in r.get("followups", [])
            if fu.get("sent")
        )
        return {
            "total_tracked": total,
            "active": active,
            "closed": total - active,
            "followups_sent": sent_total
        }
