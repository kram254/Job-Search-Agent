from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

FEATURE_WEIGHTS: Dict[str, float] = {
    "platform":  0.12,
    "kind":      0.18,
    "company":   0.08,
    "source":    0.10,
    "ats":       0.10,
    "tag":       0.12,
    "stack":     0.15,
    "location":  0.08,
    "budget":    0.09,
    "urgency":   0.08,
}

ATS_PATTERNS = {
    "greenhouse": [r"greenhouse\.io", r"boards\.greenhouse"],
    "ashby":      [r"ashbyhq\.com", r"jobs\.ashby"],
    "lever":      [r"jobs\.lever\.co"],
    "workday":    [r"myworkdayjobs\.com", r"\.wd\d+\."],
    "bamboohr":   [r"bamboohr\.com"],
    "linkedin":   [r"linkedin\.com/jobs"],
    "indeed":     [r"indeed\.com"],
    "greenhouse_eu": [r"greenhouse\.io/eu", r"eu\.greenhouse"],
}

PLATFORM_PATTERNS = {
    "remote_ok":   [r"remoteok\.com", r"remote\.co"],
    "wwr":         [r"weworkremotely\.com"],
    "hn_who_hiring": [r"news\.ycombinator\.com"],
    "builtin":     [r"builtin\.com"],
    "wellfound":   [r"wellfound\.com", r"angel\.co"],
    "dice":        [r"dice\.com"],
}

MAX_DELTA = 18.0
MIN_DELTA = -18.0


