"""Application tracker CSV for the ai-job-search framework bridge.

Implements the framework's job_search_tracker.csv contract (header, dedup,
outcome recording) and the /outcome follow-up rules, integrated with the
app's existing JSON ledger. NEW MODULE (additive only).
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

TRACKER_HEADER = [
    "date", "company", "sector", "role", "role_type", "channel", "status",
    "contact_person", "fit_rating", "notes", "cv_file", "cover_letter_file",
    "source", "deadline",
]

# Framework tracker status vocabulary (final statuses end the lifecycle)
FINAL_STATUSES = {"hired", "rejected", "no response", "withdrawn", "dead"}
FOLLOWUP_THRESHOLD_DAYS = 10
STALE_THRESHOLD_DAYS = 60
MAX_FOLLOWUPS = 2


class TrackerCSV:
    """CSV tracker that mirrors the framework's format, coexisting with the
    app's JSON application ledger (the ledger stays authoritative for the
    app's own views; this CSV is the framework-compatible record)."""

    def __init__(self, csv_path: str = "data/job_search_tracker.csv"):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            self._write_header()

    def _write_header(self) -> None:
        with open(self.csv_path, "w", newline="") as f:
            csv.writer(f).writerow(TRACKER_HEADER)

    def _read_all(self) -> List[Dict[str, str]]:
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, newline="") as f:
            return list(csv.DictReader(f))

    def _save_all(self, rows: List[Dict[str, str]]) -> None:
        with open(self.csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=TRACKER_HEADER)
            writer.writeheader()
            writer.writerows(rows)

    def add(self, company: str, role: str, status: str = "drafted",
            channel: str = "email", contact_person: str = "",
            fit_rating: str = "", notes: str = "", cv_file: str = "",
            cover_letter_file: str = "", source: str = "",
            deadline: str = "", sector: str = "", role_type: str = "") -> str:
        """Add a row. Dedup: same company+role (case-insensitive, whitespace-
        collapsed) is a no-op returning the existing row's key info."""
        def norm(s: str) -> str:
            return " ".join(s.split()).lower()
        rows = self._read_all()
        for r in rows:
            if norm(r["company"]) == norm(company) and norm(r["role"]) == norm(role):
                return f"exists:{r['company']}|{r['role']}|{r['status']}"
        rows.append({
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "company": company, "sector": sector, "role": role,
            "role_type": role_type, "channel": channel, "status": status,
            "contact_person": contact_person, "fit_rating": fit_rating,
            "notes": notes, "cv_file": cv_file,
            "cover_letter_file": cover_letter_file, "source": source,
            "deadline": deadline,
        })
        self._save_all(rows)
        return f"added:{company}|{role}|{status}"

    def update_status(self, company: str, role: str, status: str,
                      note: str = "") -> bool:
        """Update a row's status; appends a dated note marker for follow-ups."""
        rows = self._read_all()
        changed = False
        for r in rows:
            if r["company"].strip().lower() == company.strip().lower() \
               and r["role"].strip().lower() == role.strip().lower():
                r["status"] = status
                if note:
                    stamp = datetime.utcnow().strftime("%Y-%m-%d")
                    r["notes"] = (r["notes"] + "; " if r["notes"] else "") + f"{stamp} {note}"
                changed = True
        if changed:
            self._save_all(rows)
        return changed

    def mark_followup(self, company: str, role: str) -> bool:
        return self.update_status(company, role, status="applied",
                                  note=f"followed up")

    # ---------- /outcome reporting ----------

    def open_applications(self) -> List[Dict[str, Any]]:
        """Open rows with derived days_quiet + followups_sent (framework's
        derived-column rules)."""
        out = []
        for r in self._read_all():
            if r["status"].lower() in FINAL_STATUSES:
                continue
            if r["status"].lower() == "drafted":
                continue  # drafted rows never count as quiet
            dates = [r["date"]]
            dates += [w.replace("followed up", "").strip()
                      for w in r["notes"].split(";")
                      if w.strip().startswith("followed up") or "20" in w]
            days_quiet = None
            followups = r["notes"].lower().count("followed up")
            out.append({
                "company": r["company"], "role": r["role"],
                "status": r["status"], "date_applied": r["date"],
                "deadline": r["deadline"], "days_quiet_est": days_quiet,
                "followups_sent": followups,
            })
        return out

    def needs_followup(self, threshold_days: int = FOLLOWUP_THRESHOLD_DAYS) -> List[Dict[str, Any]]:
        """Open applications quiet for >= threshold with < MAX_FOLLOWUPS.
        A follow-up resets the quiet clock (dated note = last touch), matching
        the framework's days-quiet rule (counts from the latest dated entry)."""
        result = []
        for row in self.open_applications():
            if row["followups_sent"] >= MAX_FOLLOWUPS:
                continue
            try:
                applied = datetime.strptime(row["date_applied"], "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            # last touch = application date OR latest follow-up date, whichever newer
            last_touch = applied
            for fu in self._read_all():
                if fu["company"].strip().lower() == row["company"].strip().lower() \
                   and fu["role"].strip().lower() == row["role"].strip().lower():
                    for marker in fu["notes"].split(";"):
                        marker = marker.strip()
                        # note format: "YYYY-MM-DD followed up"
                        date_part = marker.split(" ", 1)[0]
                        if "followed up" not in marker:
                            continue
                        try:
                            d = datetime.strptime(date_part, "%Y-%m-%d")
                            if d > last_touch:
                                last_touch = d
                        except (ValueError, IndexError):
                            pass
            if (datetime.utcnow() - last_touch).days >= threshold_days:
                result.append(row)
        return result

    def stats(self) -> Dict[str, Any]:
        rows = self._read_all()
        by_status: Dict[str, int] = {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        return {
            "total": len(rows),
            "by_status": by_status,
            "open": sum(1 for r in rows if r["status"].lower() not in FINAL_STATUSES),
            "final": sum(1 for r in rows if r["status"].lower() in FINAL_STATUSES),
        }
