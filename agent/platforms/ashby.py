import logging
import requests
from typing import List, Dict, Any, Optional

from .base import BasePlatformHandler


ASHBY_GRAPHQL_ENDPOINT = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"

ASHBY_QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: publishedJobBoard(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
    jobPostings {
      id
      title
      teamName
      locationName
      employmentType
      descriptionPlain
      externalLink
      publishedAt
      isRemote
    }
  }
}
"""


class AshbyHandler(BasePlatformHandler):
    """Handler for Ashby ATS — prefers GraphQL API over Playwright DOM."""

    def __init__(self):
        self.logger = logging.getLogger("ashby_handler")

    def detect(self, url: str) -> bool:
        return "jobs.ashbyhq.com" in url or "ashby" in url.lower()

    @staticmethod
    def extract_slug(url: str) -> Optional[str]:
        import re
        match = re.search(r'jobs\.ashbyhq\.com/([^/?#]+)', url)
        if match:
            return match.group(1)
        return None

    def fetch_jobs(self, company_slug: str) -> List[Dict[str, Any]]:
        """Fetch jobs via Ashby GraphQL API."""
        payload = {
            "operationName": "ApiJobBoardWithTeams",
            "query": ASHBY_QUERY,
            "variables": {"organizationHostedJobsPageName": company_slug}
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        try:
            resp = requests.post(
                ASHBY_GRAPHQL_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            postings = (
                data.get("data", {})
                    .get("jobBoard", {})
                    .get("jobPostings", [])
            )
            return postings or []
        except requests.exceptions.HTTPError as e:
            self.logger.warning(f"Ashby GraphQL HTTP error for {company_slug}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Ashby GraphQL fetch failed for {company_slug}: {e}")
            return []

    def fetch_jobs_from_url(self, careers_url: str) -> List[Dict[str, Any]]:
        slug = self.extract_slug(careers_url)
        if not slug:
            return []
        return self.fetch_jobs(slug)

    def detect_login(self, page) -> bool:
        return False

    def fill_field(self, page, field_id: str, value: str) -> bool:
        try:
            selector = f'[data-field-id="{field_id}"], #{field_id}, [name="{field_id}"]'
            element = page.query_selector(selector)
            if not element:
                return False
            element.fill(value)
            return True
        except Exception as e:
            self.logger.error(f"fill_field error on {field_id}: {e}")
            return False

    def click_continue(self, page) -> bool:
        try:
            selectors = [
                'button[type="submit"]',
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Submit")'
            ]
            for sel in selectors:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
                    return True
            return False
        except Exception as e:
            self.logger.error(f"click_continue error: {e}")
            return False

    def submit_application(self, page) -> bool:
        return self.click_continue(page)
