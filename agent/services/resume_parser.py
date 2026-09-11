"""JobRight-parity Phase 4 — Resume import & profile onboarding.

NEW MODULE (additive only). Accepts an uploaded CV (markdown/text/pdf/docx),
extracts a structured profile via the existing LLM client, and produces a
MERGE PROPOSAL against data/candidate_profile.json. The proposal never touches
the real profile until the user confirms per-field; a timestamped backup is
written before any confirmed merge is applied.
"""
from __future__ import annotations

import json
import os
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("resume_parser")

BACKUP_DIR = "data/profile_backups"
ALLOWED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf", ".docx"}


class ResumeParseError(Exception):
    pass


class ResumeParser:
    def __init__(self, llm_client: Any, profile_path: str = "data/candidate_profile.json"):
        self.llm = llm_client
        self.profile_path = Path(profile_path)

    # ---------- text extraction ----------

    def extract_text(self, file_path: str, filename: str = "") -> str:
        suffix = Path(filename or file_path).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ResumeParseError(f"Unsupported file type: {suffix}. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

        if suffix in (".md", ".markdown", ".txt"):
            return Path(file_path).read_text(encoding="utf-8", errors="replace")

        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # optional dependency
            except ImportError:
                try:
                    from PyPDF2 import PdfReader  # older name
                except ImportError:
                    raise ResumeParseError(
                        "PDF parsing needs the 'pypdf' package (pip install pypdf). "
                        "Tip: markdown CVs parse best."
                    )
            reader = PdfReader(file_path)
            return "\n".join((page.extract_text() or "") for page in reader.pages)

        if suffix == ".docx":
            try:
                import docx  # python-docx, optional dependency
            except ImportError:
                raise ResumeParseError("DOCX parsing needs the 'python-docx' package (pip install python-docx).")
            document = docx.Document(file_path)
            return "\n".join(p.text for p in document.paragraphs if p.text.strip())

        raise ResumeParseError(f"Unhandled extension: {suffix}")

    # ---------- LLM extraction ----------

    def parse_profile(self, cv_text: str) -> Dict[str, Any]:
        system = (
            "You are a precise resume-to-JSON extractor. From the CV text, produce ONLY a JSON "
            "object with these keys (use null or [] when a field is not present — never invent): "
            "personal_details {name, email, phone, nationality, location}, "
            "professional_summary (string, <=80 words), "
            "skills {primary: [..max 12..], secondary: [..max 12..]}, "
            "education [{degree, institution, years}], "
            "projects [{name, description (<=40 words), technologies: [..]}], "
            "narrative {positioning (<=30 words)}. "
            "No markdown fences, no commentary — JSON only."
        )
        prompt = f"CV TEXT (may be truncated):\n{cv_text[:12000]}"
        raw = self.llm.complete_for_step("ingestor", prompt, system=system, max_tokens=2000, temperature=0.1)
        # tolerate stray fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1].lstrip("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ResumeParseError(f"Model did not return valid JSON: {e}")

    # ---------- merge proposal ----------

    MERGEABLE_KEYS = ["personal_details", "professional_summary", "skills", "education",
                      "projects", "narrative"]

    def propose_merge(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Diff a parsed profile against the current one. Never mutates anything."""
        current: Dict[str, Any] = {}
        if self.profile_path.exists():
            with open(self.profile_path) as f:
                current = json.load(f)

        changes: List[Dict[str, Any]] = []
        for key in self.MERGEABLE_KEYS:
            new_value = parsed.get(key)
            if new_value in (None, "", [], {}):
                continue
            old_value = current.get(key)
            if key == "skills" and isinstance(new_value, dict):
                new_primary = new_value.get("primary", []) or []
                old_primary = (old_value or {}).get("primary", []) or []
                if new_primary and new_primary != old_primary:
                    added = [s for s in new_primary if s not in old_primary]
                    removed = [s for s in old_primary if s not in new_primary]
                    changes.append({
                        "key": "skills.primary",
                        "action": "merge",
                        "current": old_primary,
                        "proposed": new_primary,
                        "added": added,
                        "removed": removed,
                    })
                continue
            if key == "narrative" and isinstance(new_value, dict):
                for sub_key, sub_value in new_value.items():
                    if sub_value and sub_value != (old_value or {}).get(sub_key):
                        changes.append({
                            "key": f"narrative.{sub_key}",
                            "action": "update",
                            "current": (old_value or {}).get(sub_key, ""),
                            "proposed": sub_value,
                        })
                continue
            if new_value != old_value:
                changes.append({
                    "key": key,
                    "action": "update",
                    "current": old_value,
                    "proposed": new_value,
                })

        return {
            "changes": changes,
            "change_count": len(changes),
            "profile_path": str(self.profile_path),
            "proposed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ---------- confirmed merge ----------

    def apply_merge(self, parsed: Dict[str, Any], change_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Apply ONLY the selected change keys, after writing a timestamped backup.

        A change key like 'narrative.positioning' targets a sub-field; top-level
        keys apply wholesale. If change_keys is None, all proposed changes apply.
        """
        if not self.profile_path.exists():
            raise ResumeParseError(f"Profile file not found: {self.profile_path}")

        with open(self.profile_path) as f:
            current = json.load(f)

        # timestamped backup — the user's data is never overwritten without a copy
        backup_dir = Path(BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"candidate_profile_{stamp}.json"
        shutil.copy2(str(self.profile_path), str(backup_path))

        applied = []
        for change_key in (change_keys or self.MERGEABLE_KEYS):
            new_value = parsed.get(change_key.split(".")[0])
            if new_value in (None, "", [], {}):
                continue

            if change_key == "skills.primary" and isinstance(new_value, dict):
                proposed = new_value.get("primary", []) or []
                if proposed:
                    current.setdefault("skills", {})["primary"] = proposed
                    applied.append("skills.primary")
                continue

            if change_key == "skills" and isinstance(new_value, dict):
                skills_section = current.setdefault("skills", {})
                if new_value.get("primary"):
                    skills_section["primary"] = new_value["primary"]
                    applied.append("skills.primary")
                if new_value.get("secondary"):
                    skills_section["secondary"] = new_value["secondary"]
                    applied.append("skills.secondary")
                continue

            if change_key.startswith("narrative.") and isinstance(new_value, dict):
                sub_key = change_key.split(".", 1)[1]
                if new_value.get(sub_key):
                    current.setdefault("narrative", {})[sub_key] = new_value[sub_key]
                    applied.append(change_key)
                continue

            if change_key == "narrative" and isinstance(new_value, dict):
                narrative_section = current.setdefault("narrative", {})
                for sub_key, sub_value in new_value.items():
                    if sub_value:
                        narrative_section[sub_key] = sub_value
                        applied.append(f"narrative.{sub_key}")
                continue

            if change_key in ("personal_details", "education", "projects"):
                if change_key == "personal_details" and isinstance(new_value, dict):
                    details = current.setdefault("personal_details", {})
                    for sub_key, sub_value in new_value.items():
                        if sub_value and not details.get(sub_key):
                            details[sub_key] = sub_value  # fill-only: never clobber existing details
                    applied.append("personal_details")
                elif change_key == "education" and isinstance(new_value, list) and new_value:
                    current["education"] = new_value
                    applied.append("education")
                elif change_key == "projects" and isinstance(new_value, list) and new_value:
                    current["projects"] = new_value
                    applied.append("projects")
                continue

            if change_key == "professional_summary" and new_value:
                current.setdefault("narrative", {})["professional_summary"] = new_value
                applied.append("professional_summary")

        with open(self.profile_path, "w") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

        return {
            "applied": applied,
            "backup_path": str(backup_path),
            "applied_count": len(applied),
        }


def parse_resume_file(llm_client: Any, file_path: str, filename: str = "",
                      profile_path: str = "data/candidate_profile.json") -> Dict[str, Any]:
    """Convenience wrapper used by the /profile/import route."""
    parser = ResumeParser(llm_client=llm_client, profile_path=profile_path)
    text = parser.extract_text(file_path, filename)
    if not text.strip():
        raise ResumeParseError("Extracted no text from the file — is it a valid CV?")
    parsed = parser.parse_profile(text)
    proposal = parser.propose_merge(parsed)
    proposal["parsed"] = parsed  # kept for the confirm step
    return proposal
