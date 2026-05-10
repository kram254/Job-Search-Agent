"""
Orchestrator – the state machine that drives the end‑to‑end job‑application flow.

Key responsibilities:
1. Load candidate profile & job listings.
2. Detect the target ATS from the application URL.
3. Instantiate the appropriate PlatformHandler.
4. Run the step‑by‑step workflow:
   - login / navigation
   - form discovery & inventory
   - field mapping via LLM
   - form filling (auto‑fill high‑confidence, HITL for low/flags)
   - HITL gate handling (using config/hitl_config.json)
   - final submission (only after explicit human approval)
5. Persist session state (checkpoints) so the process can be resumed after
   a pause or crash.
6. Emit events for the HITL UI (Flask) and for logging.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from agent.platforms.base import BasePlatformHandler
from agent.platforms.greenhouse import GreenhouseHandler
from agent.platforms.linkedin import LinkedInHandler
from agent.platforms.indeed import IndeedHandler
from agent.llm.field_mapper import FieldMapper, JobEvaluation, Archetype
from agent.browser.playwright_wrapper import BrowserWrapper
from agent.browser.form_inventory import FormInventory
from agent.tracker.logger import Logger
from agent.services.pdf_generator import PDFGenerator, PDFGenerationResult
from agent.scanner.portal_scanner import PortalScanner

# --------------------------------------------------------------------------- #
# Configuration & constants
# --------------------------------------------------------------------------- #
CONFIG_DIR = Path("config")
DATA_DIR = Path("data")
SESSIONS_DIR = DATA_DIR / "sessions"
LOGS_DIR = DATA_DIR / "logs"

# Ensure required directories exist
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Orchestrator Core Class
# --------------------------------------------------------------------------- #
class ApplicationOrchestrator:
    """
    High‑level workflow controller.  All external side‑effects (browser actions,
    HITL notifications, logging) are performed through well‑defined hooks so
    they can be swapped out in tests.
    """

    def __init__(self, candidate_profile_path: Path,
                 jobs_raw_path: Path,
                 hitl_config_path: Path):
        """
        :param candidate_profile_path: Path to candidate_profile.json
        :param jobs_raw_path: Path to jobs_raw.json
        :param hitl_config_path: Path to hitl_config.json
        """
        # Load static data once
        with open(candidate_profile_path, "r", encoding="utf-8") as f:
            self.candidate_profile = json.load(f)

        with open(jobs_raw_path, "r", encoding="utf-8") as f:
            self.jobs_raw = json.load(f)

        with open(hitl_config_path, "r", encoding="utf-8") as f:
            self.hitl_config = json.load(f)

        # Logger for audit trail
        self.logger = Logger(logs_dir=LOGS_DIR)

        # Browser wrapper (single persistent context per session)
        self.browser = BrowserWrapper(headless=False)  # headed for HITL visibility

        # Mapping of platform name → handler instance (lazy‑loaded)
        self.platform_handlers: Dict[str, BasePlatformHandler] = {}
        self.current_evaluation: Optional[JobEvaluation] = None
        self.pdf_generator = PDFGenerator(output_dir="output/cvs")
        self.tailored_cv_path: Optional[str] = None

    # --------------------------------------------------------------------------- #
    # 1️⃣ Public entry point
    # --------------------------------------------------------------------------- #
    def start_application(self, job_id: str, apply_url: str):
        """
        Entry point called by the user or by a batch queue.
        """
        # 1️⃣ Resolve session ID
        session_id = self._new_session_id()
        logging.info(f"[Session {session_id}] Starting application for job_id={job_id}")

        # 2️⃣ Resolve the job metadata
        job_meta = next((j for j in self.jobs_raw if j["id"] == job_id), None)
        if not job_meta:
            raise ValueError(f"Job ID {job_id} not found in jobs_raw.json")
        self.job_meta = job_meta

        # 3️⃣ Resolve final application URL (follow redirects)
        final_url = self._resolve_final_url(apply_url)
        logging.info(f"[Session {session_id}] Final application URL: {final_url}")

        # 4️⃣ Platform detection
        platform_name = self._detect_platform(final_url)
        logging.info(f"[Session {session_id}] Detected platform: {platform_name}")

        # 5️⃣ Load / instantiate the platform handler
        handler = self._get_or_create_handler(platform_name)
        self.current_handler = handler
        handler.session_id = session_id
        handler.logger = self.logger

        # 6️⃣ Navigate to the URL
        self.browser.launch(headless=False)
        self.browser.navigate(final_url)
        logging.info(f"[Session {session_id}] Navigated to {final_url}")

        # 7️⃣ Kick‑off the workflow
        self._run_workflow(handler, final_url)

    # --------------------------------------------------------------------------- #
    # 2️⃣ Helper methods
    # --------------------------------------------------------------------------- #

    def _new_session_id(self) -> str:
        """Generate a new UUID for this application session."""
        return str(uuid.uuid4())

    def _resolve_final_url(self, url: str) -> str:
        """
        Use Playwright to follow redirects until a stable URL is reached.
        Returns the final URL string.
        """
        page = self.browser.page
        page.goto(url, wait_until="networkidle")
        final = page.url
        logging.debug(f"Redirected to final URL: {final}")
        return final

    def _detect_platform(self, url: str) -> str:
        """
        Very simple detection based on hostname patterns.
        Returns a string identifier that maps to a concrete PlatformHandler class.
        """
        hostname = url.split("/")[2].lower()
        if "greenhouse" in hostname or "grnh.se" in hostname:
            return "greenhouse"
        if "linkedin" in hostname:
            return "linkedin"
        if "indeed" in hostname:
            return "indeed"
        # Add more mappings as you create handlers …
        return "generic"

    def _get_or_create_handler(self, platform_name: str) -> BasePlatformHandler:
        """
        Lazily instantiate the appropriate PlatformHandler subclass.
        Handlers are cached per‑session.
        """
        if platform_name in self.platform_handlers:
            return self.platform_handlers[platform_name]

        handler_class_map = {
            "greenhouse": GreenhouseHandler,
            "linkedin": LinkedInHandler,
            "indeed": IndeedHandler,
        }
        if platform_name not in handler_class_map:
            raise ValueError(f"Unsupported platform: {platform_name}")

        handler = handler_class_map[platform_name]()
        self.platform_handlers[platform_name] = handler
        return handler

    # --------------------------------------------------------------------------- #
    # 3️⃣ Core workflow stages
    # --------------------------------------------------------------------------- #
    def _run_workflow(self, handler: BasePlatformHandler, url: str):
        """
        Orchestrates the full application lifecycle.
        This method is deliberately linear but can be made stateful
        (pause/resume) via checkpointing.
        """
        try:
            # Step 1 – login / account creation if required
            self._handle_login(handler)

            # Step 2 – CV selection (soft gate)
            self._handle_cv_selection(handler)

            # Step 3 – form discovery & inventory
            inventory = self._discover_form_inventory()
            logging.info(f"[Session {handler.session_id}] Form inventory captured")

            # Step 4 – LLM field mapping
            field_mappings = self._map_fields(inventory)
            logging.info(f"[Session {handler.session_id}] Field mappings generated")

            # Step 5 – form filling (auto + HITL)
            fill_result = self._fill_form(handler, field_mappings)
            logging.info(f"[Session {handler.session_id}] Form filling completed")

            # Step 6 – review & final HITL gate (final submit)
            self._handle_final_gate(handler, fill_result)

            # Step 7 – submission confirmation & cleanup
            self._finalize(handler)

            logging.info(f"[Session {handler.session_id}] Application submitted successfully")
        except Exception as exc:
            logging.exception(f"[Session {handler.session_id}] Fatal error: {exc}")
            # Persist error info for later review
            self.logger.log_error(session_id=handler.session_id, error=str(exc))
            raise

    # --------------------------------------------------------------------------- #
    # 3a️⃣ Login & account creation
    # --------------------------------------------------------------------------- #
    def _handle_login(self, handler: BasePlatformHandler):
        """
        Detects a login wall and pauses for human intervention.
        """
        if handler.detect_login(self.browser.page):
            logging.info("[Session] Login wall detected – pausing for human action")
            # Emit a HITL gate event for GATE_LOGIN
            self._emit_hitl_event(
                gate_id="GATE_LOGIN",
                message="Login required – please sign in to continue."
            )
            # The UI will call /gate-response/<session_id> when the user finishes.
            # The orchestrator will automatically resume when that file appears.
            # For now we just wait (blocking sleep is avoided – see _resume_on_response).
            self._wait_for_gate_response()

    # --------------------------------------------------------------------------- #
    # 3b️⃣ CV selection (soft gate)
    # --------------------------------------------------------------------------- #
    def _handle_cv_selection(self, handler: BasePlatformHandler):
        """
        Choose the best CV variant based on job requirements.
        By default we just pick the most relevant variant; the choice can be
        overridden in a HITL gate.
        """
        # Simple heuristic – pick the PDF that matches the most required skills
        # (real logic would live in a dedicated CV‑matching module)
        preferred_pdf = self._pick_preferred_cv()
        logging.info(f"[Session {handler.session_id}] Selected CV: {preferred_pdf}")
        handler.selected_cv_path = preferred_pdf

    def _pick_preferred_cv(self) -> str:
        profile = self.candidate_profile
        pdf_paths = profile.get("cv_variants", {}).get("pdf_paths", [])
        if pdf_paths:
            return pdf_paths[0]
        md_paths = profile.get("cv_variants", {}).get("paths", [])
        if md_paths:
            return md_paths[0]
        default_cv = self.hitl_config.get("default_cv", "CVs/SoftwareDevCV.pdf")
        return default_cv

    def _fill_single_field(self, field_id: str, value: str) -> None:
        handler = getattr(self, "current_handler", None)
        if handler and hasattr(handler, "fill_field"):
            handler.fill_field(self.browser.page, field_id, value)
            return
        try:
            page = self.browser.page
            locator = page.locator(f"#{field_id}, [name='{field_id}']")
            if locator.count() > 0:
                el = locator.first
                tag = el.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    el.select_option(label=value)
                else:
                    el.fill(str(value))
        except Exception as e:
            logging.warning(f"[Orchestrator] _fill_single_field({field_id}): {e}")

    # --------------------------------------------------------------------------- #
    # 3c️⃣ Form discovery & inventory
    # --------------------------------------------------------------------------- #
    def _discover_form_inventory(self) -> list:
        """
        Takes a screenshot, extracts the DOM inventory, and returns it as JSON‑ready
        Python structures.
        """
        page = self.browser.page
        screenshot_path = self._checkpoint_state()
        inventory = FormInventory.extract_inventory(self.browser)
        logging.debug(f"[Session] Form inventory: {inventory[:5]}")  # truncate for logs
        return inventory

    # --------------------------------------------------------------------------- #
    # 3d️⃣ Field mapping via LLM
    # --------------------------------------------------------------------------- #
    def _map_fields(self, inventory: list) -> list:
        """
        Calls FieldMapper with archetype-aware evaluation to produce
        field mappings with confidence scores and HITL flags.
        """
        # Read CV text if available
        cv_text = ""
        if hasattr(self, 'tailored_cv_path') and self.tailored_cv_path:
            try:
                with open(self.tailored_cv_path, "r", encoding="utf-8") as f:
                    cv_text = f.read()
            except:
                pass

        job_description = self.job_meta.get("description", "")

        # Use the new career-ops FieldMapper
        mapper = FieldMapper(
            candidate_profile=self.candidate_profile,
            job_description=job_description,
            cv_text=cv_text
        )

        # Store evaluation for later use
        self.current_evaluation = mapper.evaluate_job()

        # Log evaluation summary
        summary = mapper.get_evaluation_summary()
        logging.info(f"[Session] Archetype: {summary['archetype']} (confidence: {summary['confidence']:.2f})")
        logging.info(f"[Session] Global Score: {summary['global_score']:.2f}")
        logging.info(f"[Session] Recommendation: {summary['recommendation']}")

        # Generate mappings
        mappings = mapper.map_fields(inventory)
        logging.debug(f"[Session] Mapped fields: {mappings[:3]}")
        return mappings

    def run_apply_mode(self, job_id: str, apply_url: str,
                       cv_path: str = "cv.md",
                       auto_submit: bool = False) -> Dict[str, Any]:
        """
        Career-ops inspired apply mode with full evaluation pipeline.

        Steps:
        1. Archetype detection & job evaluation (A-F scoring)
        2. CV tailoring with keyword injection
        3. PDF generation
        4. Interview story preparation
        5. Form filling with archetype-aware mapping
        6. Final submission (HITL-gated unless auto_submit)

        Returns: Application result with evaluation and interview prep.
        """
        session_id = self._new_session_id()
        logging.info(f"[Apply Mode {session_id}] Starting for job_id={job_id}")

        # Resolve job metadata
        job_meta = next((j for j in self.jobs_raw if j["id"] == job_id), None)
        if not job_meta:
            raise ValueError(f"Job ID {job_id} not found in jobs_raw.json")
        self.job_meta = job_meta

        job_description = job_meta.get("description", "")
        company_name = job_meta.get("company", "unknown")

        # Step 1: Evaluate job (archetype detection + A-F scoring)
        self._evaluate_job_for_apply(job_description, cv_path)

        # Check if job is worth applying to
        if self.current_evaluation and self.current_evaluation.global_score < 3.5:
            logging.warning(f"[Apply Mode] Low match score ({self.current_evaluation.global_score:.1f}), skipping")
            return {
                "session_id": session_id,
                "job_id": job_id,
                "status": "skipped",
                "reason": f"Low match score: {self.current_evaluation.global_score:.1f}",
                "evaluation": self.current_evaluation
            }

        # Step 2 & 3: Generate tailored CV PDF
        try:
            pdf_result = self.pdf_generator.generate_tailored_cv(
                cv_markdown_path=cv_path,
                job_description=job_description,
                candidate_profile=self.candidate_profile,
                archetype=self.current_evaluation.archetype.value if self.current_evaluation else "general",
                company_name=company_name
            )
            self.tailored_cv_path = pdf_result.pdf_path
            logging.info(f"[Apply Mode] Generated tailored CV: {pdf_result.pdf_path}")
        except Exception as e:
            logging.warning(f"[Apply Mode] PDF generation failed: {e}")
            self.tailored_cv_path = None

        # Step 4: Prepare interview stories
        interview_prep = self._prepare_interview_stories()

        # Step 5: Run the actual application workflow
        final_url = self._resolve_final_url(apply_url)
        platform_name = self._detect_platform(final_url)
        handler = self._get_or_create_handler(platform_name)
        handler.session_id = session_id
        handler.logger = self.logger

        # Use tailored CV for upload
        if self.tailored_cv_path:
            handler.selected_cv_path = self.tailored_cv_path

        # Run workflow with optional auto-submit
        result = self._run_apply_workflow(handler, final_url, auto_submit)

        return {
            "session_id": session_id,
            "job_id": job_id,
            "status": result.get("status", "unknown"),
            "evaluation": self._get_evaluation_summary(),
            "interview_prep": interview_prep,
            "cv_path": self.tailored_cv_path,
            "company": company_name,
            "archetype": self.current_evaluation.archetype.value if self.current_evaluation else "unknown"
        }

    def _evaluate_job_for_apply(self, job_description: str, cv_path: str) -> None:
        """Run job evaluation for apply mode."""
        cv_text = ""
        if Path(cv_path).exists():
            try:
                with open(cv_path, "r", encoding="utf-8") as f:
                    cv_text = f.read()
            except Exception as e:
                logging.warning(f"[Apply Mode] Could not read CV: {e}")

        mapper = FieldMapper(
            candidate_profile=self.candidate_profile,
            job_description=job_description,
            cv_text=cv_text
        )

        self.current_evaluation = mapper.evaluate_job()

        # Log detailed evaluation
        for block_name, block in self.current_evaluation.blocks.items():
            logging.info(f"[Eval Block {block_name}] Score: {block.score:.1f} - {block.reasoning}")

    def _prepare_interview_stories(self) -> Dict[str, Any]:
        """Prepare STAR+R interview stories based on archetype."""
        if not self.current_evaluation:
            return {"stories": [], "themes": []}

        stories = self.current_evaluation.interview_stories
        archetype = self.current_evaluation.archetype.value

        # Format for human review
        formatted_stories = []
        for story in stories:
            formatted_stories.append({
                "situation": story.get("situation", ""),
                "task": story.get("task", ""),
                "action": story.get("action", ""),
                "result": story.get("result", ""),
                "reflection": story.get("reflection", ""),
                "formatted": self._format_star_story(story)
            })

        return {
            "stories": formatted_stories,
            "themes": self.current_evaluation.cv_tailoring_plan.get("highlight_projects", []),
            "archetype": archetype,
            "recommended_prep": self._get_interview_recommendations(archetype)
        }

    def _format_star_story(self, story: Dict[str, str]) -> str:
        """Format a STAR+R story for display."""
        return f"""
