import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


class ScanScheduler:

    def __init__(self, schedule_path: str = "data/schedule.json"):
        self.schedule_path = Path(schedule_path)
        self._schedules: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self.schedule_path.exists():
            try:
                with open(self.schedule_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.schedule_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.schedule_path, "w", encoding="utf-8") as f:
            json.dump(self._schedules, f, indent=2)

    def add_schedule(self, cv_path: str, interval_days: int = 2,
                     role_keywords: Optional[List[str]] = None,
                     config_path: str = "config/portals.yml",
                     label: str = "") -> str:
        schedule_id = str(uuid.uuid4())[:8]
        entry = {
            "id": schedule_id,
            "cv_path": cv_path,
            "interval_days": interval_days,
            "role_keywords": role_keywords or [],
            "config_path": config_path,
            "label": label or f"scan-{schedule_id}",
            "created_at": datetime.utcnow().isoformat(),
            "last_run": None,
            "next_run": datetime.utcnow().isoformat(),
            "run_count": 0,
            "status": "active"
        }
        self._schedules.append(entry)
        self._save()
        return schedule_id

    def get_schedules(self) -> List[Dict[str, Any]]:
        return list(self._schedules)

    def get_due(self) -> List[Dict[str, Any]]:
        now = datetime.utcnow()
        due = []
        for s in self._schedules:
            if s.get("status") != "active":
                continue
            next_run = s.get("next_run")
            if next_run is None:
                due.append(s)
                continue
            try:
                if now >= datetime.fromisoformat(next_run):
                    due.append(s)
            except Exception:
                due.append(s)
        return due

    def mark_ran(self, schedule_id: str) -> None:
        now = datetime.utcnow()
        for s in self._schedules:
            if s["id"] == schedule_id:
                s["last_run"] = now.isoformat()
                s["run_count"] = s.get("run_count", 0) + 1
                s["next_run"] = (now + timedelta(days=s.get("interval_days", 2))).isoformat()
                break
        self._save()

    def remove(self, schedule_id: str) -> bool:
        before = len(self._schedules)
        self._schedules = [s for s in self._schedules if s["id"] != schedule_id]
        self._save()
        return len(self._schedules) < before

    def pause(self, schedule_id: str) -> bool:
        for s in self._schedules:
            if s["id"] == schedule_id:
                s["status"] = "paused"
                self._save()
                return True
        return False

    def resume(self, schedule_id: str) -> bool:
        for s in self._schedules:
            if s["id"] == schedule_id:
                s["status"] = "active"
                self._save()
                return True
        return False

    def run_due(self, candidate_profile: dict, jobs_raw_path: str) -> List[Dict[str, Any]]:
        due = self.get_due()
        results = []
        for schedule in due:
            try:
                result = self._run_schedule(schedule, candidate_profile, jobs_raw_path)
                self.mark_ran(schedule["id"])
                results.append({"schedule_id": schedule["id"], "status": "ran", "result": result})
            except Exception as exc:
                logging.exception(f"[ScanScheduler] Error running schedule {schedule['id']}: {exc}")
                results.append({"schedule_id": schedule["id"], "status": "error", "error": str(exc)})
        return results

    def _run_schedule(self, schedule: dict, candidate_profile: dict, jobs_raw_path: str) -> Dict[str, Any]:
        from agent.llm.field_mapper import FieldMapper
        from agent.scanner.portal_scanner import PortalScanner
        from agent.browser.playwright_wrapper import BrowserWrapper
        import asyncio

        cv_path = schedule.get("cv_path", "")
        role_keywords = list(schedule.get("role_keywords", []))
        config_path = schedule.get("config_path", "config/portals.yml")

        cv_text = ""
        if cv_path and Path(cv_path).exists():
            try:
                with open(cv_path, "r", encoding="utf-8") as f:
                    cv_text = f.read()
            except Exception:
                pass

        if not role_keywords:
            try:
                mapper = FieldMapper(
                    candidate_profile=candidate_profile,
                    job_description="",
                    cv_text=cv_text
                )
                evaluation = mapper.evaluate_job()
                role_keywords = mapper._get_archetype_keywords(evaluation.archetype)
            except Exception as e:
                logging.warning(f"[ScanScheduler] CV analysis failed: {e}")

        browser = BrowserWrapper(headless=True)
        browser.launch(headless=True)
        try:
            scanner = PortalScanner(
                browser=browser,
                config_path=config_path,
                history_path="data/scan_history.json"
            )
            scan_result = asyncio.run(scanner.run_full_scan())
            scanner.export_to_jobs_raw(scan_result, jobs_raw_path)
            return {
                "total_found": scan_result.total_found,
                "added_to_pipeline": scan_result.added_to_pipeline,
                "filtered_out": scan_result.filtered_out,
                "duration_seconds": scan_result.scan_duration_seconds,
                "role_keywords_used": role_keywords
            }
        finally:
            browser.close()
