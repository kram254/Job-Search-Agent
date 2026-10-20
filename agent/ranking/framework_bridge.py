"""AI-Job-Search framework bridge — integrates the MadsLorentzen framework's
disciplined evaluation methodology into the Job-Search-Agent app.

NEW MODULE (additive only). Ports the framework's core gates and scoring:
  - posting integrity gate   (posting_guard methodology)
  - eligibility gate         (citizenship/clearance hard stops)
  - language gate            (PASS/FLAG/FAIL vs declared languages)
  - 5-dimension scoring      (technical, experience, behavioral, location,
                              career) with weighted overall + verdict bands

The LLM does the semantic work (reading the posting); this module enforces the
STRUCTURE: gate order, score bands, verdict mapping, and honest reporting.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional

# Verdict bands from the framework's evaluation doc
VERDICT_BANDS = [
    (85, "Strong Fit"),
    (70, "Good Fit"),
    (55, "Moderate Fit"),
    (40, "Weak Fit"),
    (0, "Poor Fit"),
]

# Dimension weights (framework default; location is pass/fail, salary optional)
DIMENSION_WEIGHTS = {
    "technical_skills": 0.30,
    "experience_match": 0.25,
    "behavioral_culture": 0.20,
    "career_alignment": 0.25,
}

INSTRUCTION_SHAPED = re.compile(
    r"(?i)^(ignore (all )?previous|disregard (all )?prior|you are now|"
    r"as an ai (language )?model|system:|assistant:|forget (everything|all)|"
    r"reveal (your )?(prompt|instructions)|print (your )?(prompt|instructions))"
)

HIDDEN_PATTERNS = [
    ("display:none", re.compile(r"display\s*:\s*none", re.I)),
    ("visibility:hidden", re.compile(r"visibility\s*:\s*hidden", re.I)),
    ("opacity:0", re.compile(r"opacity\s*:\s*0(?![.\d])", re.I)),
    ("font-size:0", re.compile(r"font-size\s*:\s*0(?![.\d])", re.I)),
    ("aria-hidden", re.compile(r"aria-hidden\s*=\s*[\"']?true", re.I)),
]


def gate_posting(text: str) -> Dict[str, Any]:
    """Integrity gate: scan a posting for manipulation patterns (the
    posting_guard methodology, in-app port). Returns verdict + findings."""
    findings: List[str] = []
    t = str(text or "")
    for name, pattern in HIDDEN_PATTERNS:
        if pattern.search(t):
            findings.append(f"hidden_style:{name}")
    invisible = sum(t.count(c) for c in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad", "\u2060"))
    if invisible:
        findings.append(f"invisible_chars:{invisible}")
    instruction_lines = []
    for line in t.splitlines():
        s = line.strip()
        if len(s) < 80 and INSTRUCTION_SHAPED.search(s):
            instruction_lines.append(s[:60])
    if instruction_lines:
        findings.append("instruction_shaped_lines:" + "; ".join(instruction_lines[:3]))
    url_m = re.findall(r"https?://\S+", t)
    clean = re.sub(r"<[^>]+>", " ", t)
    # mojibake quick check
    mojibake = len(re.findall(r"Ã‚|Ã¢|ÂÂ", clean))
    if mojibake > 2:
        findings.append(f"mojibake_runs:{mojibake}")

    # instruction-shaped lines are the targeting signal -> warning verdict
    verdict = "warn" if (instruction_lines or any("invisible" in f for f in findings)) else "clean"
    return {
        "verdict": verdict,
        "findings": findings,
        "urls_found": len(url_m),
        "chars": len(clean),
    }


def eligibility_gate(text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Hard-stop gates from the framework: citizenship/clearance requirements
    the candidate cannot satisfy. Silence = proceed, marked unverified."""
    t = str(text or "").lower()
    nationality = str((profile.get("personal_details", {}) or {}).get("nationality", "")).lower()
    kenyan = "kenya" in nationality

    hard_stops = [
        ("us_citizen", r"(?i)\b(must be a )?u\.?s\.? citizen\b"),
        ("clearance", r"(?i)\b(security clearance( required|\s*required)?)\b"),
        ("pr_requirement", r"(?i)\b(permanent residen(t|cy) (requirement|only|status required))\b"),
        ("eu_only", r"(?i)\b(right to work in the (eu|uk))(?!.*welcome)"),
    ]
    for label, pattern in hard_stops:
        m = re.search(pattern, t)
        if m and not (label == "pr_requirement" and "visa sponsorship" in t):
            return {"pass": False, "reason": f"eligibility:{label}", "quoted": m.group(0)}

    # explicit welcome overrides silence
    if re.search(r"(?i)(international applicants welcome|visa holders considered|we sponsor)", t):
        return {"pass": True, "verified": True}
    return {"pass": True, "verified": False, "note": "posting silent on eligibility — unverified"}


