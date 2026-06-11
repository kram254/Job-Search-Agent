from __future__ import annotations

import logging
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

logger = logging.getLogger("cv_selector")

try:
    from agent.mcp_server import _extract_stack
    _stack_available = True
except Exception:
    _stack_available = False


def _variant_skill_overlap(variant: Dict[str, Any], jd_stack: List[str]) -> float:
    tags = set(t.lower() for t in variant.get("focus_tags", []))
    jd_set = set(s.lower() for s in jd_stack)
    if not tags or not jd_set:
        return 0.0
    return len(tags & jd_set) / max(len(jd_set), 1)


def select_cv_variant(
    candidate_profile: Dict[str, Any],
    archetype: str = "unknown",
    job_description: str = "",
) -> Dict[str, Any]:
    variants: List[Dict[str, Any]] = (
        candidate_profile.get("cv_variants", {}).get("variants", [])
    )

    if not variants:
        pdf_paths = candidate_profile.get("cv_variants", {}).get("pdf_paths", [])
        md_paths = candidate_profile.get("cv_variants", {}).get("paths", [])
        fallback_pdf = pdf_paths[0] if pdf_paths else ""
        fallback_md = md_paths[0] if md_paths else ""
        return {"pdf_path": fallback_pdf, "md_path": fallback_md, "id": "fallback", "label": "Default CV"}

    jd_stack: List[str] = []
    if job_description and _stack_available:
        try:
            jd_stack = _extract_stack(job_description)
        except Exception:
            pass

    scored: List[tuple] = []
    for v in variants:
        archetype_score = 2.0 if archetype in v.get("archetypes", []) else 0.0
        skill_score = _variant_skill_overlap(v, jd_stack) * 3.0
        pdf_exists = Path(v.get("pdf_path", "")).exists()
        md_exists = Path(v.get("md_path", "")).exists()
        if not pdf_exists and not md_exists:
            continue
        total = archetype_score + skill_score
        scored.append((total, v))

    if not scored:
        scored = [(0.0, v) for v in variants]

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    logger.info(
        f"[CVSelector] Selected '{best.get('label')}' for archetype={archetype} "
        f"(score={scored[0][0]:.2f})"
    )
    return best
