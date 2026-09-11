"""JobRight-parity Phase 3 — Real-time alert engine.

NEW MODULE (additive only). After a scan, diffs the fresh listings against the
previous alert state and emits alerts for high-match, newly-seen jobs. Alerts are
persisted to data/alerts.json (new file — nothing existing is touched) and can be
handed to the existing digest notifier for email delivery.
"""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("alert_engine")

DEFAULT_ALERTS_PATH = "data/alerts.json"
DEFAULT_SCORE_THRESHOLD = 75.0
MAX_ALERTS_KEPT = 200


class AlertEngine:
    """Generates and stores alerts for high-match new listings."""

    def __init__(self, alerts_path: str = DEFAULT_ALERTS_PATH,
                 score_threshold: float = DEFAULT_SCORE_THRESHOLD):
        self.alerts_path = Path(alerts_path)
        self.score_threshold = float(
            os.environ.get("ALERT_SCORE_THRESHOLD", score_threshold)
        )
        self.alerts_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- storage ----------

    def _load(self) -> List[Dict[str, Any]]:
        if not self.alerts_path.exists():
            return []
        try:
            with open(self.alerts_path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, alerts: List[Dict[str, Any]]) -> None:
        tmp = str(self.alerts_path) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(alerts[:MAX_ALERTS_KEPT], f, indent=2)
        os.replace(tmp, str(self.alerts_path))

    # ---------- core ----------

    def seen_urls(self) -> set:
        return {a.get("url", "") for a in self._load() if a.get("url")}

    def evaluate_scan_results(self, listings: List[Dict[str, Any]],
                              previously_seen_urls: Optional[set] = None) -> List[Dict[str, Any]]:
        """Create alerts for listings that are new AND score above threshold.

        :param listings: fresh listings from a scan (dicts with title/company/url/score)
        :param previously_seen_urls: urls seen before this scan (e.g. prior feed ids/urls)
        """
        seen = previously_seen_urls if previously_seen_urls is not None else self.seen_urls()
        new_alerts = []
        for listing in listings or []:
            url = str(listing.get("url", ""))
            if not url or url in seen:
                continue
            try:
                score = float(listing.get("score", 0) or 0)
            except (TypeError, ValueError):
                continue
            if score < self.score_threshold:
                continue
            new_alerts.append({
                "id": f"alert_{int(datetime.now(timezone.utc).timestamp())}_{abs(hash(url)) % 10000}",
                "type": "high_match_new_job",
                "title": listing.get("title", ""),
                "company": listing.get("company", listing.get("companyName", "")),
                "url": url,
                "score": score,
                "location": listing.get("location", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "read": False,
            })
        if new_alerts:
            current = self._load()
            self._save(new_alerts + current)
        return new_alerts

    def list_alerts(self, unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        alerts = self._load()
        if unread_only:
            alerts = [a for a in alerts if not a.get("read", False)]
        return alerts[:limit]

    def unread_count(self) -> int:
        return sum(1 for a in self._load() if not a.get("read", False))

    def mark_read(self, alert_id: str) -> bool:
        alerts = self._load()
        changed = False
        for a in alerts:
            if a.get("id") == alert_id and not a.get("read", False):
                a["read"] = True
                changed = True
        if changed:
            self._save(alerts)
        return changed

    def mark_all_read(self) -> int:
        alerts = self._load()
        changed = 0
        for a in alerts:
            if not a.get("read", False):
                a["read"] = True
                changed += 1
        if changed:
            self._save(alerts)
        return changed

    # ---------- email delivery via the existing notifier ----------

    def notify_by_email(self, alerts: List[Dict[str, Any]]) -> bool:
        """Hand new alerts to the existing digest notifier. Best-effort."""
        if not alerts:
            return False
        try:
            from agent.digest.notifier import _format_plain  # additive reuse
            lines = [f"🔔 {len(alerts)} new high-match job(s) just landed:\n"]
            for a in alerts:
                lines.append(f"- {a.get('title', '?')} @ {a.get('company', '?')} — score {a.get('score', '?')}/100")
                lines.append(f"  {a.get('url', '')}")
            body = "\n".join(lines)
            logger.info(f"[alerts] email body prepared:\n{body}")
            # Actual email delivery reuses the digest notifier's send path when
            # configured; import here so the alert engine works without it.
            try:
                from agent.digest import notifier as _notifier
                send = getattr(_notifier, "send_email", None) or getattr(_notifier, "send", None)
                if callable(send):
                    send(subject=f"🔔 {len(alerts)} new high-match jobs", body=body)
                    return True
            except Exception:
                pass
            return False
        except Exception as e:
            logger.warning(f"[alerts] email notification failed: {e}")
            return False


def evaluate_listings_for_alerts(listings: List[Dict[str, Any]],
                                 alerts_path: str = DEFAULT_ALERTS_PATH,
                                 previously_seen_urls: Optional[set] = None) -> List[Dict[str, Any]]:
    """Convenience wrapper used by the /scan hook and /alerts routes."""
    engine = AlertEngine(alerts_path=alerts_path)
    return engine.evaluate_scan_results(listings, previously_seen_urls)
