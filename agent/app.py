from flask import Flask, request, jsonify, Response, stream_with_context
from pathlib import Path
import os
import json
import logging
import queue
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


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})


@app.route('/apply', methods=['POST'])
def apply():
    data = request.json
    job_id = data.get('job_id')
    apply_url = data.get('apply_url')

    if not job_id or not apply_url:
        return jsonify({"error": "Missing job_id or apply_url"}), 400

    try:
        orch = get_orchestrator()
        orch.start_application(job_id, apply_url)
        return jsonify({"status": "application_started", "job_id": job_id})
    except Exception as e:
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
    contact_name = data.get('contact_name', 'Hiring Manager')
    platform = data.get('platform', 'linkedin')
    archetype = data.get('archetype', 'AI Engineering')

    try:
        orch = get_orchestrator()
        name = orch.candidate_profile.get("personal_details", {}).get("name", "")

        if platform == "linkedin":
            message = (
                f"Hi {contact_name},\n\n"
                f"I came across the {data.get('title', 'role')} at {company} and it immediately caught my attention. "
                f"I've been building in {archetype} and the problems your team is solving align directly with "
                f"where I've been focusing my work.\n\n"
                f"I'd love to connect briefly to learn more about the team. Would you be open to a quick chat?\n\n"
                f"Best,\n{name}"
            )
        else:
            message = (
                f"Hi {contact_name},\n\n"
                f"I'm reaching out regarding the {data.get('title', 'position')} at {company}. "
                f"My background in {archetype} maps closely to what you're building.\n\n"
                f"Happy to share more. Let me know if a brief call makes sense.\n\n"
                f"Best,\n{name}"
            )

        return jsonify({
            "platform": platform,
            "contact": contact_name,
            "company": company,
            "message": message,
            "character_count": len(message)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
