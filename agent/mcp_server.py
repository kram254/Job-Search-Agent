from __future__ import annotations

import sys
import json
import re
import logging
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("mcp_server")

try:
    from agent.ranking.quality_gate import QualityGate
    from agent.ranking.feedback_ranker import FeedbackRanker
    from agent.ranking.taxonomy import resolve_canonical, get_category, TECH_TAXONOMY
    _ranking_available = True
except Exception as _e:
    logger.warning(f"Ranking engine unavailable: {_e}")
    _ranking_available = False

try:
    from agent.llm.field_mapper import FieldMapper
    _mapper_available = True
except Exception as _e:
    logger.warning(f"FieldMapper unavailable: {_e}")
    _mapper_available = False

_quality_gate = QualityGate() if _ranking_available else None
_feedback_ranker = FeedbackRanker() if _ranking_available else None

TOOLS = [
    {
        "name": "score_job_fit",
        "description": (
            "Score how well a job description matches a candidate's skills. "
            "Returns a quality gate assessment plus per-skill taxonomy matches."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_description": {"type": "string", "description": "Full job description text"},
                "candidate_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of candidate skill names or aliases"
                }
            },
            "required": ["job_description"]
        }
    },
    {
        "name": "evaluate_lead_quality",
        "description": (
            "Evaluate the quality of a job listing using the quality gate and feedback signals. "
            "Returns pass/fail verdict with penalty breakdown."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing": {
                    "type": "object",
                    "description": "Job listing dict with keys: url, title, company, description, location, date_posted",
                    "properties": {
                        "url":          {"type": "string"},
                        "title":        {"type": "string"},
                        "company":      {"type": "string"},
                        "description":  {"type": "string"},
                        "location":     {"type": "string"},
                        "date_posted":  {"type": "string"}
                    },
                    "required": ["description"]
                }
            },
            "required": ["listing"]
        }
    },
    {
        "name": "extract_lead_intel",
        "description": (
            "Extract structured intelligence from a job description: "
            "canonical skill stack, seniority years, location type, "
            "salary range, and urgency signals."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_description": {"type": "string", "description": "Full job description text"}
            },
            "required": ["job_description"]
        }
    }
]


_SHORT_TERM_MIN_LEN = 8


def _word_boundary_match(term: str, text: str) -> bool:
    import re as _re
    if len(term) >= _SHORT_TERM_MIN_LEN:
        return term in text
    pattern = r'(?<![a-z0-9])' + _re.escape(term) + r'(?![a-z0-9])'
    return bool(_re.search(pattern, text, _re.IGNORECASE))


def _extract_stack(text: str) -> List[str]:
    if not _ranking_available:
        return []
    text_lower = text.lower()
    found = []
    for canonical, (aliases, _cat) in TECH_TAXONOMY.items():
        if _word_boundary_match(canonical, text_lower):
            found.append(canonical)
            continue
        for alias in aliases:
            if _word_boundary_match(alias, text_lower):
                found.append(canonical)
                break
    return sorted(set(found))


def _extract_seniority_years(text: str) -> Optional[int]:
    patterns = [
        r"(\d+)\+?\s*years?\s+of\s+(?:experience|exp)",
        r"(\d+)\+?\s*years?\s+(?:experience|exp)",
        r"minimum\s+(\d+)\s+years?",
        r"at\s+least\s+(\d+)\s+years?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def _extract_location_type(text: str) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in ("fully remote", "100% remote", "remote-first", "work from anywhere")):
        return "fully_remote"
    if any(k in text_lower for k in ("remote", "work from home")):
        return "remote_ok"
    if any(k in text_lower for k in ("hybrid", "partially remote")):
        return "hybrid"
    if any(k in text_lower for k in ("onsite", "on-site", "in-office", "in office")):
        return "onsite"
    return "unspecified"


def _extract_salary(text: str) -> Optional[str]:
    patterns = [
        r"\$(\d[\d,]*)[kK]?\s*[-–—]\s*\$?(\d[\d,]*)[kK]?(?:\s*/\s*(?:yr|year|annual))?",
        r"up to \$(\d[\d,]*)[kK]?",
        r"salary[:\s]+\$(\d[\d,]*)[kK]?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def _extract_urgency(text: str) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in ("asap", "immediate", "immediately", "urgent", "start immediately")):
        return "high"
    if any(k in text_lower for k in ("rolling", "open until filled")):
        return "low"
    return "normal"


def _handle_score_job_fit(params: Dict[str, Any]) -> Dict[str, Any]:
    jd = params.get("job_description", "")
    candidate_skills: List[str] = params.get("candidate_skills", [])

    stack = _extract_stack(jd)

    resolved_candidate: List[str] = []
    if _ranking_available:
        for skill in candidate_skills:
            canonical = resolve_canonical(skill)
            if canonical:
                resolved_candidate.append(canonical)

    resolved_candidate_set = list(dict.fromkeys(resolved_candidate))
    matched = [s for s in resolved_candidate_set if s in stack]
    missing = [s for s in stack if s not in resolved_candidate_set]

    quality: Dict[str, Any] = {}
    if _quality_gate:
        listing = {"description": jd, "title": params.get("title", ""), "url": ""}
        quality = _quality_gate.evaluate(listing)

    return {
        "jd_stack":          stack,
        "candidate_skills":  resolved_candidate_set,
        "matched_skills":    matched,
        "missing_skills":    missing,
        "match_ratio":       round(len(matched) / max(len(stack), 1), 3),
        "quality_gate":      quality,
    }


def _handle_evaluate_lead_quality(params: Dict[str, Any]) -> Dict[str, Any]:
    listing: Dict[str, Any] = params.get("listing", {})

    quality: Dict[str, Any] = {}
    feedback_delta: float = 0.0

    if _quality_gate:
        quality = _quality_gate.evaluate(listing)
    if _feedback_ranker:
        feedback_delta = _feedback_ranker.score_listing(listing)

    return {
        "quality_gate":     quality,
        "feedback_delta":   round(feedback_delta, 3),
        "adjusted_score":   round(quality.get("final_score", 0) + feedback_delta, 3),
        "verdict":          "PASS" if quality.get("passes", False) else "FAIL",
    }


def _handle_extract_lead_intel(params: Dict[str, Any]) -> Dict[str, Any]:
    jd = params.get("job_description", "")
    return {
        "stack":           _extract_stack(jd),
        "seniority_years": _extract_seniority_years(jd),
        "location_type":   _extract_location_type(jd),
        "salary_range":    _extract_salary(jd),
        "urgency":         _extract_urgency(jd),
    }


def _dispatch_tool(name: str, params: Dict[str, Any]) -> Any:
    if name == "score_job_fit":
        return _handle_score_job_fit(params)
    if name == "evaluate_lead_quality":
        return _handle_evaluate_lead_quality(params)
    if name == "extract_lead_intel":
        return _handle_extract_lead_intel(params)
    raise ValueError(f"Unknown tool: {name}")


def _send(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "job-search-mcp", "version": "1.0.0"}
            }
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = _dispatch_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                    "isError": False
                }
            }
        except Exception as e:
            return _error_response(req_id, -32603, str(e))

    if method == "notifications/initialized":
        return None

    return _error_response(req_id, -32601, f"Method not found: {method}")


def run() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send(_error_response(None, -32700, f"Parse error: {e}"))
            continue
        response = _handle_request(req)
        if response is not None:
            _send(response)


if __name__ == "__main__":
    run()