class FeedbackRanker:

    def __init__(self, data_path: str = "data/feedback_signals.json"):
        self.data_path = Path(data_path)
        self._signals: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self._signals, f, indent=2)

    def record_outcome(self, job_id: str, listing: Dict[str, Any], outcome: str) -> None:
        features = self._extract_features(listing)
        self._signals.append({
            "job_id":    job_id,
            "features":  features,
            "outcome":   outcome,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()

    def score_listing(self, listing: Dict[str, Any]) -> float:
        if not self._signals:
            return 0.0

        features = self._extract_features(listing)
        pos_signals = [s for s in self._signals if s.get("outcome") == "positive"]
        neg_signals = [s for s in self._signals if s.get("outcome") == "negative"]

        delta = 0.0
        for key, value in features.items():
            if not value:
                continue
            weight = FEATURE_WEIGHTS.get(key, 0.0)
            pos_matches = sum(1 for s in pos_signals if s.get("features", {}).get(key) == value)
            neg_matches = sum(1 for s in neg_signals if s.get("features", {}).get(key) == value)
            total = pos_matches + neg_matches
            if total > 0:
                signal = (pos_matches - neg_matches) / total
                delta += signal * weight * MAX_DELTA

        return max(MIN_DELTA, min(MAX_DELTA, delta))

    def _extract_features(self, listing: Dict[str, Any]) -> Dict[str, str]:
        url = listing.get("url", listing.get("applyUrl", ""))
        description = listing.get("description", "")
        title = listing.get("title", "")

        return {
            "platform":  self._detect_platform(url),
            "kind":      self._classify_kind(title),
            "company":   listing.get("company", "").lower().strip(),
            "source":    listing.get("source", "").lower().strip(),
            "ats":       self._detect_ats(url),
            "tag":       self._extract_primary_tag(description),
            "stack":     self._extract_primary_stack(description),
            "location":  self._normalize_location(listing.get("location", "")),
            "budget":    self._classify_budget(description),
            "urgency":   self._classify_urgency(description),
        }

    @staticmethod
    def _detect_ats(url: str) -> str:
        url_lower = url.lower()
        for ats, patterns in ATS_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return ats
        return "unknown"

    @staticmethod
    def _detect_platform(url: str) -> str:
        url_lower = url.lower()
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return platform
        return "direct"

    @staticmethod
    def _classify_kind(title: str) -> str:
        title_lower = title.lower()
        if any(t in title_lower for t in ["engineer", "developer", "programmer", "sre", "devops"]):
            return "engineering"
        if any(t in title_lower for t in ["manager", "director", "head of", "vp"]):
            return "management"
        if any(t in title_lower for t in ["scientist", "researcher", "analyst"]):
            return "research"
        if any(t in title_lower for t in ["designer", "ux", "ui"]):
            return "design"
        if any(t in title_lower for t in ["product", "pm", "po"]):
            return "product"
        return "other"

    @staticmethod
    def _extract_primary_tag(description: str) -> str:
        desc_lower = description.lower()
        tags = [
            ("llm", ["llm", "large language model", "gpt", "claude"]),
            ("ml",  ["machine learning", "deep learning", "neural"]),
            ("data", ["data engineer", "data pipeline", "etl"]),
            ("agent", ["agent", "agentic", "multi-agent"]),
            ("infra", ["kubernetes", "terraform", "devops"]),
            ("backend", ["api", "microservice", "rest"]),
        ]
        for tag, keywords in tags:
            if any(kw in desc_lower for kw in keywords):
                return tag
        return "general"

    @staticmethod
    def _extract_primary_stack(description: str) -> str:
        desc_lower = description.lower()
        stacks = [
            ("python_ml", ["pytorch", "tensorflow", "huggingface", "sklearn"]),
            ("python_web", ["django", "fastapi", "flask"]),
            ("js_node", ["node.js", "express", "nest.js"]),
            ("java_spring", ["spring boot", "java", "jvm"]),
            ("go", ["golang", "go "]),
            ("rust", ["rust", "tokio"]),
        ]
        for stack, keywords in stacks:
            if any(kw in desc_lower for kw in keywords):
                return stack
        return "unknown"

    @staticmethod
    def _normalize_location(location: str) -> str:
        loc_lower = location.lower().strip()
        if not loc_lower or any(kw in loc_lower for kw in ["remote", "anywhere", "worldwide"]):
            return "remote"
        if any(kw in loc_lower for kw in ["us", "united states", "usa", "america"]):
            return "us"
        if any(kw in loc_lower for kw in ["uk", "united kingdom", "england"]):
            return "uk"
        if any(kw in loc_lower for kw in ["europe", "eu"]):
            return "europe"
        if any(kw in loc_lower for kw in ["kenya", "nairobi", "africa"]):
            return "africa"
        return "other"

    @staticmethod
    def _classify_budget(description: str) -> str:
        desc_lower = description.lower()
        salary_patterns = [
            (r"\$(\d+)[kK]?\s*[-–]\s*\$?(\d+)[kK]?", "range"),
            (r"up to \$(\d+)[kK]?", "max"),
        ]
        for pattern, kind in salary_patterns:
            match = re.search(pattern, desc_lower)
            if match:
                try:
                    if kind == "range":
                        low = int(match.group(1))
                        high = int(match.group(2))
                        mid = (low + high) / 2
                    else:
                        mid = int(match.group(1))
                    if mid < 100:
                        mid *= 1000
                    if mid >= 200000:
                        return "senior_plus"
                    if mid >= 150000:
                        return "senior"
                    if mid >= 100000:
                        return "mid_senior"
                    if mid >= 70000:
                        return "mid"
                    return "junior"
                except Exception:
                    pass
        return "undisclosed"

    @staticmethod
    def _classify_urgency(description: str) -> str:
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["immediate", "asap", "start immediately", "urgent"]):
            return "high"
        if any(kw in desc_lower for kw in ["rolling", "open until filled"]):
            return "low"
        return "normal"

    def get_signal_summary(self) -> Dict[str, Any]:
        pos = sum(1 for s in self._signals if s.get("outcome") == "positive")
        neg = sum(1 for s in self._signals if s.get("outcome") == "negative")
        return {
            "total_signals": len(self._signals),
            "positive":      pos,
            "negative":      neg,
        }
