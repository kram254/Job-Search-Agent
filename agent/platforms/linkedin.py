"""
LinkedIn Easy Apply platform handler.
Handles the LinkedIn Jobs “Easy Apply” flow, which is a modal‑based multi‑step
process.  This handler is a skeleton – you will flesh out the details in
Phase 3 when your field mapper is more robust.
"""

import re
import logging
import time
from typing import List, Dict, Any
from .base import BasePlatformHandler
from ..browser.playwright_wrapper import BrowserWrapper


class LinkedInHandler(BasePlatformHandler):
    """
    Detection: URLs containing `linkedin.com/jobs` or `linkedin.com/job-groups`
    Flow: a modal appears with “Easy Apply” – steps:
     1. Contact info
     2. Resume upload
     3. Additional questions (cover letter, notifications, work auth)
     4. Review & Submit
    """

    URL_PATTERNS = [
        r"linkedin\.com/jobs",
        r"linkedin\.com/job-groups",
    ]

    def detect(self, url: str, page_snapshot: str) -> bool:
        # Simple hostname check
        return any(re.search(pat, url, re.IGNORECASE) for pat in self.URL_PATTERNS)

    def get_form_steps(self) -> List[Dict[str, Any]]:
        """
        LinkedIn Easy Apply steps – each step is a dict containing the step ID,
        description, fields expected and the “next” button label.
        """
        return [
            {
                "step_id": "contact_info",
                "description": "Contact Information",
                "fields": ["first_name", "last_name", "email", "phone", "country"],
                "next_button": "Continue",
            },
            {
                "step_id": "resume_upload",
                "description": "Upload Resume",
                "fields": ["resume_file"],
                "next_button": "Continue",
            },
            {
                "step_id": "questions",
                "description": "Additional Questions",
                "fields": [
                    "cover_letter",
                    "desired_salary",
                    "sponsorship_required",
                    "how_heard_about_job"
                ],
                "next_button": "Continue",
            },
            {
                "step_id": "review_submit",
                "description": "Review & Submit",
                "fields": [],
                "next_button": "Submit application",
                "final": True,
            },
        ]

    def handle_step(self, step: Dict[str, Any], field_mappings: List[Dict[str, Any]], browser: BrowserWrapper):
        """
        For LinkedIn, we need to:
        - Fill text fields with the mapped values.
        - Upload the selected resume file (if present).
        - Click the step’s “next” button.
        """
        result = {}

        for field in step["fields"]:
            # Find the matching mapping entry for this field name
            mapping = next((m for m in field_mappings if m["field_id"] == field), None)
            if not mapping:
                logging.warning(f"[LinkedIn] No mapping for field '{field}' – skipping")
                continue

            if mapping["requires_hitl"]:
                # Signal the HITL UI for human involvement
                self._trigger_hitl_for_field(field, mapping)
                self._wait_for_gate_response()
                # After human resolves, reload the value from somewhere (e.g. a temp cache)
                value = self._get_human_filled_value(field)  # you will implement storage
            else:
                value = mapping["candidate_value"]

            try:
                # Fill the field (LinkedIn form controls have predictable selectors)
                self._fill_field(browser, field, value)
                result[field] = {"status": "filled", "value": value}
            except Exception as e:
                result[field] = {"status": "error", "msg": str(e)}

        # Click “Continue” or “Submit” at the end of this step
        button_text = step["next_button"]
        self._click_button(browser, button_text)

        return result

    def _fill_field(self, browser: BrowserWrapper, field_name: str, value):
        """
        Helper to fill a known LinkedIn field by its name / aria‑label.
        In practice you would use robust selectors based on `page.get_by_role` etc.
        """
        page = browser.page
        if field_name == "resume_file":
            # value should be a path to a PDF
            page.set_input_files('input[type="file"]', str(value))
        else:
            # Use Playwright's `get_by_label` convenience method for text fields
            locator = page.get_by_label(field_name, exact=False)
            if locator.count() > 0:
                locator.fill(str(value))
            else:
                # Fallback to a CSS selector based on placeholder
                page.locator(f"input[placeholder*='{field_name}']").fill(str(value))

    def _click_button(self, browser: BrowserWrapper, text: str):
        page = browser.page
        page.get_by_role("button", name=text, exact=False).click()

    def detect_login(self, page) -> bool:
        """
        LinkedIn uses a full‑page sign‑in modal or redirect.
        Simple heuristic: presence of a password field.
        """
        return page.get_by_label("Password").count() > 0

    def submit_application(self, browser: BrowserWrapper):
        """
        LinkedIn’s final step is true submission; you can call this method only
        after the final HITL gate has been cleared.
        """
        # The final "Submit application" button should already have been clicked
        # in _handle_step for the `final` step.  Here we just wait for a confirmation.
        page = browser.page
        page.wait_for_selector("h2:has-text('Subm')", timeout=30000)  # e.g., "Submission complete"
        logging.info("[LinkedIn] Application submitted successfully")

    # --------------------------------------------------------------------- #
    # HITL helpers – these talk with the central orchestrator / HITL UI.
    # --------------------------------------------------------------------- #
    def _trigger_hitl_for_field(self, field: str, mapping: Dict[str, Any]):
        # The central orchestrator will emit an event; here we just log.
        logging.info(f"[LinkedIn] HITL field: {field} – reason: {mapping.get('hitl_reason')}")

    def _wait_for_gate_response(self):
        # Delegate to orchestrator's main loop (or implement a simple poll)
        time.sleep(0.5)  # placeholder – orchestrator will handle waiting

    def _get_human_filled_value(self, field: str) -> str:
        """
        In a real implementation the orchestrator would store the human’s input
        in a shared object or read it from a temporary file.  Here we return a
        placeholder.
        """
        return "HUMAN_FILLED_VALUE"