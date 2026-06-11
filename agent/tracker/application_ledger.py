from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ApplicationLedger:

    def __init__(self, ledger_path: str = "data/applications.json"):
        self._path = Path(ledger_path)
        self._records: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(self._path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2)
        os.replace(tmp, str(self._path))

    def _normalize_url(self, url: str) -> str:
        return url.split("?")[0].rstrip("/").lower()

    def already_applied(self, url: str, company: str = "", title: str = "") -> bool:
        norm = self._normalize_url(url)
        for rec in self._records:
            if self._normalize_url(rec.get("url", "")) == norm:
                return True
            if company and title:
                if (rec.get("company", "").lower() == company.lower() and
                        rec.get("title", "").lower() == title.lower()):
                    return True
        return False

    def record(
        self,
        url: str,
        job_id: str = "",
        company: str = "",
        title: str = "",
        archetype: str = "",
        cv_used: str = "",
        session_id: str = "",
        status: str = "applied",
    ) -> str:
        record_id = f"app_{abs(hash(url + company)) % 10000000000}"
        self._records.append({
            "id": record_id,
            "url": url,
            "job_id": job_id,
            "company": company,
            "title": title,
            "archetype": archetype,
            "cv_used": cv_used,
            "session_id": session_id,
            "status": status,
            "applied_at": datetime.utcnow().isoformat(),
        })
        self._save()
        return record_id

    def update_status(self, record_id: str, status: str) -> bool:
        for rec in self._records:
            if rec.get("id") == record_id:
                rec["status"] = status
                rec["updated_at"] = datetime.utcnow().isoformat()
                self._save()
                return True
        return False

    def all(self) -> List[Dict[str, Any]]:
        return list(self._records)

    def stats(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for rec in self._records:
            s = rec.get("status", "applied")
            by_status[s] = by_status.get(s, 0) + 1
        return {"total": len(self._records), "by_status": by_status}