**Situation**: {story.get('situation', '')}
**Task**: {story.get('task', '')}
**Action**: {story.get('action', '')}
**Result**: {story.get('result', '')}
**Reflection**: {story.get('reflection', '')}
        """.strip()

    def _get_interview_recommendations(self, archetype: str) -> List[str]:
        """Get interview prep recommendations based on archetype."""
        recommendations = {
            "ai_platform_llmops": [
                "Prepare examples of LLM monitoring/observability",
                "Practice discussing eval frameworks and metrics",
                "Review your experience with production ML systems"
            ],
            "agentic_automation": [
                "Prepare agent architecture examples",
                "Practice HITL design discussions",
                "Review workflow orchestration experience"
            ],
            "technical_ai_pm": [
                "Prepare roadmap examples with trade-offs",
                "Practice stakeholder management stories",
                "Review AI product metrics and KPIs"
            ],
            "ai_solutions_architect": [
                "Prepare system design discussions",
                "Practice enterprise integration examples",
                "Review architecture decision records"
            ],
            "ai_forward_deployed": [
                "Prepare rapid prototyping examples",
                "Practice client communication scenarios",
                "Review deployment troubleshooting stories"
            ],
            "ai_transformation": [
                "Prepare change management examples",
                "Practice adoption metric discussions",
                "Review training/enablement experience"
            ]
        }
        return recommendations.get(archetype, ["Prepare general technical and behavioral questions"])

    def _run_apply_workflow(self, handler: BasePlatformHandler,
                           url: str, auto_submit: bool) -> Dict[str, str]:
        """
        Run the apply workflow with optional auto-submit.
        Career-ops: No auto-submission by default (HITL required).
        """
        try:
            # Login handling
            self._handle_login(handler)

            # CV selection (use tailored CV if available)
            self._handle_cv_selection(handler)

            # Form discovery
            inventory = self._discover_form_inventory()
            logging.info(f"[Apply Workflow] Discovered {len(inventory)} form fields")

            # Field mapping with evaluation context
            field_mappings = self._map_fields(inventory)

            # Log archetype info in mappings
            if field_mappings:
                archetype = field_mappings[0].get("archetype", "unknown")
                score = field_mappings[0].get("global_score", 0)
                logging.info(f"[Apply Workflow] Using archetype: {archetype} (score: {score:.2f})")

            # Form filling
            fill_result = self._fill_form(handler, field_mappings)

            # Final submission
            if auto_submit:
                # Auto-submit only if explicitly requested and score is high
                if self.current_evaluation and self.current_evaluation.global_score >= 4.5:
                    logging.warning("[Apply Workflow] Auto-submit enabled (not recommended)")
                    handler.submit_application(self.browser)
                    return {"status": "submitted", "method": "auto"}
                else:
                    logging.info("[Apply Workflow] Auto-submit blocked - score below 4.5 threshold")
                    self._handle_final_gate(handler, fill_result)
                    return {"status": "submitted", "method": "hitl"}
            else:
                # Default: HITL gate for all submissions
                self._handle_final_gate(handler, fill_result)
                return {"status": "submitted", "method": "hitl"}

        except Exception as exc:
            logging.exception(f"[Apply Workflow] Error: {exc}")
            self.logger.log_error(session_id=handler.session_id, error=str(exc))
            return {"status": "error", "error": str(exc)}

    def _get_evaluation_summary(self) -> Optional[Dict[str, Any]]:
        """Get current evaluation summary for API response."""
        if not self.current_evaluation:
            return None

        return {
            "archetype": self.current_evaluation.archetype.value,
            "confidence": self.current_evaluation.archetype_confidence,
            "global_score": self.current_evaluation.global_score,
            "recommendation": self.current_evaluation.recommendation,
            "blocks": {
                k: {"score": v.score, "reasoning": v.reasoning}
                for k, v in self.current_evaluation.blocks.items()
            },
            "cv_tailoring": self.current_evaluation.cv_tailoring_plan,
            "interview_stories_count": len(self.current_evaluation.interview_stories)
        }

    # --------------------------------------------------------------------------- #
    # 3e️⃣ Form filling (auto + HITL)
    # --------------------------------------------------------------------------- #
    def _fill_form(self, handler: BasePlatformHandler,
                   field_mappings: list):
        """
        Iterates over each field mapping:
        - High confidence (>0.85) → auto‑fill via Playwright.
        - Low confidence or flagged → pause for human input (HITL gate).
        - Sensitive fields (salary, SSN, payment) always trigger HITL.
        """
        browser = self.browser.page
        for mapping in field_mappings:
            fid = mapping["field_id"]
            value = mapping["candidate_value"]
            needs_hitl = mapping["requires_hitl"]
            reason = mapping.get("hitl_reason", "")

            if needs_hitl:
                logging.info(f"[Session] HITL field detected: {fid} (reason={reason})")
                self._emit_hitl_event(
                    gate_id=f"GATE_{fid.upper().replace('-', '_')}",
                    message=f"Field '{fid}' needs human input (reason: {reason})"
                )
                self._wait_for_gate_response()
                # After the human resolves the gate, they will have edited the
                # value via the UI; we read it back here:
                value = handler.get_human_filled_value(fid)
            else:
                # Auto‑fill
                try:
                    self._fill_single_field(fid, value)
                    logging.debug(f"[Session] Auto‑filled {fid} with {value}")
                except Exception as e:
                    logging.warning(f"[Session] Auto‑fill failed for {fid}: {e}")

        # After all fields are filled, click the final “Continue/Save” button
        # (handler‑specific helper)
        if hasattr(handler, "click_continue"):
            handler.click_continue(self.browser.page)
            logging.debug("[Session] Clicked 'Continue' after field fill")

    # --------------------------------------------------------------------------- #
    # 3f️⃣ Final gate (final submit)
    # --------------------------------------------------------------------------- #
    def _handle_final_gate(self, handler: BasePlatformHandler, fill_result: dict):
        """
        Triggers GATE_FINAL_SUBMIT.  The UI must show a full‑page screenshot
        and a confirmation button.  Only after the user clicks the button
        do we actually call handler.submit_application().
        """
        logging.info("[Session] Triggering final submit gate")
        self._emit_hitl_event(
            gate_id="GATE_FINAL_SUBMIT",
            message="Review the completed application form and click 'Submit Application' to finalize."
        )
        self._wait_for_gate_response()
        # At this point the UI will have called /gate-response/<session_id>
        # with a payload confirming the submit.  The orchestrator then calls:
        handler.submit_application(self.browser)

    # --------------------------------------------------------------------------- #
    # 3g️⃣ Finalization & cleanup
    # --------------------------------------------------------------------------- #
    def _finalize(self, handler: BasePlatformHandler):
        """
        Takes a screenshot of the confirmation page, archives the session,
        logs the outcome, and shuts down the browser.
        """
        # Capture final screenshot
        final_screenshot_path = self._checkpoint_state(step="final")
        logging.info(f"[Session] Final screenshot saved to {final_screenshot_path}")

        # Log success
        self.logger.log_success(
            session_id=handler.session_id,
            job_id=self.job_meta["id"],
            status="submitted",
            screenshot_dir=self.browser.session_dir
        )

        # Close browser
        self.browser.close()
        logging.info("[Session] Browser closed – session complete")

    # --------------------------------------------------------------------------- #
    # 4️⃣ HITL plumbing – notifications & response handling
    # --------------------------------------------------------------------------- #
    def _emit_hitl_event(self, gate_id: str, message: str):
        """
        Sends a notification to the Flask UI (via POST to /gate-notify/<session_id>)
        and logs the event locally.
        """
        # In a real implementation you would POST to the UI endpoint.
        # For this skeleton we just log; the UI can poll for new response files.
        logging.info(f"[HITL EVENT] {gate_id}: {message}")

        # Ensure the response file exists so the UI can read it
        resp_path = DATA_DIR / f"gates/{gate_id}_{self.current_handler.session_id}.response"
        os.makedirs(os.path.dirname(resp_path), exist_ok=True)
        with open(resp_path, "w") as f:
            f.write("{}")  # empty JSON placeholder

    def _wait_for_gate_response(self):
        """
        Blocks until a `.response` file appears in the gates directory.
        This is a naive poll; in production you could use websockets or
        a message queue.
        """
        import time
        resp_pattern = os.path.join(
            DATA_DIR, "gates", f"{'*'}_{self.current_handler.session_id}.response"
        )
        while not any(os.path.exists(f) for f in os.listdir(os.path.dirname(resp_pattern))):
            time.sleep(1)  # simple back‑off
        logging.debug("[Session] Gate response received – proceeding")

    # --------------------------------------------------------------------------- #
    # 5️⃣ Checkpoint helpers
    # --------------------------------------------------------------------------- #
    def _checkpoint_state(self, step: str = "checkpoint") -> str:
        """
        Serialises the current browser context (URL, cookies, entered values)
        into a JSON file under data/sessions/<session_id>/.
        Returns the file path for later retrieval.
        """
        session_dir = SESSIONS_DIR / self.current_handler.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            "url": self.browser.page.url,
            "cookies": self.browser.context.cookies,
            "step": step,
            "timestamp": datetime.utcnow().isoformat()
        }
        path = session_dir / f"checkpoint_{step}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)
        return str(path)

    def _load_checkpoint(self, path: str):
        """
        Restores a previously saved checkpoint (used after a crash or pause).
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.browser.context.update_storage_state({"cookies": data["cookies"]})
        self.browser.page.goto(data["url"])

# --------------------------------------------------------------------------- #
# Entry‑point for debugging / manual execution
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Example usage (replace paths with your actual locations)
    orchestrator = ApplicationOrchestrator(
        candidate_profile_path=Path("data/candidate_profile.json"),
        jobs_raw_path=Path("jobs_raw.json"),
        hitl_config_path=Path("config/hitl_config.json")
    )
    # Simulated launch – in practice this would be triggered by a UI or CLI command
    # orchestrator.start_application(job_id="4380364969", apply_url="https://grnh.se/10titkdq1us")