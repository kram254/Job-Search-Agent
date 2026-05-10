import re
import logging
import time
from typing import List, Dict, Any, Optional
from .base import BasePlatformHandler


class FieldMapper:

    def __init__(self, candidate_profile, job_description):
        self.candidate = candidate_profile
        self.job = job_description
        self.field_map = {
            "skills": "skills",
            "experience": "experience",
            "education": "education",
            "projects": "projects",
            "certifications": "certifications"
        }

    def map_fields(self):
        matches = {}
        for skill in self.candidate.get("skills", []):
            if skill in self.job.get("required_skills", []) or skill in self.job.get("preferred_skills", []):
                matches[skill] = {
                    "match_type": "required",
                    "confidence": 0.9
                }
        for experience in self.candidate.get("experience", []):
            if experience.get("role") in self.job.get("required_roles", []) or experience.get("role") in self.job.get("preferred_roles", []):
                matches[experience.get("role", "")] = {
                    "duration": experience.get("duration", ""),
                    "company": experience.get("company", ""),
                    "achievements": experience.get("achievements", [])
                }
        return matches

    def generate_cover_letter(self):
        letter = f"""Dear Hiring Manager,

I am writing to express my interest in the {self.job.get('job_title', '')} position at {self.job.get('company', '')} as advertised on {self.job.get('source', '')}.
"""
        letter += (
            "Throughout my career, I've developed expertise in relevant skills. "
            "My experience includes building scalable systems, leading technical initiatives, "
            "and delivering measurable results."
        )
        letter += (
            "\n\nI'm confident I can contribute to your team's success and would welcome "
            "the opportunity to discuss my qualifications further.\n\nSincerely,\n[Candidate Name]"
        )
        return letter

    def detect_captcha(self):
        return False

    def create_cover_letter(self):
        return self.generate_cover_letter()

    def write_to_file(self, file_path):
        with open(file_path, "w") as f:
            f.write(self.generate_cover_letter())
        return file_path

    def test_field_mapper(self):
        test_data = {
            "skills": ["Python", "LLM", "RAG"],
            "experience": [
                {"role": "Senior AI Engineer", "company": "Metova", "duration": "2 years"},
                {"role": "ML Engineer", "company": "Saransh", "duration": "3 years"}
            ],
            "projects": ["Project A", "Project B"]
        }
        return self.map_fields()

    def test_cover_letter(self):
        return self.generate_cover_letter()

    def test_captcha_detection(self):
        return self.detect_captcha()

    def test_all(self):
        self.test_field_mapper()
        self.test_cover_letter()
        self.test_captcha_detection()
        return True


class GreenhouseHandler(BasePlatformHandler):

    URL_PATTERNS = [
        r"greenhouse\.io",
        r"grnh\.se",
        r"job-boards\.greenhouse\.io",
        r"boards\.greenhouse\.io",
        r"job-boards\.eu\.greenhouse\.io",
    ]

    STEP_SELECTORS = {
        "continue": [
            "button[data-provides='next-step']",
            "button:has-text('Continue')",
            "button:has-text('Next')",
            "input[type='submit']",
        ],
        "submit": [
            "button[data-provides='submit']",
            "button:has-text('Submit Application')",
            "button:has-text('Submit')",
        ],
    }

    def detect(self, url: str, page_snapshot: str) -> bool:
        return any(re.search(pat, url, re.IGNORECASE) for pat in self.URL_PATTERNS)

    def detect_login(self, page) -> bool:
        try:
            return (
                page.locator("input[type='password']").count() > 0
                or page.locator("text=Sign in").count() > 0
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
            logging.warning(f"[Greenhouse] get_form_fields error: {e}")
            return []

    def fill_field(self, page, field_id: str, value: str) -> bool:
        try:
            selectors = [
                f"#{field_id}",
                f"[name='{field_id}']",
                f"[data-field-id='{field_id}']",
            ]
            for selector in selectors:
                locator = page.locator(selector)
                if locator.count() > 0:
                    el = locator.first
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        el.select_option(label=value)
                    elif el.get_attribute("type") in ("checkbox", "radio"):
                        if value.lower() in ("true", "yes", "1"):
                            el.check()
                    else:
                        el.fill(str(value))
                    return True
            label_locator = page.get_by_label(field_id, exact=False)
            if label_locator.count() > 0:
                label_locator.first.fill(str(value))
                return True
        except Exception as e:
            logging.warning(f"[Greenhouse] fill_field({field_id}) error: {e}")
        return False

    def upload_resume(self, page, cv_path: str) -> bool:
        try:
            upload_selectors = [
                "input[type='file'][name*='resume']",
                "input[type='file'][name*='cv']",
                "input[type='file']",
            ]
            for selector in upload_selectors:
                locator = page.locator(selector)
                if locator.count() > 0:
                    locator.first.set_input_files(cv_path)
                    logging.info(f"[Greenhouse] Resume uploaded: {cv_path}")
                    return True
        except Exception as e:
            logging.warning(f"[Greenhouse] upload_resume error: {e}")
        return False

    def click_continue(self, page) -> bool:
        for selector in self.STEP_SELECTORS["continue"]:
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
        for selector in self.STEP_SELECTORS["submit"]:
            try:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.first.is_enabled():
                    btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    logging.info("[Greenhouse] Application submitted")
                    return True
            except Exception:
                continue
        logging.error("[Greenhouse] Submit button not found")
        return False

    def detect_confirmation(self, page) -> bool:
        confirmation_signals = [
            "text=Application submitted",
            "text=Thank you for applying",
            "text=We've received your application",
            "text=successfully submitted",
        ]
        for signal in confirmation_signals:
            try:
                if page.locator(signal).count() > 0:
                    return True
            except Exception:
                continue
        return False

    def get_human_filled_value(self, field_id: str) -> str:
        return ""
