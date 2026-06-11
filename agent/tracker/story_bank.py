import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class StoryBank:
    """Persistent cross-session STAR+R interview story accumulator."""

    STORY_FIELDS = ["situation", "task", "action", "result", "reflection"]

    def __init__(self, storage_path: str = "data/story_bank.json"):
        self.storage_path = Path(storage_path)
        self.stories: List[Dict[str, Any]] = self._load()

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
            json.dump(self.stories, f, indent=2)
        os.replace(tmp, str(self.storage_path))

    def append(self, story: Dict[str, Any]) -> str:
        for required in ["situation", "task", "action", "result"]:
            if required not in story:
                raise ValueError(f"Missing required STAR field: {required}")

        story.setdefault("reflection", "")
        story.setdefault("archetype", "unknown")
        story.setdefault("tags", [])
        story.setdefault("added_at", datetime.utcnow().isoformat())
        story_id = f"story_{abs(hash(story['situation'] + story['action'])) % 10000000}"
        story["id"] = story_id

        existing_ids = {s.get("id") for s in self.stories}
        if story_id not in existing_ids:
            self.stories.append(story)
            self._save()

        return story_id

    def lookup(self, archetype: Optional[str] = None, tags: Optional[List[str]] = None,
               limit: int = 5) -> List[Dict[str, Any]]:
        results = self.stories[:]

        if archetype:
            results = [s for s in results if s.get("archetype") == archetype]

        if tags:
            results = [
                s for s in results
                if any(t in s.get("tags", []) for t in tags)
            ]

        results.sort(key=lambda s: s.get("added_at", ""), reverse=True)
        return results[:limit]

    def get_by_id(self, story_id: str) -> Optional[Dict[str, Any]]:
        return next((s for s in self.stories if s.get("id") == story_id), None)

    def update(self, story_id: str, updates: Dict[str, Any]) -> bool:
        for i, story in enumerate(self.stories):
            if story.get("id") == story_id:
                self.stories[i].update(updates)
                self.stories[i]["updated_at"] = datetime.utcnow().isoformat()
                self._save()
                return True
        return False

    def delete(self, story_id: str) -> bool:
        original_len = len(self.stories)
        self.stories = [s for s in self.stories if s.get("id") != story_id]
        if len(self.stories) < original_len:
            self._save()
            return True
        return False

    def all(self) -> List[Dict[str, Any]]:
        return self.stories[:]

    def count(self) -> int:
        return len(self.stories)

    def stats(self) -> Dict[str, Any]:
        archetypes: Dict[str, int] = {}
        for story in self.stories:
            arch = story.get("archetype", "unknown")
            archetypes[arch] = archetypes.get(arch, 0) + 1

        return {
            "total": len(self.stories),
            "archetypes": archetypes,
            "with_reflection": sum(1 for s in self.stories if s.get("reflection"))
        }
