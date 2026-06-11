import json
import os
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed


class BatchProcessor:
    """Stateful resumable parallel job evaluator with state file persistence."""

    def __init__(self, state_path: str = "data/batch_state.json",
                 max_workers: int = 4):
        self.state_path = Path(state_path)
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "batch_id": None,
            "started_at": None,
            "completed_at": None,
            "status": "idle",
            "total": 0,
            "processed": 0,
            "failed": 0,
            "results": {}
        }

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            tmp = str(self.state_path) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.state, f, indent=2)
            os.replace(tmp, str(self.state_path))

    def start_batch(self, items: List[Dict[str, Any]], batch_id: Optional[str] = None) -> str:
        bid = batch_id or f"batch_{abs(hash(str(items[:1]))) % 10000000}_{int(datetime.utcnow().timestamp())}"
        self.state = {
            "batch_id": bid,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "status": "running",
            "total": len(items),
            "processed": 0,
            "failed": 0,
            "results": {}
        }
        self._save_state()
        return bid

    def process(self, items: List[Dict[str, Any]],
                processor_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
                batch_id: Optional[str] = None,
                resume: bool = True) -> Dict[str, Any]:
        prior_results = dict(self.state.get("results", {})) if resume else {}
        bid = self.start_batch(items, batch_id)
        if resume and prior_results:
            self.state["results"] = prior_results
        already_done = set(self.state.get("results", {}).keys()) if resume else set()

        pending = [item for item in items if str(item.get("id", "")) not in already_done]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(self._safe_process, processor_fn, item): item
                for item in pending
            }

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                item_id = str(item.get("id", id(item)))
                try:
                    result = future.result()
                    with self._lock:
                        self.state["results"][item_id] = result
                        self.state["processed"] += 1
                        tmp = str(self.state_path) + ".tmp"
                        with open(tmp, "w") as _f:
                            json.dump(self.state, _f, indent=2)
                        os.replace(tmp, str(self.state_path))
                except Exception as e:
                    with self._lock:
                        self.state["results"][item_id] = {"error": str(e), "status": "failed"}
                        self.state["failed"] += 1
                        tmp = str(self.state_path) + ".tmp"
                        with open(tmp, "w") as _f:
                            json.dump(self.state, _f, indent=2)
                        os.replace(tmp, str(self.state_path))

        self.state["status"] = "completed"
        self.state["completed_at"] = datetime.utcnow().isoformat()
        self._save_state()

        return self.get_summary()

    def _safe_process(self, fn: Callable, item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = fn(item)
            return {"status": "ok", "result": result, "processed_at": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"status": "failed", "error": str(e), "processed_at": datetime.utcnow().isoformat()}

    def get_summary(self) -> Dict[str, Any]:
        return {
            "batch_id": self.state.get("batch_id"),
            "status": self.state.get("status"),
            "total": self.state.get("total", 0),
            "processed": self.state.get("processed", 0),
            "failed": self.state.get("failed", 0),
            "started_at": self.state.get("started_at"),
            "completed_at": self.state.get("completed_at"),
            "results_count": len(self.state.get("results", {}))
        }

    def get_results(self) -> Dict[str, Any]:
        return self.state.get("results", {})

    def is_running(self) -> bool:
        return self.state.get("status") == "running"

    def reset(self) -> None:
        self.state = self._load_state()
        self.state["status"] = "idle"
        self._save_state()