def language_gate(text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Framework language gate: job-condition language requirements vs the
    candidate's declared languages. English-only candidate defaults: postings
    demanding only English pass; other named languages FLAG for review."""
    t = str(text or "").lower()
    declared = {"english"}  # from profile: English-speaking (Kenya, educated in English)
    for lang in ("spanish", "french", "german", "arabic", "swahili", "polish", "russian", "mandarin", "chinese"):
        if lang in str((profile.get("personal_details", {}) or {}).get("languages", "")):
            declared.add(lang)

    required = []
    for lang in ("french", "german", "arabic", "spanish", "mandarin", "chinese", "polish", "russian", "dutch", "swedish", "danish", "norwegian"):
        if re.search(rf"(?i)\b(fluent|native|business[- ]level|proficient)?\s*{lang}\b", t) \
           and re.search(rf"(?i){lang}\s*(required|must|essential)", t):
            required.append(lang)
    if not required:
        return {"verdict": "PASS", "note": "no non-English job-condition language requirement detected"}
    missing = [r for r in required if r not in declared]
    if missing:
        return {
            "verdict": "FAIL",
            "note": f"requires {', '.join(missing)} as a job condition; not in your declared languages",
            "quoted": f"requires: {', '.join(required)}",
        }
    return {"verdict": "FLAG", "note": f"requires {', '.join(required)} — verify your level vs the stated bar"}


def score_dimensions(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Map the LLM's per-dimension 0-100 scores onto the framework's weighted
    overall + verdict band. Expects an evaluation dict with numeric values for
    technical_skills, experience_match, behavioral_culture, career_alignment;
    location_pass (bool); location_notes (str)."""
    dims = {}
    for key, weight in DIMENSION_WEIGHTS.items():
        try:
            value = float(evaluation.get(key))
        except (TypeError, ValueError):
            return {"error": f"missing or non-numeric dimension: {key}"}
        if not 0 <= value <= 100:
            return {"error": f"dimension out of range: {key}={value}"}
        dims[key] = {"score": value, "weight": weight}
    location_pass = bool(evaluation.get("location_pass", True))

    overall = round(sum(d["score"] * d["weight"] for d in dims.values()), 1)
    if not location_pass:
        overall = round(overall * 0.5, 1)  # framework: relocation deal-breaker halves it
        location_note = evaluation.get("location_notes", "")
    else:
        location_note = evaluation.get("location_notes", "")

    verdict = next(label for floor, label in VERDICT_BANDS if overall >= floor)
    return {
        "overall_score": overall,
        "verdict": verdict,
        "location_pass": location_pass,
        "location_notes": location_note,
        "dimensions": {k: v["score"] for k, v in dims.items()},
        "weights": DIMENSION_WEIGHTS,
    }


def full_framework_evaluation(job_text: str, profile: Dict[str, Any],
                              llm_evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """The complete bridge: gates first, then dimensions. Returns the
    framework's evaluation shape (gates + scores + verdict + recommendation
    inputs). llm_evaluation supplies the 4 numeric dimension scores + location
    verdict; this function owns gates, weighting, bands, and honesty notes."""
    posting_gate = gate_posting(job_text)
    elig = eligibility_gate(job_text, profile)
    lang = language_gate(job_text, profile)

    if not elig["pass"]:
        return {
            "gate_blocked": True,
            "gate": "eligibility",
            "reason": elig.get("reason"),
            "quoted": elig.get("quoted"),
            "posting_gate": posting_gate,
        }
    if lang["verdict"] == "FAIL":
        return {
            "gate_blocked": True,
            "gate": "language",
            "reason": lang.get("note"),
            "quoted": lang.get("quoted"),
            "posting_gate": posting_gate,
        }

    scored = score_dimensions(llm_evaluation)
    if "error" in scored:
        return {"gate_blocked": False, "error": scored["error"], "posting_gate": posting_gate}

    return {
        "gate_blocked": False,
        "posting_gate": posting_gate,
        "eligibility": elig,
        "language_gate": lang,
        **scored,
        "framework": "ai-job-search v1.3.6 (5-dimension weighted + gates)",
        "honesty_note": "triage scores; company research + reviewer pass remain part of the full /apply flow",
    }
