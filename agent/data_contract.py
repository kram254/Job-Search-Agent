from pathlib import Path

SYSTEM_FILES = [
    "agent/app.py",
    "agent/orchestrator.py",
    "agent/llm/field_mapper.py",
    "agent/llm/llm_client.py",
    "agent/scanner/portal_scanner.py",
    "agent/scanner/liveness_checker.py",
    "agent/services/pdf_generator.py",
    "agent/platforms/base.py",
    "agent/platforms/greenhouse.py",
    "agent/platforms/linkedin.py",
    "agent/platforms/indeed.py",
    "agent/platforms/ashby.py",
    "agent/browser/playwright_wrapper.py",
    "agent/browser/form_inventory.py",
    "agent/tracker/logger.py",
    "agent/tracker/story_bank.py",
    "agent/tracker/status_machine.py",
    "agent/tracker/followup_tracker.py",
    "agent/pipeline/pipeline_manager.py",
    "agent/batch/batch_processor.py",
    "agent/analytics/pattern_analyzer.py",
    "config/portals.yml",
    "config/hitl_config.json",
    "render.yaml",
    "requirements.txt"
]

USER_DATA_FILES = [
    "data/candidate_profile.json",
    "data/story_bank.json",
    "data/pipeline.json",
    "data/batch_state.json",
    "data/followups.json",
    "data/scan_history.json",
    "data/sessions/",
    "data/gates/",
    "data/logs/",
    "jobs_raw.json",
    "output/cvs/"
]

CV_FILES = [
    "CVs/"
]

NEVER_DELETE = USER_DATA_FILES + CV_FILES

NEVER_COMMIT = [
    "data/candidate_profile.json",
    ".env",
    "*.pem",
    "*.key"
]


def classify(path: str) -> str:
    p = str(path)
    for f in SYSTEM_FILES:
        if p.endswith(f) or p == f:
            return "system"
    for f in USER_DATA_FILES:
        if p.startswith(f) or p == f.rstrip("/"):
            return "user_data"
    for f in CV_FILES:
        if p.startswith(f):
            return "cv"
    return "unknown"


def is_safe_to_delete(path: str) -> bool:
    p = str(path)
    for protected in NEVER_DELETE:
        if p.startswith(protected) or p == protected.rstrip("/"):
            return False
    return True


def validate_paths(paths: list) -> dict:
    results = {}
    for path in paths:
        results[path] = {
            "classification": classify(path),
            "safe_to_delete": is_safe_to_delete(path),
            "safe_to_commit": path not in NEVER_COMMIT
        }
    return results
