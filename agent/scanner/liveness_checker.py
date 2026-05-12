import re
import requests
from typing import Tuple, Optional


EXPIRED_BODY_SIGNALS = [
    "no longer accepting applications",
    "position has been filled",
    "this job is no longer available",
    "application period has closed",
    "job has expired",
    "posting has expired",
    "this position has been closed",
    "we are no longer accepting",
    "this job posting has expired",
    "page not found",
    "404 - not found",
    "job not found",
    "sorry, this job is",
    "this listing is no longer active"
]

EXPIRED_URL_SIGNALS = [
    "error=true",
    "expired=true",
    "status=closed",
    "job-not-found",
    "posting-closed"
]


class LivenessChecker:
    """Verify whether a job posting URL is still active."""

    def __init__(self, timeout: int = 8):
        self.timeout = timeout

    def check(self, url: str) -> Tuple[bool, str]:
        """
        Returns (is_live, reason).
        is_live=True means posting is active.
        """
        if not url or not url.startswith("http"):
            return False, "invalid_url"

        for signal in EXPIRED_URL_SIGNALS:
            if signal in url.lower():
                return False, f"url_signal:{signal}"

        try:
            head_resp = requests.head(url, timeout=self.timeout, allow_redirects=True)
            final_url = head_resp.url

            for signal in EXPIRED_URL_SIGNALS:
                if signal in final_url.lower():
                    return False, f"redirect_signal:{signal}"

            if head_resp.status_code == 404:
                return False, "http_404"

            if head_resp.status_code == 410:
                return False, "http_410_gone"

            if head_resp.status_code >= 500:
                return True, "server_error_assume_live"

        except requests.exceptions.Timeout:
            return True, "timeout_assume_live"
        except requests.exceptions.ConnectionError:
            return False, "connection_error"
        except Exception:
            return True, "check_failed_assume_live"

        try:
            get_resp = requests.get(url, timeout=self.timeout, allow_redirects=True)
            content = get_resp.text.lower()

            for signal in EXPIRED_BODY_SIGNALS:
                if signal in content:
                    return False, f"body_signal:{signal[:40]}"

            return True, "live"

        except Exception:
            return True, "get_failed_assume_live"

    def check_batch(self, urls: list) -> dict:
        results = {}
        for url in urls:
            is_live, reason = self.check(url)
            results[url] = {"is_live": is_live, "reason": reason}
        return results

    @staticmethod
    def extract_posted_date(html_content: str) -> Optional[str]:
        patterns = [
            r'datePosted["\s]*:["\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})',
            r'posted[_\s]*date["\s]*:["\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})',
            r'<time[^>]*datetime=["\']([0-9]{4}-[0-9]{2}-[0-9]{2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
