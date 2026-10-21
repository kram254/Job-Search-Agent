from flask import Flask, request, jsonify, Response, stream_with_context, send_file
from pathlib import Path
import os
import json
import logging
import queue
import re
import threading
import time
from flask_cors import CORS
from agent.orchestrator import ApplicationOrchestrator

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent.parent
CANDIDATE_PROFILE = BASE_DIR / "data" / "candidate_profile.json"
JOBS_RAW = BASE_DIR / "jobs_raw.json"
HITL_CONFIG = BASE_DIR / "config" / "hitl_config.json"
SESSIONS_DIR = BASE_DIR / "data" / "sessions"
GATES_DIR = BASE_DIR / "data" / "gates"
DATA_DIR = BASE_DIR / "data"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
GATES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

_sse_clients: list = []
_sse_lock = threading.Lock()

# JobRight-parity Phase 4 (additive): in-memory cache of the last parsed CV,
# bridging /profile/import -> /profile/import/confirm without persisting
# candidate data anywhere new.
_parsed_cache: dict = {'latest': None}

# Async-apply registry (bulk-apply fix): apply workflows run in background
# threads; /approve returns an apply_job_id and /apply-status/<id> reports
# progress. In-memory by design (worker restart = jobs lost, acceptable for
# a single-user tool).
_apply_jobs: dict = {}


def datetime_infix() -> str:
    """Timestamp fragment for temp upload filenames."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def datetime_now_iso() -> str:
    """ISO timestamp for persisted records (discover-persistence fix)."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def sanitize_job_description(text: str) -> str:
    """HTML/mojibake cleanup for scraped descriptions (UI-readability fix).

    Scraped descriptions arrive as raw HTML (p tags, li tags, inline styles)
    with double-encoded entities (Â artifacts). Strip to clean plain text so
    the frontend renders readable paragraphs instead of markup.
    """
    if not text:
        return ""
    t = str(text)
    # 1) mojibake: UTF-8 bytes mis-decoded as latin-1/cp1252 ("Â â€™" etc.)
    try:
        t = t.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    # 2) block-level tags become newlines; <li> becomes a bullet
    t = re.sub(r"(?i)</p\s*>|<br\s*/?>|</div\s*>|</h[1-6]\s*>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "\n- ", t)
    # 3) drop every remaining tag (style attrs, strong, spans...)
    t = re.sub(r"<[^>]+>", " ", t)
    # 4) decode entities (&amp; &nbsp; &#163; ...)
    import html as _html
    t = _html.unescape(t)
    # 5) collapse whitespace runs, trim per line
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in t.splitlines()]
    return "\n".join(ln for ln in lines if ln)

orchestrator = None


def get_orchestrator():
    global orchestrator
    if orchestrator is None:
        orchestrator = ApplicationOrchestrator(
            candidate_profile_path=CANDIDATE_PROFILE,
            jobs_raw_path=JOBS_RAW,
            hitl_config_path=HITL_CONFIG
        )
    return orchestrator


def _broadcast_event(event_type: str, data: dict):
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


@app.route('/output/cvs/<path:filename>', methods=['GET'])
def serve_cv_file(filename):
    cv_dir = BASE_DIR / "output" / "cvs"
    filepath = cv_dir / filename
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(filepath), as_attachment=True, download_name=filename, mimetype='application/pdf')


@app.route('/cover-letter', methods=['POST'])
def cover_letter():
    data = request.json or {}
    job_description = data.get('job_description', '')
    company = data.get('company', '')
    title = data.get('title', '')
    archetype = data.get('archetype', 'agentic_automation')
    if not job_description and not title:
        return jsonify({"error": "Provide job_description or title"}), 400
    try:
        orch = get_orchestrator()
        profile = orch.candidate_profile
        name = profile.get("personal_details", {}).get("name", "Emmanuel Ndaliro").title()
        summary = profile.get("narrative", {}).get("professional_summary", "")
        proof_points = profile.get("proof_points", [])
        github = profile.get("professional_profiles", {}).get("github", "")
        linkedin = profile.get("professional_profiles", {}).get("linkedin", "")
        proof_text = "\n".join(f"- {p['metric']} ({p['context']})" for p in proof_points[:3])
        jd_snippet = job_description[:800] if job_description else f"{title} at {company}"
        prompt = f"""Write a concise, powerful cover letter (3-4 paragraphs, under 250 words) for:

CANDIDATE: {name}
SUMMARY: {summary}
PROOF POINTS:
{proof_text}
ROLE: {title} at {company}
ARCHETYPE: {archetype}
JD EXCERPT: {jd_snippet}

Rules:
- First paragraph: hook with a specific achievement + why THIS company/role
- Second paragraph: top 2-3 relevant proof points tied to JD requirements
- Third paragraph: brief forward-looking close with specific ask
- Tone: direct, technically credible, never hollow phrases like "I am passionate"
- Sign off as {name} with {github} and {linkedin}

Output ONLY the letter text, no subject line, no meta commentary."""
        from agent.llm.llm_client import LLMClient
        client = LLMClient()
        letter = client.complete(prompt, system="You write concise, technically credible cover letters.", max_tokens=600, temperature=0.4)
        return jsonify({"letter": letter, "company": company, "title": title, "archetype": archetype})
    except Exception as e:
        logging.exception("cover-letter error")
        return jsonify({"error": str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "job-search-agent",
        "status": "healthy",
        "endpoints": [
            "/health", "/jobs", "/sessions", "/applications",
            "/discover", "/approve", "/evaluate", "/outreach",
            "/analytics/overview", "/analytics/patterns",
            "/pipeline", "/follow-ups", "/providers", "/stream"
        ]
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})


@app.route('/apply', methods=['POST'])
def apply():
    data = request.json or {}
    job_id = data.get('job_id')
    apply_url = data.get('apply_url')
    mode = data.get('mode', 'draft')
    cv_path = data.get('cv_path', 'cv.md')

    if not job_id or not apply_url:
        return jsonify({"error": "Missing job_id or apply_url"}), 400

    try:
        orch = get_orchestrator()
        result = orch.run_apply_mode(job_id=job_id, apply_url=apply_url, cv_path=cv_path, mode=mode)
        return jsonify(result)
    except Exception as e:
        logging.exception("apply error")
        return jsonify({"error": str(e)}), 500


@app.route('/apply-from-url', methods=['POST'])
def apply_from_url():
    data = request.json or {}
    url = data.get('url')
    mode = data.get('mode', 'draft')
    cv_path = data.get('cv_path', 'cv.md')
    title = data.get('title', '')
    company = data.get('company', '')

    if not url:
        return jsonify({"error": "Missing url"}), 400

    try:
        orch = get_orchestrator()
        result = orch.start_from_url(
            apply_url=url,
            mode=mode,
            cv_path=cv_path,
            title=title,
            company=company
        )
        _broadcast_event("application_started", {"url": url, "mode": mode, "status": result.get("status")})
        return jsonify(result)
    except Exception as e:
        logging.exception("apply-from-url error")
        return jsonify({"error": str(e)}), 500


