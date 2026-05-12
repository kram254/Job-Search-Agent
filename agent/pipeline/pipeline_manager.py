import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class PipelineManager:
    """URL queue manager for bulk job processing."""

    def __init__(self, pipeline_path: str = "data/pipeline.json"):
        self.pipeline_path = Path(pipeline_path)
        self.entries: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.pipeline_path.exists():
            return []
        try:
            with open(self.pipeline_path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self) -> None:
        self.pipeline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pipeline_path, "w") as f:
            json.dump(self.entries, f, indent=2)

    def add(self, url: str, title: str = "", company: str = "",
            priority: int = 0, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry_id = f"pl_{abs(hash(url)) % 10000000000}"

        for entry in self.entries:
            if entry.get("url") == url:
                return entry.get("id", entry_id)

        entry = {
            "id": entry_id,
            "url": url,
            "title": title,
            "company": company,
            "priority": priority,
            "status": "pending",
            "added_at": datetime.utcnow().isoformat(),
            "processed_at": None,
            "metadata": metadata or {}
        }
        self.entries.append(entry)
        self._save()
        return entry_id

    def add_batch(self, items: List[Dict[str, Any]]) -> List[str]:
        ids = []
        for item in items:
            entry_id = self.add(
                url=item.get("url", ""),
                title=item.get("title", ""),
                company=item.get("company", ""),
                priority=item.get("priority", 0),
                metadata=item.get("metadata")
            )
            ids.append(entry_id)
        return ids

    def get_pending(self, limit: int = 20) -> List[Dict[str, Any]]:
        pending = [e for e in self.entries if e.get("status") == "pending"]
        pending.sort(key=lambda e: (-e.get("priority", 0), e.get("added_at", "")))
        return pending[:limit]

    def mark_processing(self, entry_id: str) -> bool:
        return self._set_status(entry_id, "processing")

    def mark_done(self, entry_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        for entry in self.entries:
            if entry.get("id") == entry_id:
                entry["status"] = "done"
                entry["processed_at"] = datetime.utcnow().isoformat()
                if result:
                    entry["result"] = result
                self._save()
                return True
        return False

    def mark_failed(self, entry_id: str, error: str = "") -> bool:
        for entry in self.entries:
            if entry.get("id") == entry_id:
                entry["status"] = "failed"
                entry["error"] = error
                entry["processed_at"] = datetime.utcnow().isoformat()
                self._save()
                return True
        return False

    def _set_status(self, entry_id: str, status: str) -> bool:
        for entry in self.entries:
            if entry.get("id") == entry_id:
                entry["status"] = status
                self._save()
                return True
        return False

    def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        return next((e for e in self.entries if e.get("id") == entry_id), None)

    def all(self) -> List[Dict[str, Any]]:
        return self.entries[:]

    def stats(self) -> Dict[str, Any]:
        statuses: Dict[str, int] = {}
        for entry in self.entries:
            s = entry.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "total": len(self.entries),
            "by_status": statuses,
            "pending": statuses.get("pending", 0),
            "processing": statuses.get("processing", 0),
            "done": statuses.get("done", 0),
            "failed": statuses.get("failed", 0)
        }

    def reset_failed(self) -> int:
        count = 0
        for entry in self.entries:
            if entry.get("status") == "failed":
                entry["status"] = "pending"
                entry.pop("error", None)
                count += 1
        if count:
            self._save()
        return count

    def clear_done(self) -> int:
        original = len(self.entries)
        self.entries = [e for e in self.entries if e.get("status") != "done"]
        removed = original - len(self.entries)
        if removed:
            self._save()
        return removed
