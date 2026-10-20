"""JobRight-parity Phase 2 — Orion-style 24/7 AI career copilot.

NEW MODULE (additive only). A persistent, context-aware chat assistant that
answers career questions grounded in THIS candidate's real data: their profile,
current job feed, match scores, application pipeline, follow-ups and story bank.
It can also suggest concrete next actions (which map to existing endpoints the
frontend already calls — evaluate, generate-cv, outreach, approve).

Conversations are stored as JSON under data/copilot_history/ — a brand-new
directory; nothing existing is read-modified or overwritten.
"""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("career_copilot")

DEFAULT_HISTORY_DIR = "data/copilot_history"

SYSTEM_PROMPT = """You are Orion, the candidate's personal AI career copilot inside their own \
job-search agent. You have been given a live context pack about the candidate: their \
profile, top job matches with scores, pipeline state, application history, follow-ups \
and their interview story bank.

Your job:
- Answer questions about their job search concretely, using the context pack. Cite \
specific jobs by title/company and their scores when relevant.
- Be direct and practical. Recommend specific next actions (evaluate a job, tailor a CV, \
draft outreach, approve an application, follow up).
- When recommending an action, append an ACTION line in this exact format so the UI can \
render a button: ACTION: <action_key> | <human label>
  Valid action_keys: evaluate_job, generate_cv, outreach, scan, follow_ups, insights.
- Never invent jobs, companies, scores or application statuses that are not in the \
context pack. If the context pack is empty, say what to run first (e.g. a scan).
- Keep answers under 250 words unless the user asks for depth."""

ACTION_KEYS = {
    "evaluate_job",
    "generate_cv",
    "outreach",
    "scan",
    "follow_ups",
    "insights",
    # ai-job-search framework bridge (v2 integration)
    "framework_evaluate",
    "framework_track",
    "framework_outcomes",
}


class CareerCopilot:
    """Stateful chat copilot grounded in the candidate's live data."""

    def __init__(self, llm_client: Any,
                 history_dir: str = DEFAULT_HISTORY_DIR,
                 max_context_messages: int = 12):
        self.llm = llm_client
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.max_context_messages = max_context_messages

    # ---------- context pack (reads only from existing data) ----------

    def build_context_pack(self, candidate_profile: Dict[str, Any],
                           jobs: List[Dict[str, Any]],
                           applications: List[Dict[str, Any]],
                           pipeline_stats: Optional[Dict[str, Any]] = None,
                           followups_due: int = 0) -> str:
        profile = candidate_profile or {}
        skills = profile.get("skills", {}) or {}
        name = str((profile.get("personal_details", {}) or {}).get("name", "the candidate"))
        summary = str((profile.get("narrative", {}) or {}).get("professional_summary", ""))

        top_jobs = sorted(
            jobs or [],
            key=lambda j: float(j.get("score", 0) or 0),
            reverse=True,
        )[:8]
        job_lines = []
        for j in top_jobs:
            job_lines.append(
                f"- {j.get('title', 'Unknown')} @ {j.get('companyName', j.get('company', 'Unknown'))} "
                f"— score {j.get('score', '?')}/100 — id {j.get('id', '?')}"
            )

        app_lines = []
        for a in (applications or [])[:10]:
            app_lines.append(
                f"- {a.get('title', '?')} @ {a.get('company', '?')} — status: {a.get('status', '?')}"
            )

        parts = [
            f"CANDIDATE: {name}",
            f"SUMMARY: {summary[:500]}",
            f"SKILLS (primary): {', '.join(str(s) for s in (skills.get('primary', []) or [])[:15])}",
            f"SKILLS (secondary): {', '.join(str(s) for s in (skills.get('secondary', []) or [])[:15])}",
            f"TOP JOBS IN FEED ({len(jobs or [])} total):",
            *(job_lines if job_lines else ["- (feed empty — suggest running a scan)"]),
            f"APPLICATIONS ({len(applications or [])} tracked):",
            *(app_lines if app_lines else ["- (none yet)"]),
            f"PIPELINE: {json.dumps(pipeline_stats or {})}",
            f"FOLLOW-UPS DUE: {followups_due}",
        ]
        return "\n".join(parts)

    # ---------- history persistence ----------

    def _history_path(self, conversation_id: str) -> Path:
        safe = "".join(c for c in conversation_id if c.isalnum() or c in "-_")
        return self.history_dir / f"{safe or 'default'}.json"

    def load_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        path = self._history_path(conversation_id)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("messages", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def append_history(self, conversation_id: str, role: str, content: str,
                       actions: Optional[List[Dict[str, Any]]] = None) -> None:
        path = self._history_path(conversation_id)
        history = self.load_history(conversation_id)
        history.append({
            "role": role,
            "content": content,
            "actions": actions or [],
            "at": datetime.now(timezone.utc).isoformat(),
        })
        payload = {"conversation_id": conversation_id, "messages": history}
        tmp = str(path) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, str(path))

    # ---------- action parsing ----------

    def _extract_actions(self, text: str) -> tuple:
        """Pull ACTION: lines out of the model reply; return (clean_text, actions)."""
        actions = []
        clean_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("ACTION:"):
                body = stripped[len("ACTION:"):].strip()
                key, _, label = body.partition("|")
                key = key.strip().lower().replace(" ", "_")
                if key in ACTION_KEYS:
                    actions.append({"action_key": key, "label": (label or key).strip()})
                continue
            clean_lines.append(line)
        return "\n".join(clean_lines).strip(), actions

    # ---------- public API ----------

    def chat(self, message: str, conversation_id: str = "default",
             candidate_profile: Dict[str, Any] = None,
             jobs: List[Dict[str, Any]] = None,
             applications: List[Dict[str, Any]] = None,
             pipeline_stats: Optional[Dict[str, Any]] = None,
             followups_due: int = 0) -> Dict[str, Any]:
        history = self.load_history(conversation_id)
        context_pack = self.build_context_pack(
            candidate_profile or {}, jobs or [], applications or [],
            pipeline_stats=pipeline_stats, followups_due=followups_due,
        )

        # recent conversation window (kept small; the pack carries the ground truth)
        recent = history[-self.max_context_messages:]
        conversation_block = "\n".join(
            f"{m.get('role', 'user').upper()}: {str(m.get('content', ''))[:400]}"
            for m in recent
        )

        prompt = (
            f"LIVE CONTEXT PACK:\n{context_pack}\n\n"
            + (f"RECENT CONVERSATION:\n{conversation_block}\n\n" if conversation_block else "")
            + f"USER: {message}\n\n"
            + "Answer as Orion. Include ACTION lines for any concrete next steps."
        )

        try:
            raw_reply = self.llm.complete_for_step(
                "generator", prompt, system=SYSTEM_PROMPT, max_tokens=1024, temperature=0.4
            )
        except Exception as e:
            logger.error(f"[copilot] LLM call failed: {e}")
            raw_reply = (
                "I couldn't reach the language model just now. Your data is intact — "
                "try again in a moment, or use the dashboard actions directly."
            )

        reply, actions = self._extract_actions(raw_reply)

        self.append_history(conversation_id, "user", message)
        self.append_history(conversation_id, "assistant", reply, actions=actions)

        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "actions": actions,
            "message_count": len(self.load_history(conversation_id)),
        }


def get_copilot(llm_client: Any, history_dir: str = DEFAULT_HISTORY_DIR) -> CareerCopilot:
    """Factory used by the /copilot routes."""
    return CareerCopilot(llm_client=llm_client, history_dir=history_dir)