@app.route('/sessions/<session_id>/submit', methods=['POST'])
def submit_draft_session(session_id):
    try:
        orch = get_orchestrator()
        result = orch.submit_draft(session_id)
        if result.get("status") == "error":
            return jsonify(result), 400
        _broadcast_event("draft_submitted", {"session_id": session_id})
        return jsonify(result)
    except Exception as e:
        logging.exception("submit draft error")
        return jsonify({"error": str(e)}), 500


@app.route('/schedule', methods=['GET'])
def list_schedules():
    try:
        from agent.scheduler.scan_scheduler import ScanScheduler
        scheduler = ScanScheduler(schedule_path=str(DATA_DIR / "schedule.json"))
        schedules = scheduler.get_schedules()
        due = scheduler.get_due()
        return jsonify({"schedules": schedules, "due_count": len(due)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/schedule', methods=['POST'])
def create_schedule():
    data = request.json or {}
    cv_path = data.get('cv_path', 'cv.md')
    interval_days = int(data.get('interval_days', 2))
    role_keywords = data.get('role_keywords', [])
    config_path = data.get('config_path', 'config/portals.yml')
    label = data.get('label', '')

    try:
        from agent.scheduler.scan_scheduler import ScanScheduler
        scheduler = ScanScheduler(schedule_path=str(DATA_DIR / "schedule.json"))
        schedule_id = scheduler.add_schedule(
            cv_path=cv_path,
            interval_days=interval_days,
            role_keywords=role_keywords,
            config_path=config_path,
            label=label
        )
        return jsonify({"schedule_id": schedule_id, "status": "created", "interval_days": interval_days})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/schedule/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    try:
        from agent.scheduler.scan_scheduler import ScanScheduler
        scheduler = ScanScheduler(schedule_path=str(DATA_DIR / "schedule.json"))
        removed = scheduler.remove(schedule_id)
        if not removed:
            return jsonify({"error": "Schedule not found"}), 404
        return jsonify({"status": "removed", "schedule_id": schedule_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/schedule/<schedule_id>/run', methods=['POST'])
def run_schedule_now(schedule_id):
    try:
        from agent.scheduler.scan_scheduler import ScanScheduler
        scheduler = ScanScheduler(schedule_path=str(DATA_DIR / "schedule.json"))
        schedules = scheduler.get_schedules()
        target = next((s for s in schedules if s["id"] == schedule_id), None)
        if not target:
            return jsonify({"error": "Schedule not found"}), 404

        orch = get_orchestrator()
        result = scheduler._run_schedule(target, orch.candidate_profile, str(JOBS_RAW))
        scheduler.mark_ran(schedule_id)

        _broadcast_event("scan_complete", {"schedule_id": schedule_id, **result})
        return jsonify({"schedule_id": schedule_id, "status": "ran", "result": result})
    except Exception as e:
        logging.exception("schedule run error")
        return jsonify({"error": str(e)}), 500


@app.route('/gate-response/<session_id>', methods=['POST'])
def gate_response(session_id):
    data = request.json
    gate_id = data.get('gate_id')
    response_data = data.get('response')

    if not gate_id:
        return jsonify({"error": "Missing gate_id"}), 400

    resp_path = GATES_DIR / f"{gate_id}_{session_id}.response"
    with open(resp_path, "w") as f:
        json.dump(response_data, f)

    _broadcast_event("gate_resolved", {"gate_id": gate_id, "session_id": session_id})
    return jsonify({"status": "response_received"})


@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.json or {}
    job_id = data.get('job_id')
    job_description = data.get('job_description', '')
    cv_path = data.get('cv_path', 'cv.md')

    if not job_id and not job_description:
        return jsonify({"error": "Provide job_id or job_description"}), 400

    try:
        orch = get_orchestrator()

        if job_id and not job_description:
            job_meta = next((j for j in orch.jobs_raw if j["id"] == job_id), None)
            if not job_meta:
                return jsonify({"error": f"Job {job_id} not found"}), 404
            job_description = job_meta.get("description", "")

        from agent.llm.field_mapper import FieldMapper

        cv_text = ""
        cv_file = Path(cv_path)
        if cv_file.exists():
            cv_text = cv_file.read_text(encoding="utf-8")

        mapper = FieldMapper(
            candidate_profile=orch.candidate_profile,
            job_description=job_description,
            cv_text=cv_text
        )
        evaluation = mapper.evaluate_job()
        summary = mapper.get_evaluation_summary()

        return jsonify({
            "job_id": job_id,
            "archetype": summary["archetype"],
            "confidence": summary["confidence"],
            "global_score": summary["global_score"],
            "recommendation": summary["recommendation"],
            "scores": summary["scores"],
            "cv_tailoring": summary["cv_tailoring"],
            "interview_stories_count": summary["interview_stories_count"]
        })
    except Exception as e:
        logging.exception("evaluate error")
        return jsonify({"error": str(e)}), 500


@app.route('/generate-cv', methods=['POST'])
def generate_cv():
    data = request.json or {}
    job_id = data.get('job_id')
    job_description = data.get('job_description', '')
    cv_path = data.get('cv_path', 'cv.md')
    archetype = data.get('archetype', 'general')
    company_name = data.get('company', 'company')

    if not job_id and not job_description:
        return jsonify({"error": "Provide job_id or job_description"}), 400

    try:
        orch = get_orchestrator()

        if job_id and not job_description:
            job_meta = next((j for j in orch.jobs_raw if j["id"] == job_id), None)
            if not job_meta:
                return jsonify({"error": f"Job {job_id} not found"}), 404
            job_description = job_meta.get("description", "")
            company_name = job_meta.get("company", company_name)
            archetype = data.get('archetype', 'general')

        from agent.services.pdf_generator import PDFGenerator
        generator = PDFGenerator(output_dir=str(BASE_DIR / "output" / "cvs"))
        result = generator.generate_tailored_cv(
            cv_markdown_path=cv_path,
            job_description=job_description,
            candidate_profile=orch.candidate_profile,
            archetype=archetype,
            company_name=company_name
        )

        return jsonify({
            "pdf_path": result.pdf_path,
            "page_count": result.page_count,
            "file_size_kb": result.file_size_kb,
            "keywords_injected": result.keywords_injected,
            "coverage_percentage": result.coverage_percentage,
            "format": result.format_used
        })
    except Exception as e:
        logging.exception("generate-cv error")
        return jsonify({"error": str(e)}), 500


@app.route('/scan', methods=['POST'])
def scan():
    data = request.json or {}
    config_path = data.get('config_path', 'config/portals.yml')

    try:
        from agent.browser.playwright_wrapper import BrowserWrapper
        from agent.scanner.portal_scanner import PortalScanner
        import asyncio

        browser = BrowserWrapper(headless=True)
        browser.launch(headless=True)

        scanner = PortalScanner(
            browser=browser,
            config_path=config_path,
            history_path=str(BASE_DIR / "data" / "scan_history.json")
        )

        result = asyncio.run(scanner.run_full_scan())
        scanner.export_to_jobs_raw(result, str(JOBS_RAW))
        browser.close()

        # JobRight-parity Phase 3 hook (additive): generate alerts for new
        # high-match listings. Isolated in try/except so the scan's own
        # behavior and response are completely unchanged if it fails.
        try:
            from agent.alerts.alert_engine import evaluate_listings_for_alerts
            scan_listings = [
                {"title": l.title, "company": l.company, "url": l.url,
                 "location": l.location, "score": l.score}
                for l in result.listings
            ]
            fresh_alerts = evaluate_listings_for_alerts(
                scan_listings,
                alerts_path=str(DATA_DIR / "alerts.json"),
            )
            if fresh_alerts:
                _broadcast_event("alerts_new", {"count": len(fresh_alerts)})
        except Exception as _alert_err:
            logging.warning(f"alert generation skipped: {_alert_err}")

        _broadcast_event("scan_complete", {
            "total_found": result.total_found,
            "added": result.added_to_pipeline,
            "filtered": result.filtered_out,
            "duration_s": result.scan_duration_seconds
        })

        return jsonify({
            "total_found": result.total_found,
            "added_to_pipeline": result.added_to_pipeline,
            "filtered_out": result.filtered_out,
            "duplicates_skipped": result.duplicates_skipped,
            "expired_skipped": result.expired_skipped,
            "duration_seconds": result.scan_duration_seconds,
            "listings": [
                {
                    "title": l.title,
                    "company": l.company,
                    "url": l.url,
                    "location": l.location,
                    "score": l.score,
                    "detected_via": l.detected_via.value
                }
                for l in result.listings
            ]
        })
    except Exception as e:
        logging.exception("scan error")
        return jsonify({"error": str(e)}), 500


@app.route('/sessions', methods=['GET'])
def list_sessions():
    sessions = []
    if SESSIONS_DIR.exists():
        for session_dir in sorted(SESSIONS_DIR.iterdir(), reverse=True):
            if not session_dir.is_dir():
                continue
            checkpoints = list(session_dir.glob("checkpoint_*.json"))
            latest = None
            if checkpoints:
                latest_file = max(checkpoints, key=lambda p: p.stat().st_mtime)
                try:
                    with open(latest_file) as f:
                        latest = json.load(f)
                except Exception:
                    pass
            sessions.append({
                "session_id": session_dir.name,
                "checkpoints": len(checkpoints),
                "latest": latest
            })
    return jsonify({"sessions": sessions})


@app.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    session_dir = SESSIONS_DIR / session_id
    if not session_dir.exists():
        return jsonify({"error": "Session not found"}), 404

    checkpoints = []
    for cp in sorted(session_dir.glob("checkpoint_*.json")):
        try:
            with open(cp) as f:
                checkpoints.append(json.load(f))
        except Exception:
            pass

    gates = []
    for gf in GATES_DIR.glob(f"*_{session_id}.response"):
        try:
            with open(gf) as f:
                gates.append({"gate_id": gf.stem.replace(f"_{session_id}", ""), "response": json.load(f)})
        except Exception:
            pass

    return jsonify({"session_id": session_id, "checkpoints": checkpoints, "gates": gates})


@app.route('/stream', methods=['GET'])
def stream():
    q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route('/jobs', methods=['GET'])
def list_jobs():
    min_score = float(request.args.get('min_score', 0))
    limit = int(request.args.get('limit', 50))
    try:
        with open(JOBS_RAW) as f:
            jobs = json.load(f)
        if min_score > 0:
            jobs = [j for j in jobs if float(j.get('score', 0)) >= min_score]
        return jsonify({"jobs": jobs[:limit], "total": len(jobs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    try:
        with open(JOBS_RAW) as f:
            jobs = json.load(f)
        job = next((j for j in jobs if j.get("id") == job_id), None)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/liveness', methods=['POST'])
def liveness():
    data = request.json or {}
    url = data.get('url', '')
    if not url:
        return jsonify({"error": "Missing url"}), 400
    try:
        from agent.scanner.liveness_checker import LivenessChecker
        checker = LivenessChecker()
        is_live, reason = checker.check(url)
        return jsonify({"url": url, "is_live": is_live, "reason": reason})
    except Exception as e:
        logging.exception("liveness error")
        return jsonify({"error": str(e)}), 500


@app.route('/normalize-statuses', methods=['POST'])
def normalize_statuses():
    data = request.json or {}
    statuses = data.get('statuses', [])
    if not statuses:
        return jsonify({"error": "Provide statuses list"}), 400
    try:
        from agent.tracker.status_machine import StatusMachine
        sm = StatusMachine()
        normalized = [{"raw": s, "canonical": sm.normalize(s), "description": sm.describe(s)} for s in statuses]
        return jsonify({"normalized": normalized})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/story-bank', methods=['GET'])
def list_stories():
    archetype = request.args.get('archetype')
    tags = request.args.getlist('tag')
    limit = int(request.args.get('limit', 20))
    try:
        from agent.tracker.story_bank import StoryBank
        bank = StoryBank(storage_path=str(DATA_DIR / "story_bank.json"))
        stories = bank.lookup(archetype=archetype or None, tags=tags or None, limit=limit)
        return jsonify({"stories": stories, "stats": bank.stats()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/story-bank', methods=['POST'])
def add_story():
    data = request.json or {}
    try:
        from agent.tracker.story_bank import StoryBank
        bank = StoryBank(storage_path=str(DATA_DIR / "story_bank.json"))
        story_id = bank.append(data)
        return jsonify({"story_id": story_id, "status": "added"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/pipeline', methods=['GET'])
def list_pipeline():
    try:
        from agent.pipeline.pipeline_manager import PipelineManager
        pm = PipelineManager(pipeline_path=str(DATA_DIR / "pipeline.json"))
        return jsonify({"entries": pm.all(), "stats": pm.stats()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/pipeline', methods=['POST'])
def add_to_pipeline():
    data = request.json or {}
    if isinstance(data, list):
        items = data
    else:
        items = [data] if data.get('url') else data.get('items', [])

    if not items:
        return jsonify({"error": "Provide url or items list"}), 400

    try:
        from agent.pipeline.pipeline_manager import PipelineManager
        pm = PipelineManager(pipeline_path=str(DATA_DIR / "pipeline.json"))
        ids = pm.add_batch(items)
        return jsonify({"added": len(ids), "ids": ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/pipeline/process', methods=['POST'])
def process_pipeline():
    data = request.json or {}
    limit = int(data.get('limit', 10))
    try:
        from agent.pipeline.pipeline_manager import PipelineManager
        from agent.llm.field_mapper import FieldMapper

        pm = PipelineManager(pipeline_path=str(DATA_DIR / "pipeline.json"))
        pending = pm.get_pending(limit=limit)

        orch = get_orchestrator()
        processed = []

        for entry in pending:
            pm.mark_processing(entry["id"])
            try:
                jd = entry.get("metadata", {}).get("description", entry.get("title", ""))
                mapper = FieldMapper(
                    candidate_profile=orch.candidate_profile,
                    job_description=jd
                )
                summary = mapper.get_evaluation_summary()
                pm.mark_done(entry["id"], result=summary)
                processed.append({"id": entry["id"], "status": "done", "score": summary.get("global_score")})
            except Exception as e:
                pm.mark_failed(entry["id"], error=str(e))
                processed.append({"id": entry["id"], "status": "failed", "error": str(e)})

        _broadcast_event("pipeline_processed", {"count": len(processed)})
        return jsonify({"processed": len(processed), "results": processed})
    except Exception as e:
        logging.exception("pipeline/process error")
        return jsonify({"error": str(e)}), 500


@app.route('/batch', methods=['POST'])
def batch_evaluate():
    data = request.json or {}
    items = data.get('items', [])
    batch_id = data.get('batch_id')

    if not items:
        return jsonify({"error": "Provide items list"}), 400

    try:
        from agent.batch.batch_processor import BatchProcessor
        from agent.llm.field_mapper import FieldMapper

        orch = get_orchestrator()

        def evaluate_item(item: dict) -> dict:
            jd = item.get("description", item.get("title", ""))
            mapper = FieldMapper(
                candidate_profile=orch.candidate_profile,
                job_description=jd
            )
            return mapper.get_evaluation_summary()

        processor = BatchProcessor(state_path=str(DATA_DIR / "batch_state.json"))
        summary = processor.process(items, evaluate_item, batch_id=batch_id)
        return jsonify(summary)
    except Exception as e:
        logging.exception("batch error")
        return jsonify({"error": str(e)}), 500


@app.route('/follow-ups', methods=['GET'])
def list_followups():
    try:
        from agent.tracker.followup_tracker import FollowUpTracker
        tracker = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
        due = tracker.get_due()
        return jsonify({"due": due, "stats": tracker.stats(), "active": tracker.all_active()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/follow-ups', methods=['POST'])
def track_followup():
    data = request.json or {}
    job_id = data.get('job_id')
    company = data.get('company', '')
    title = data.get('title', '')
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400
    try:
        from agent.tracker.followup_tracker import FollowUpTracker
        tracker = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
        record_id = tracker.track(
            job_id=job_id,
            company=company,
            title=title,
            applied_at=data.get('applied_at'),
            contact_name=data.get('contact_name', ''),
            archetype=data.get('archetype', '')
        )
        return jsonify({"record_id": record_id, "status": "tracking"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/providers', methods=['GET'])
def list_providers():
    try:
        from agent.llm.llm_client import LLMClient
        client = LLMClient()
        return jsonify(client.provider_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/models', methods=['GET'])
def list_models():
    source = request.args.get('source', 'all')
    try:
        from agent.llm.llm_client import LLMClient
        client = LLMClient()
        result: dict = {}
        if source in ('all', 'openrouter'):
            category = request.args.get('category', '')
            result['openrouter'] = client.list_openrouter_models(category or None)
        if source in ('all', 'ollama'):
            result['ollama'] = client.list_ollama_models()
        if source == 'all':
            result['hermes'] = {
                'openrouter': LLMClient.HERMES_OR_MODEL,
                'ollama':     LLMClient.HERMES_OLLAMA_MODEL,
            }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/llm/complete', methods=['POST'])
def llm_complete():
    data = request.json or {}
    prompt   = data.get('prompt', '')
    system   = data.get('system', '')
    provider = data.get('provider', '')
    model    = data.get('model', '')
    max_tokens  = int(data.get('max_tokens', 1024))
    temperature = float(data.get('temperature', 0.3))
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400
    try:
        from agent.llm.llm_client import LLMClient
        client = LLMClient()
        if provider:
            result = client.complete_with_provider(
                provider, prompt, system=system,
                max_tokens=max_tokens, temperature=temperature,
                model=model or None,
            )
        else:
            result = client.complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        return jsonify({"result": result, "provider": provider or client.provider()})
    except Exception as e:
        logging.exception("llm/complete error")
        return jsonify({"error": str(e)}), 500


@app.route('/composio/connect', methods=['POST'])
def composio_connect():
    data = request.json or {}
    app_name = data.get('app', '')
    if not app_name:
        return jsonify({"error": "Missing app name (e.g. telegram, slack, gmail)"}), 400
    try:
        from agent.digest.notifier import ComposioNotifier
        cn = ComposioNotifier()
        redirect_url = cn.get_connection_url(app_name)
        if redirect_url:
            return jsonify({"app": app_name, "connect_url": redirect_url})
        return jsonify({"error": "Could not get connection URL. Check COMPOSIO_API_KEY."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/composio/connections', methods=['GET'])
def composio_connections():
    try:
        from agent.digest.notifier import ComposioNotifier
        cn = ComposioNotifier()
        return jsonify({"connections": cn.get_connections()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/composio/send', methods=['POST'])
def composio_send():
    data = request.json or {}
    channel  = data.get('channel', 'telegram')
    jobs     = data.get('jobs', [])
    intro    = data.get('intro', '')
    target   = data.get('target', '')
    if not jobs:
        return jsonify({"error": "Provide jobs list"}), 400
    try:
        from agent.digest.notifier import ComposioNotifier
        cn = ComposioNotifier()
        if channel == 'telegram':
            ok = cn.send_telegram(jobs, intro=intro, chat_id=target or None)
        elif channel == 'slack':
            ok = cn.send_slack(jobs, intro=intro, channel=target or None)
        elif channel == 'whatsapp':
            ok = cn.send_whatsapp(jobs, intro=intro, to_number=target or None)
        elif channel == 'gmail':
            ok = cn.send_gmail(jobs, intro=intro, to_email=target or None)
        else:
            return jsonify({"error": f"Unknown channel '{channel}'. Use telegram|slack|whatsapp|gmail"}), 400
        return jsonify({"channel": channel, "sent": ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/feedback', methods=['POST'])
def record_feedback():
    data = request.json or {}
    job_id = data.get('job_id', '')
    outcome = data.get('outcome', '')
    if not job_id or outcome not in ('positive', 'negative'):
        return jsonify({"error": "Provide job_id and outcome (positive|negative)"}), 400
    try:
        from agent.ranking.feedback_ranker import FeedbackRanker
        orch = get_orchestrator()
        listing = next((j for j in orch.jobs_raw if j.get("id") == job_id), {})
        ranker = FeedbackRanker(data_path=str(DATA_DIR / "feedback_signals.json"))
        ranker.record_outcome(job_id=job_id, listing=listing, outcome=outcome)
        _broadcast_event("feedback_recorded", {"job_id": job_id, "outcome": outcome})
        return jsonify({"status": "recorded", "job_id": job_id, "outcome": outcome})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/analytics/overview', methods=['GET'])
def analytics_overview():
    try:
        from agent.analytics.pattern_analyzer import PatternAnalyzer
        analyzer = PatternAnalyzer(
            sessions_dir=str(SESSIONS_DIR),
            jobs_raw_path=str(JOBS_RAW)
        )
        return jsonify(analyzer.overview())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/analytics/patterns', methods=['GET'])
def analytics_patterns():
    try:
        from agent.analytics.pattern_analyzer import PatternAnalyzer
        analyzer = PatternAnalyzer(
            sessions_dir=str(SESSIONS_DIR),
            jobs_raw_path=str(JOBS_RAW)
        )
        return jsonify({
            "conversion_by_score_band": analyzer.conversion_by_score_band(),
            "rejection_by_archetype": analyzer.rejection_by_archetype(),
            "top_companies_by_response": analyzer.top_companies_by_response(),
            "score_vs_outcome_correlation": analyzer.score_vs_outcome_correlation()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/calibrate-style', methods=['POST'])
def calibrate_style():
    data = request.json or {}
    samples = data.get('writing_samples', [])
    if not samples:
        return jsonify({"error": "Provide writing_samples list"}), 400
    try:
        from agent.llm.field_mapper import FieldMapper
        mapper = FieldMapper(
            candidate_profile={},
            job_description="",
            writing_samples=samples
        )
        profile = mapper.calibrate_style(samples)
        return jsonify(profile)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/deep-research', methods=['POST'])
def deep_research():
    data = request.json or {}
    job_description = data.get('job_description', '')
    company = data.get('company', '')
    if not job_description:
        return jsonify({"error": "Provide job_description"}), 400
    try:
        from agent.llm.field_mapper import FieldMapper
        orch = get_orchestrator()
        mapper = FieldMapper(
            candidate_profile=orch.candidate_profile,
            job_description=job_description
        )
        evaluation = mapper.evaluate_job()
        summary = mapper.get_evaluation_summary()

        archetype_keywords = mapper._get_archetype_keywords(evaluation.archetype)
        stories = evaluation.interview_stories

        research_output = {
            "archetype": summary["archetype"],
            "confidence": summary["confidence"],
            "global_score": summary["global_score"],
            "recommendation": summary["recommendation"],
            "scores": summary["scores"],
            "posting_legitimacy": summary.get("posting_legitimacy"),
            "cv_tailoring": summary["cv_tailoring"],
            "archetype_keywords": archetype_keywords,
            "interview_stories": stories,
            "application_answer_why": mapper.generate_application_answer(
                "Why do you want to work here?", company=company
            ),
            "application_answer_strength": mapper.generate_application_answer(
                "What is your greatest strength?", company=company
            )
        }
        return jsonify(research_output)
    except Exception as e:
        logging.exception("deep-research error")
        return jsonify({"error": str(e)}), 500


@app.route('/outreach', methods=['POST'])
def outreach():
    data = request.json or {}
    job_id = data.get('job_id', '')
    company = data.get('company', '')
    domain = data.get('domain', '')
    job_description = data.get('job_description', '')
    archetype = data.get('archetype', 'agentic_automation')

    try:
        orch = get_orchestrator()

        job_meta = {}
        if job_id:
            job_meta = next((j for j in orch.jobs_raw if j.get("id") == job_id), {})
            if not job_description:
                job_description = job_meta.get("description", "")
            if not company:
                company = job_meta.get("company", "")
            if not domain:
                domain = job_meta.get("domain", "")

        contact = None
        hunter_key = os.environ.get("HUNTER_API_KEY", "")
        lookup_domain = domain or (company.lower().replace(" ", "") + ".com" if company else "")
        if hunter_key and lookup_domain:
            try:
                from agent.outreach.contact_lookup import ContactLookup
                lkp = ContactLookup(api_key=hunter_key)
                contact = lkp.lookup(lookup_domain)
            except Exception as _le:
                logging.warning(f"Hunter.io lookup failed: {_le}")

        if contact is None:
            contact = {
                "name": data.get('contact_name', ''),
                "title": data.get('contact_title', ''),
                "email": data.get('contact_email', ''),
                "confidence": 0,
                "domain": lookup_domain,
            }

        from agent.mcp_server import _handle_score_job_fit
        candidate_skills = (
            orch.candidate_profile.get("skills", {}).get("primary", []) +
            orch.candidate_profile.get("skills", {}).get("secondary", [])
        )
        fit = {}
        if job_description:
            fit = _handle_score_job_fit({"job_description": job_description, "candidate_skills": candidate_skills})

        evaluation_ctx = {
            "archetype": archetype,
            "matched_skills": fit.get("matched_skills", []),
            "missing_skills": fit.get("missing_skills", []),
            "quality_gate": fit.get("quality_gate", {"final_score": 80}),
        }

        from agent.outreach.email_generator import EmailGenerator
        gen = EmailGenerator()
        result = gen.generate(
            profile=orch.candidate_profile,
            job_meta={**job_meta, "company": company, "description": job_description},
            contact=contact,
            evaluation=evaluation_ctx,
        )

        return jsonify({
            "subject": result.get("subject", ""),
            "body": result.get("body", ""),
            "contact": contact,
            "matched_skills": fit.get("matched_skills", []),
            "archetype": archetype,
            "word_count": result.get("word_count", 0),
        })
    except Exception as e:
        logging.exception("outreach error")
        return jsonify({"error": str(e)}), 500


@app.route('/discover', methods=['POST'])
def discover():
    data = request.json or {}
    sources = data.get('sources', ['remoteok', 'linkedin'])
    top_n = int(data.get('top_n', 5))
    keywords = data.get('keywords', 'AI engineer LLM machine learning agentic')

    try:
        from agent.digest.daily_digest import DailyDigest
        orch = get_orchestrator()
        candidate_skills = (
            orch.candidate_profile.get("skills", {}).get("primary", []) +
            orch.candidate_profile.get("skills", {}).get("secondary", [])
        )

        digest = DailyDigest(
            candidate_skills=candidate_skills,
            linkedin_keywords=keywords,
            top_n=top_n,
            output_dir=str(BASE_DIR / "output"),
        )
        result = digest.run()

        # Additive (dashboard-persistence fix): persist every scraped job into
        # jobs_raw.json — the file /jobs and the dashboard read from. Previously
        # discover results only went to output/digest_*.json + notifications,
        # so scraped jobs never appeared in the UI. Mirrors what /scan does via
        # export_to_jobs_raw. Wrapped in try/except: discovery's own response
        # and notifications are unaffected if persistence fails.
        persisted = {"added": 0, "total_in_feed": 0}
        id_by_url = {}  # url -> final feed id, so the response can link correctly
        try:
            all_jobs = result.get("all_jobs") or []
            with open(JOBS_RAW) as _f:
                existing_jobs = json.load(_f)
            existing_urls = {str(j.get("url") or j.get("link") or "") for j in existing_jobs}
            existing_urls.discard("")
            # index existing feed entries by url too, so already-known jobs can
            # still be linked from the discovery response (404-link fix)
            existing_id_by_url = {
                str(j.get("url") or j.get("link") or ""): str(j.get("id"))
                for j in existing_jobs
            }
            next_id = max([int(j.get("id")) for j in existing_jobs if str(j.get("id", "")).isdigit()] or [0]) + 1
            added = 0
            for job in all_jobs:
                url = str(job.get("url") or "")
                if not url:
                    continue
                if url in existing_urls:
                    # 404-link fix: remember the EXISTING feed id for this url
                    if url in existing_id_by_url:
                        id_by_url[url] = existing_id_by_url[url]
                    continue
                # prefer the scraper's own stable id when it is numeric and not
                # already taken in the feed (keeps Discover page links and feed
                # ids in sync); otherwise continue the sequential counter
                scrape_id = str(job.get("id") or "")
                taken_ids = {str(j.get("id")) for j in existing_jobs}
                if scrape_id.isdigit() and scrape_id not in taken_ids:
                    entry_id = scrape_id
                    if int(scrape_id) >= next_id:
                        next_id = int(scrape_id) + 1
                else:
                    entry_id = str(next_id)
                    next_id += 1
                entry = {
                    "id": entry_id,
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "url": url,
                    "location": job.get("location", ""),
                    "description": sanitize_job_description(job.get("description", "")),
                    "score": job.get("score", 0),
                    "match_ratio": job.get("match_ratio", 0),
                    "matched_skills": job.get("matched_skills", []),
                    "source": job.get("source", "remoteok"),
                    "salary_range": job.get("salary_range", ""),
                    "discovered_at": datetime_now_iso(),
                }
                existing_jobs.append(entry)
                existing_urls.add(url)
                id_by_url[url] = entry_id
                added += 1
            if added:
                with open(JOBS_RAW, "w") as _f:
                    json.dump(existing_jobs, _f, indent=2)
            # stale-memory fix: the orchestrator loads jobs_raw once at
            # construction; refresh its in-memory copy so detail routes
            # (match-explanation, evaluate, outreach) see discovered jobs too
            try:
                orch = get_orchestrator()
                orch.jobs_raw = existing_jobs
            except Exception:
                pass
            persisted = {"added": added, "total_in_feed": len(existing_jobs)}
            logging.info(f"discover persistence: +{added} jobs (feed now {len(existing_jobs)})")
        except Exception as _persist_err:
            logging.warning(f"discover persistence skipped: {_persist_err}")

        # Alert-engine hook for discover (same as /scan's Phase 3 hook):
        # new high-match (75+) listings raise alerts. Isolated try/except.
        try:
            from agent.alerts.alert_engine import evaluate_listings_for_alerts
            fresh_alerts = evaluate_listings_for_alerts(
                result.get("all_jobs") or [],
                alerts_path=str(DATA_DIR / "alerts.json"),
            )
            if fresh_alerts:
                _broadcast_event("alerts_new", {"count": len(fresh_alerts)})
                logging.info(f"discover alerts: +{len(fresh_alerts)}")
        except Exception as _alert_err:
            logging.warning(f"discover alert generation skipped: {_alert_err}")

        # 404-link fix: annotate the response's top_jobs with their REAL feed
        # ids (or the external apply url when a job is not in the feed), so
        # every "Details ->" link resolves. Additive: original fields unchanged.
        for tj in result.get("top_jobs", []):
            url = str(tj.get("url") or "")
            if url and url in id_by_url:
                tj["id"] = id_by_url[url]
                tj["in_feed"] = True
            else:
                tj["in_feed"] = False
                tj["external_url"] = url

        _broadcast_event("discovery_complete", {
            "total": result["remoteok_count"] + result["linkedin_count"],
            "top_n": len(result["top_jobs"]),
        })

        return jsonify({
            "remoteok_count": result["remoteok_count"],
            "linkedin_count": result["linkedin_count"],
            "top_jobs": result["top_jobs"],
            "saved_to": result["saved_to"],
            "notifications": result["notifications"],
            # additive response keys:
            "persisted": persisted,
            "total_in_feed": persisted["total_in_feed"],
        })
    except Exception as e:
        logging.exception("discover error")
        return jsonify({"error": str(e)}), 500


@app.route('/approve', methods=['POST'])
def approve():
    data = request.json or {}
    url = data.get('url', '')
    title = data.get('title', '')
    company = data.get('company', '')
    mode = data.get('mode', 'draft')
    cv_path = data.get('cv_path', '')

    if not url:
        return jsonify({"error": "Missing url"}), 400

    try:
        orch = get_orchestrator()

        if orch.ledger.already_applied(url, company, title):
            return jsonify({"status": "duplicate_blocked", "message": "Already applied to this role"})

        # Async-apply fix: the apply workflow (LLM eval + CV + browser) takes
        # minutes, but Render's edge proxy kills HTTP requests at ~30s (502)
        # — every synchronous /approve from the bulk-apply queue died with
        # 'Failed to fetch' while the backend kept working. /approve now
        # returns a job id immediately; the workflow runs in a background
        # thread; GET /apply-status/<job_id> reports progress. The response
        # shape stays backward compatible (async=true + job_id added).
        apply_job_id = f"apply_{int(time.time() * 1000)}"
        _apply_jobs[apply_job_id] = {
            "status": "queued", "url": url, "title": title,
            "company": company, "created_at": datetime_now_iso(),
        }

        def _run_apply_workflow_async():
            job_state = _apply_jobs[apply_job_id]
            try:
                job_state["status"] = "running"
                # fresh dedicated thread state for Playwright (sync-in-asyncio fix)
                import concurrent.futures
                def _run():
                    return orch.start_from_url(
                        apply_url=url,
                        mode=mode,
                        cv_path=cv_path or 'CVs/My CVc.md',
                        title=title,
                        company=company,
                    )
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
                    future = _ex.submit(_run)
                    result = future.result(timeout=540)
                job_state["status"] = "done"
                job_state["result"] = result
            except Exception as e:
                job_state["status"] = "failed"
                job_state["error"] = str(e)
                logging.exception(f"[apply-job {apply_job_id}] failed")

        threading.Thread(target=_run_apply_workflow_async, daemon=True).start()

        _broadcast_event("application_approved", {"url": url, "async": True, "job_id": apply_job_id})
        return jsonify({
            "async": True,
            "apply_job_id": apply_job_id,
            "status": "queued",
            "message": "Application workflow started; poll /apply-status/<id>",
        })

        if result.get("status") in ("submitted", "draft_saved"):
            from agent.tracker.followup_tracker import FollowUpTracker
            tracker = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
            candidate_name = orch.candidate_profile.get("personal_details", {}).get("name", "")
            tracker.track(
                job_id=result.get("job_id", ""),
                company=company,
                title=title,
                archetype=result.get("archetype", ""),
            )

        _broadcast_event("application_approved", {"url": url, "status": result.get("status")})
        return jsonify(result)
    except Exception as e:
        logging.exception("approve error")
        return jsonify({"error": str(e)}), 500


@app.route('/applications', methods=['GET'])
def list_applications():
    try:
        orch = get_orchestrator()
        return jsonify({"applications": orch.ledger.all(), "stats": orch.ledger.stats()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===========================================================================
# JobRight-parity additions (Phases 1-5) — NEW ROUTES ONLY.
# Everything above is untouched; the routes below are purely additive and
# only read existing data sources / reuse existing services.
# ===========================================================================

# ---------- Phase 1: match explanation + insights ----------

@app.route('/jobs/<job_id>/match-explanation', methods=['GET'])
def job_match_explanation(job_id):
    """JobRight-style 'why this score' breakdown for one job."""
    try:
        from agent.ranking.match_explainer import explain_match
        orch = get_orchestrator()
        job = next((j for j in orch.jobs_raw if j.get("id") == job_id), None)
        if not job:
            return jsonify({"error": f"Job {job_id} not found"}), 404
        explanation = explain_match(orch.candidate_profile, job)
        return jsonify(explanation)
    except Exception as e:
        logging.exception("match-explanation error")
        return jsonify({"error": str(e)}), 500


@app.route('/insights', methods=['GET'])
def insights():
    """Profile-vs-market alignment view (skills demand, seniority mix, funnel)."""
    try:
        from agent.analytics.insights_builder import build_insights
        orch = get_orchestrator()
        return jsonify(build_insights(
            orch.candidate_profile,
            orch.jobs_raw,
            applications=orch.ledger.all(),
        ))
    except Exception as e:
        logging.exception("insights error")
        return jsonify({"error": str(e)}), 500


# ---------- Phase 2: AI career copilot ----------

@app.route('/copilot/chat', methods=['POST'])
def copilot_chat():
    data = request.json or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"error": "Provide message"}), 400
    conversation_id = data.get('conversation_id', 'default')
    try:
        from agent.copilot.career_copilot import get_copilot
        orch = get_orchestrator()

        followups_due = 0
        try:
            from agent.tracker.followup_tracker import FollowUpTracker
            ft = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
            followups_due = len(ft.get_due())
        except Exception:
            pass

        pipeline_stats = {}
        try:
            from agent.pipeline.pipeline_manager import PipelineManager
            pm = PipelineManager(pipeline_path=str(DATA_DIR / "pipeline.json"))
            pipeline_stats = pm.stats()
        except Exception:
            pass

        copilot = get_copilot(orch.llm_client, history_dir=str(DATA_DIR / "copilot_history"))
        result = copilot.chat(
            message=message,
            conversation_id=conversation_id,
            candidate_profile=orch.candidate_profile,
            jobs=orch.jobs_raw,
            applications=orch.ledger.all(),
            pipeline_stats=pipeline_stats,
            followups_due=followups_due,
        )
        return jsonify(result)
    except Exception as e:
        logging.exception("copilot chat error")
        return jsonify({"error": str(e)}), 500


@app.route('/copilot/history', methods=['GET'])
def copilot_history():
    conversation_id = request.args.get('conversation_id', 'default')
    try:
        from agent.copilot.career_copilot import get_copilot
        orch = get_orchestrator()
        copilot = get_copilot(orch.llm_client, history_dir=str(DATA_DIR / "copilot_history"))
        return jsonify({
            "conversation_id": conversation_id,
            "messages": copilot.load_history(conversation_id),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Phase 3: alerts ----------

@app.route('/alerts', methods=['GET'])
def list_alerts():
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 50))
    try:
        from agent.alerts.alert_engine import AlertEngine
        engine = AlertEngine(alerts_path=str(DATA_DIR / "alerts.json"))
        return jsonify({
            "alerts": engine.list_alerts(unread_only=unread_only, limit=limit),
            "unread_count": engine.unread_count(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/alerts/<alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    try:
        from agent.alerts.alert_engine import AlertEngine
        engine = AlertEngine(alerts_path=str(DATA_DIR / "alerts.json"))
        return jsonify({"marked": engine.mark_read(alert_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/alerts/read-all', methods=['POST'])
def mark_all_alerts_read():
    try:
        from agent.alerts.alert_engine import AlertEngine
        engine = AlertEngine(alerts_path=str(DATA_DIR / "alerts.json"))
        return jsonify({"marked": engine.mark_all_read()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Phase 4: resume import ----------

@app.route('/profile/import', methods=['POST'])
def profile_import():
    """Upload a CV file; returns a merge proposal without touching the profile."""
    try:
        from agent.services.resume_parser import parse_resume_file, ResumeParseError
        f = request.files.get('file')
        if not f:
            return jsonify({"error": "Provide a 'file' upload (md, txt, pdf, docx)"}), 400
        filename = f.filename or "uploaded_cv"
        temp_path = DATA_DIR / f"upload_{datetime_infix()}_{Path(filename).name}"
        f.save(str(temp_path))
        try:
            orch = get_orchestrator()
            proposal = parse_resume_file(
                llm_client=orch.llm_client,
                file_path=str(temp_path),
                filename=filename,
                profile_path=str(CANDIDATE_PROFILE),
            )
        finally:
            temp_path.unlink(missing_ok=True)
        # the parsed payload travels separately from the persisted proposal
        response = {k: v for k, v in proposal.items() if k != "parsed"}
        _parsed_cache['latest'] = proposal.get("parsed", {})
        return jsonify(response)
    except ResumeParseError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.exception("profile import error")
        return jsonify({"error": str(e)}), 500


@app.route('/profile/import/confirm', methods=['POST'])
def profile_import_confirm():
    """Apply selected (or all) proposed changes from the last parse."""
    data = request.json or {}
    change_keys = data.get('change_keys')  # None => apply all proposed
    try:
        from agent.services.resume_parser import ResumeParser, ResumeParseError
        parsed = _parsed_cache.get('latest')
        if not parsed:
            return jsonify({"error": "No pending import — upload a CV via /profile/import first"}), 404
        orch = get_orchestrator()
        parser = ResumeParser(llm_client=orch.llm_client, profile_path=str(CANDIDATE_PROFILE))
        result = parser.apply_merge(parsed, change_keys=change_keys)
        _parsed_cache['latest'] = None
        return jsonify(result)
    except ResumeParseError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.exception("profile import confirm error")
        return jsonify({"error": str(e)}), 500


# ---------- Phase 5: interviews + insider discovery ----------

@app.route('/interviews', methods=['GET'])
def list_interviews():
    upcoming_only = request.args.get('upcoming_only', 'false').lower() == 'true'
    try:
        from agent.tracker.followup_tracker import FollowUpTracker
        ft = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
        return jsonify({"interviews": ft.get_interviews(upcoming_only=upcoming_only)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/interviews', methods=['POST'])
def add_interview():
    data = request.json or {}
    if not data.get('job_id') or not data.get('scheduled_at'):
        return jsonify({"error": "Provide job_id and scheduled_at (ISO)"}), 400
    try:
        from agent.tracker.followup_tracker import FollowUpTracker
        orch = get_orchestrator()
        ft = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
        record = ft.add_interview(
            job_id=data.get('job_id'),
            company=data.get('company', ''),
            title=data.get('title', ''),
            scheduled_at=data.get('scheduled_at'),
            interview_type=data.get('interview_type', 'screening'),
            contact_name=data.get('contact_name', ''),
            notes=data.get('notes', ''),
            candidate_name=orch.candidate_profile.get("personal_details", {}).get("name", ""),
        )
        _broadcast_event("interview_scheduled", {"company": record.get("company"), "when": record.get("scheduled_at")})
        return jsonify(record)
    except Exception as e:
        logging.exception("add interview error")
        return jsonify({"error": str(e)}), 500


@app.route('/interviews/<interview_id>/status', methods=['POST'])
def update_interview_status(interview_id):
    data = request.json or {}
    status = data.get('status', '')
    if status not in ('scheduled', 'completed', 'cancelled'):
        return jsonify({"error": "status must be scheduled|completed|cancelled"}), 400
    try:
        from agent.tracker.followup_tracker import FollowUpTracker
        ft = FollowUpTracker(storage_path=str(DATA_DIR / "followups.json"))
        return jsonify({"updated": ft.update_interview_status(interview_id, status)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/insiders', methods=['GET'])
def insiders():
    """Insider discovery for a company (contacts + alumni/hiring-manager links)."""
    company = request.args.get('company', '')
    domain = request.args.get('domain', '')
    if not company and not domain:
        return jsonify({"error": "Provide company or domain"}), 400
    try:
        from agent.outreach.contact_lookup import ContactLookup
        orch = get_orchestrator()
        lookup = ContactLookup()
        education = orch.candidate_profile.get("education", []) or []
        result = lookup.find_insiders(domain or company, candidate_education=education)
        return jsonify(result)
    except Exception as e:
        logging.exception("insiders error")
        return jsonify({"error": str(e)}), 500


# ---------- ai-job-search framework bridge (additive integration) ----------

@app.route('/framework/evaluate', methods=['POST'])
def framework_evaluate():
    """Full ai-job-search framework evaluation for one job: integrity gate ->
    eligibility gate -> language gate -> 5-dimension weighted score + verdict.

    Accepts job_id (fetches from feed) or raw job_text. The LLM dimension
    scores reuse the existing FieldMapper evaluation; gates and weighting run
    locally (deterministic)."""
    data = request.json or {}
    job_text = data.get('job_text', '')
    job_id = data.get('job_id', '')
    try:
        from agent.ranking.framework_bridge import full_framework_evaluation
        orch = get_orchestrator()

        if job_id and not job_text:
            job = next((j for j in orch.jobs_raw if str(j.get("id")) == str(job_id)), None)
            if not job:
                return jsonify({"error": f"Job {job_id} not found"}), 404
            job_text = job.get("description") or job.get("descriptionText") or ""
            if not job_text:
                return jsonify({"error": "Job has no description to evaluate"}), 400

        if not job_text:
            return jsonify({"error": "Provide job_id or job_text"}), 400

        # dimension scores via the existing evaluator (archetype/global flow),
        # mapped onto the framework's 4 numeric dimensions
        from agent.llm.field_mapper import FieldMapper
        mapper = FieldMapper(
            candidate_profile=orch.candidate_profile,
            job_description=job_text,
        )
        evaluation = mapper.evaluate_job()
        summary = mapper.get_evaluation_summary()
        scores = summary.get("scores", {})

        def _norm(block_score: Any) -> float:
            """Block scores are 0-5; framework dimensions are 0-100."""
            try:
                v = float(block_score)
                return v * 20.0 if v <= 5.0 else min(v, 100.0)
            except (TypeError, ValueError):
                return 50.0

        loc_text = f"{job_text[:500].lower()}"
        location_pass = not any(w in loc_text for w in ("relocation required", "on-site only", "must relocate"))

        llm_dims = {
            "technical_skills": _norm(scores.get("technical", scores.get("skills", 3))),
            "experience_match": _norm(scores.get("experience", 3)),
            "behavioral_culture": _norm(scores.get("culture", scores.get("behavioral", 3))),
            "career_alignment": _norm(scores.get("motivation", scores.get("career", 3))),
            "location_pass": location_pass,
            "location_notes": "assessed from posting text (remote/unknown = pass)",
        }

        result = full_framework_evaluation(job_text, orch.candidate_profile, llm_dims)
        result["job_id"] = job_id or None
        result["archetype"] = summary.get("archetype")
        result["legacy_global_score"] = summary.get("global_score")
        return jsonify(result)
    except Exception as e:
        logging.exception("framework evaluate error")
        return jsonify({"error": str(e)}), 500


@app.route('/framework/track', methods=['POST'])
def framework_track():
    """Record an application in the framework's tracker CSV (dedup by
    company+role). Mirrors the ai-job-search job_search_tracker.csv format."""
    data = request.json or {}
    company = (data.get('company') or '').strip()
    role = (data.get('role') or '').strip()
    if not company or not role:
        return jsonify({"error": "Provide company and role"}), 400
    try:
        from agent.tracker.framework_tracker import TrackerCSV
        tracker = TrackerCSV(csv_path=str(DATA_DIR / "job_search_tracker.csv"))
        result = tracker.add(
            company=company, role=role,
            status=data.get('status', 'drafted'),
            channel=data.get('channel', 'email'),
            contact_person=data.get('contact_person', ''),
            fit_rating=data.get('fit_rating', ''),
            notes=data.get('notes', ''),
            cv_file=data.get('cv_file', ''),
            cover_letter_file=data.get('cover_letter_file', ''),
            source=data.get('source', ''),
            deadline=data.get('deadline', ''),
        )
        return jsonify({"result": result, "stats": tracker.stats()})
    except Exception as e:
        logging.exception("framework track error")
        return jsonify({"error": str(e)}), 500


@app.route('/framework/outcomes', methods=['GET'])
def framework_outcomes():
    """/outcome view: open applications, follow-up-needing rows, stats."""
    try:
        from agent.tracker.framework_tracker import TrackerCSV
        tracker = TrackerCSV(csv_path=str(DATA_DIR / "job_search_tracker.csv"))
        return jsonify({
            "open": tracker.open_applications(),
            "needs_followup": tracker.needs_followup(),
            "stats": tracker.stats(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/framework/outcomes/update', methods=['POST'])
def framework_outcome_update():
    """/outcome update: set a row's status (interview, offer, rejected...)."""
    data = request.json or {}
    company = (data.get('company') or '').strip()
    role = (data.get('role') or '').strip()
    status = (data.get('status') or '').strip()
    if not company or not role or not status:
        return jsonify({"error": "Provide company, role, status"}), 400
    try:
        from agent.tracker.framework_tracker import TrackerCSV
        tracker = TrackerCSV(csv_path=str(DATA_DIR / "job_search_tracker.csv"))
        changed = tracker.update_status(company, role, status, note=data.get('note', ''))
        return jsonify({"updated": changed, "stats": tracker.stats()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/apply-status/<apply_job_id>', methods=['GET'])
def apply_status(apply_job_id):
    """Poll an async apply job started by /approve (bulk-apply fix)."""
    job_state = _apply_jobs.get(apply_job_id)
    if not job_state:
        return jsonify({"error": "Unknown apply_job_id (worker restarted or expired)"}), 404
    payload = {
        "apply_job_id": apply_job_id,
        "status": job_state["status"],
        "url": job_state.get("url"),
        "title": job_state.get("title"),
        "company": job_state.get("company"),
    }
    if job_state["status"] == "done":
        result = job_state.get("result", {})
        payload["result"] = {
            k: result.get(k) for k in
            ("status", "session_id", "job_id", "archetype", "evaluation_summary")
            if result.get(k) is not None
        }
        # keep the compat shape the old synchronous callers expected
        payload.update({k: result.get(k) for k in ("status", "session_id") if result.get(k) is not None})
    elif job_state["status"] == "failed":
        payload["error"] = job_state.get("error")
    return jsonify(payload)


if __name__ == '__main__':
    port = int(os.environ.get("PORT") or 5000)
    app.run(host='0.0.0.0', port=port)
