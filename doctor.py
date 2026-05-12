#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "OK" if ok else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return ok


def run_checks() -> int:
    failures = 0
    base = Path(__file__).parent

    print("=== Job Search Agent Health Check ===\n")

    print("[1] Environment")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not check("ANTHROPIC_API_KEY set", bool(api_key)):
        failures += 1
    check("GEMINI_API_KEY set (optional)", bool(os.environ.get("GEMINI_API_KEY", "")))

    print("\n[2] Required files")
    required_files = [
        "agent/app.py",
        "agent/orchestrator.py",
        "agent/llm/field_mapper.py",
        "agent/services/pdf_generator.py",
        "agent/scanner/portal_scanner.py",
        "config/portals.yml",
        "requirements.txt"
    ]
    for f in required_files:
        if not check(f, (base / f).exists()):
            failures += 1

    print("\n[3] Data directories")
    data_dirs = ["data/sessions", "data/gates", "data/logs", "output/cvs"]
    for d in data_dirs:
        path = base / d
        path.mkdir(parents=True, exist_ok=True)
        check(d, path.exists(), "created if missing")

    print("\n[4] Candidate profile")
    profile_path = base / "data" / "candidate_profile.json"
    if profile_path.exists():
        try:
            with open(profile_path) as f:
                profile = json.load(f)
            check("profile loads", True)
            check("personal_details present", "personal_details" in profile)
            check("skills present", "skills" in profile)
        except json.JSONDecodeError as e:
            check("profile JSON valid", False, str(e))
            failures += 1
    else:
        check("candidate_profile.json exists", False, "create data/candidate_profile.json")
        failures += 1

    print("\n[5] Python imports")
    imports_ok = True
    critical_imports = [
        ("flask", "flask"),
        ("anthropic", "anthropic"),
        ("playwright.sync_api", "playwright"),
        ("yaml", "pyyaml"),
        ("requests", "requests")
    ]
    for module, pkg in critical_imports:
        try:
            __import__(module)
            check(f"import {module}", True)
        except ImportError:
            check(f"import {module}", False, f"pip install {pkg}")
            failures += 1
            imports_ok = False

    print("\n[6] Agent module imports")
    agent_modules = [
        "agent.app",
        "agent.orchestrator",
        "agent.llm.field_mapper",
        "agent.tracker.logger",
        "agent.tracker.story_bank",
        "agent.tracker.status_machine",
        "agent.tracker.followup_tracker",
        "agent.pipeline.pipeline_manager",
        "agent.batch.batch_processor",
        "agent.analytics.pattern_analyzer",
        "agent.llm.llm_client",
        "agent.data_contract"
    ]
    for module in agent_modules:
        try:
            os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-key-for-doctor")
            __import__(module)
            check(f"import {module}", True)
        except ImportError as e:
            check(f"import {module}", False, str(e))
            failures += 1
        except Exception as e:
            check(f"import {module}", False, f"runtime error: {e}")

    print("\n[7] Config validation")
    portals_path = base / "config" / "portals.yml"
    if portals_path.exists():
        try:
            import yaml
            with open(portals_path) as f:
                portals = yaml.safe_load(f)
            companies = portals.get("tracked_companies", [])
            check("portals.yml loads", True)
            check(f"tracked_companies count", len(companies) >= 10, f"{len(companies)} companies")
        except Exception as e:
            check("portals.yml loads", False, str(e))
            failures += 1
    else:
        check("portals.yml exists", False)
        failures += 1

    print(f"\n{'='*38}")
    if failures == 0:
        print("All checks passed.")
    else:
        print(f"{failures} check(s) failed. See above for details.")

    return failures


if __name__ == "__main__":
    sys.exit(run_checks())
