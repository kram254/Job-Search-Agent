from flask import Flask, request, jsonify
from pathlib import Path
import os
import json
import logging
from flask_cors import CORS
from agent.orchestrator import ApplicationOrchestrator

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Base paths
BASE_DIR = Path(__file__).parent.parent
CANDIDATE_PROFILE = BASE_DIR / "data" / "candidate_profile.json"
JOBS_RAW = BASE_DIR / "jobs_raw.json"
HITL_CONFIG = BASE_DIR / "config" / "hitl_config.json"

# Initialize Orchestrator
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
        # Note: start_application is currently blocking in the orchestrator
        # For deployment, this should ideally be handled by a task queue (e.g. Celery)
        # But for MVP, we'll keep it simple
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
        
    resp_path = BASE_DIR / "data" / "gates" / f"{gate_id}_{session_id}.response"
    os.makedirs(os.path.dirname(resp_path), exist_ok=True)
    
    with open(resp_path, "w") as f:
        json.dump(response_data, f)
        
    return jsonify({"status": "response_received"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
