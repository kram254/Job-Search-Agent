import re
import logging
import time
from typing import List, Dict, Any
from .base import BasePlatformHandler


class IndeedHandler(BasePlatformHandler):

    URL_PATTERNS = [
        r"indeed\.com",
        r"indeed\.co\.",
    ]

    def detect(self, url: str, page_snapshot: str) -> bool:
        return any(re.search(pat, url, re.IGNORECASE) for pat in self.URL_PATTERNS)

    def detect_login(self, page) -> bool:
        try:
            return (
                page.locator("input[type='password']").count() > 0
                or page.locator("text=Sign in").count() > 0
                or page.locator("text=Log in").count() > 0
            )
        except Exception:
            return False

    def get_form_fields(self, page) -> List[Dict[str, Any]]:
        try:
            fields = page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('input, select, textarea').forEach(el => {
                    const label = document.querySelector(`label[for="${el.id}"]`);
                    results.push({
                        id: el.id || el.name || '',
                        type: el.type || el.tagName.toLowerCase(),
                        name: el.name || '',
                        placeholder: el.placeholder || '',
                        label: label ? label.innerText.trim() : '',
                        required: el.required,
                        value: el.value || ''
                    });
                });
                return results;
            }""")
            return fields or []
        except Exception as e:
            logging.warning(f"[Indeed] get_form_fields error: {e}")
            return []

    def fill_field(self, page, field_id: str, value: str) -> bool:
        try:
            selectors = [f"#{field_id}", f"[name='{field_id}']"]
            for selector in selectors:
                locator = page.locator(selector)
                if locator.count() > 0:
                    el = locator.first
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        el.select_option(label=value)
                    else:
                        el.fill(str(value))
                    return True
            label_locator = page.get_by_label(field_id, exact=False)
            if label_locator.count() > 0:
                label_locator.first.fill(str(value))
                return True
        except Exception as e:
            logging.warning(f"[Indeed] fill_field({field_id}) error: {e}")
        return False

    def upload_resume(self, page, cv_path: str) -> bool:
        try:
            locator = page.locator("input[type='file']")
            if locator.count() > 0:
                locator.first.set_input_files(cv_path)
                logging.info(f"[Indeed] Resume uploaded: {cv_path}")
                return True
        except Exception as e:
            logging.warning(f"[Indeed] upload_resume error: {e}")
        return False

    def click_continue(self, page) -> bool:
        continue_selectors = [
            "button:has-text('Continue')",
            "button:has-text('Next')",
            "button[type='submit']",
        ]
        for selector in continue_selectors:
            try:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.first.is_enabled():
                    btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            except Exception:
                continue
        return False

    def submit_application(self, browser) -> bool:
        page = browser.page if hasattr(browser, "page") else browser
        submit_selectors = [
            "button:has-text('Submit your application')",
            "button:has-text('Apply now')",
            "button[type='submit']",
        ]
        for selector in submit_selectors:
            try:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.first.is_enabled():
                    btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    logging.info("[Indeed] Application submitted")
                    return True
            except Exception:
                continue
        logging.error("[Indeed] Submit button not found")
        return False

    def get_human_filled_value(self, field_id: str) -> str:
        return ""
