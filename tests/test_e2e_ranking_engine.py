from __future__ import annotations

import json
import sys
import os
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.ranking.taxonomy import (
    resolve_canonical,
    get_category,
    skills_are_adjacent,
    TECH_TAXONOMY,
    WRONG_FIELD_TERMS,
    RED_FLAGS,
    SENIORITY_HARD_CAPS,
)
from agent.ranking.quality_gate import QualityGate
from agent.ranking.feedback_ranker import FeedbackRanker

STRONG_AI_JD = """
Senior AI Engineer – Remote (Worldwide)

We are building an agentic automation platform powered by LLMs. You will design,
implement, and ship production-grade RAG pipelines, multi-agent orchestration, and
vector database integrations.

Requirements:
- 5+ years of experience with Python, FastAPI, and cloud infrastructure (AWS/GCP)
- Deep expertise in LangChain, LLMs (OpenAI API / Anthropic API), and vector databases
  (Pinecone, Weaviate, Qdrant)
- Experience with HuggingFace Transformers, PyTorch or TensorFlow
- Proficiency with Docker, Kubernetes, and CI/CD pipelines (GitHub Actions)
- Strong grasp of MLOps practices (MLflow, Weights & Biases)

Nice to have: experience with Kafka, Elasticsearch, and real-time inference serving.

Compensation: $130,000 – $180,000 / year. Remote-first. Immediate start preferred.
"""

WRONG_FIELD_JD = """
Senior Plumber needed for commercial projects in Chicago.
Must have 7+ years of experience with pipe fitting, soldering, and HVAC systems.
No coding required. Salary up to $85,000/year.
"""

THIN_JD = """
We're hiring. Join our team. Apply now.
"""

RED_FLAG_JD = """
Unlimited earning potential! Be your own boss. No experience needed.
Passive income opportunity. Make money fast from home!
"""


def test_taxonomy_resolution():
    assert resolve_canonical("pytorch") == "pytorch"
    assert resolve_canonical("torch") == "pytorch"
    assert resolve_canonical("sklearn") == "scikit_learn"
    assert resolve_canonical("k8s") == "kubernetes"
    assert resolve_canonical("ts") == "typescript"
    assert resolve_canonical("nonexistent_xyz_skill") is None
    print("  taxonomy resolution: PASS")


def test_taxonomy_categories():
    assert get_category("python") == "language"
    assert get_category("react") == "frontend"
    assert get_category("fastapi") == "backend"
    assert get_category("pytorch") == "ai"
    assert get_category("docker") == "infra"
    print("  taxonomy categories: PASS")


def test_adjacency():
    assert skills_are_adjacent("pytorch", "tensorflow") is True
    assert skills_are_adjacent("pytorch", "langchain") is True
    assert skills_are_adjacent("python", "javascript") is False
    assert skills_are_adjacent("react", "vue") is False
    assert skills_are_adjacent("docker", "kubernetes") is True
    print("  skill adjacency: PASS")


def test_quality_gate_strong_jd():
    gate = QualityGate()
    listing = {
        "url": "https://jobs.example.com/ai-engineer",
        "title": "Senior AI Engineer",
        "company": "AcmeCorp",
        "description": STRONG_AI_JD,
        "location": "Remote",
        "date_posted": "2026-05-20",
    }
    result = gate.evaluate(listing)
    assert result["passes"] is True, f"Expected PASS but got: {result}"
    assert result["total_penalty"] < 50
    print(f"  quality gate (strong JD): PASS  penalty={result['total_penalty']}  score={result['final_score']:.2f}")


def test_quality_gate_thin_jd():
    gate = QualityGate()
    listing = {
        "url": "https://jobs.example.com/mystery",
        "title": "Engineer",
        "company": "",
        "description": THIN_JD,
        "location": "",
        "date_posted": "2024-01-01",
    }
    result = gate.evaluate(listing)
    assert result["passes"] is False, f"Stale+thin+missing_company JD should FAIL but got: {result}"
    penalty_reasons = [p["reason"] for p in result["penalties"]]
    assert any("thin" in r for r in penalty_reasons)
    assert any("missing_company" in r for r in penalty_reasons)
    assert any("stale" in r for r in penalty_reasons)
    print(f"  quality gate (thin JD): PASS  penalty={result['total_penalty']}")


def test_quality_gate_red_flags():
    gate = QualityGate()
    listing = {
        "url": "https://scam-jobs.example.com/rich",
        "title": "Wealth Advisor",
        "company": "FastCash LLC",
        "description": RED_FLAG_JD,
        "location": "Remote",
        "date_posted": "2026-05-20",
    }
    result = gate.evaluate(listing)
    assert result["passes"] is False, f"Red-flag JD should FAIL but got: {result}"
    print(f"  quality gate (red flags): PASS  penalty={result['total_penalty']}")


def test_feedback_ranker_cycle(tmp_path):
    signals_path = str(tmp_path / "feedback_signals.json")
    ranker = FeedbackRanker(data_path=signals_path)

    ai_listing = {
        "url": "https://wellfound.com/jobs/ai-engineer",
        "title": "Senior AI Engineer",
        "company": "AcmeCorp",
        "description": STRONG_AI_JD,
        "location": "Remote",
        "source": "wellfound",
    }

    assert ranker.score_listing(ai_listing) == 0.0, "No signals → delta must be 0"

    ranker.record_outcome("job_001", ai_listing, "positive")
    ranker.record_outcome("job_002", ai_listing, "positive")
    ranker.record_outcome("job_003", ai_listing, "negative")

    delta = ranker.score_listing(ai_listing)
    assert delta > 0, f"More positive than negative signals – delta should be positive, got {delta}"

    summary = ranker.get_signal_summary()
    assert summary["total_signals"] == 3
    assert summary["positive"] == 2
    assert summary["negative"] == 1
    print(f"  feedback ranker: PASS  delta={delta:.3f}  signals={summary}")


def test_stack_extraction_from_jd():
    from agent.mcp_server import _extract_stack, _extract_seniority_years, _extract_location_type, _extract_salary, _extract_urgency

    stack = _extract_stack(STRONG_AI_JD)
    assert "python" in stack, f"python not in stack: {stack}"
    assert "fastapi" in stack, f"fastapi not in stack: {stack}"
    assert "docker" in stack, f"docker not in stack: {stack}"
    assert "kubernetes" in stack, f"kubernetes not in stack: {stack}"
    assert "langchain" in stack, f"langchain not in stack: {stack}"
    assert "pytorch" in stack or "tensorflow" in stack, f"pytorch/tensorflow not in stack: {stack}"

    years = _extract_seniority_years(STRONG_AI_JD)
    assert years == 5, f"Expected 5 years, got {years}"

    loc = _extract_location_type(STRONG_AI_JD)
    assert loc in ("remote_ok", "fully_remote"), f"Expected remote, got {loc}"

    salary = _extract_salary(STRONG_AI_JD)
    assert salary is not None, "Salary should be extracted"

    urgency = _extract_urgency(STRONG_AI_JD)
    assert urgency == "high", f"Expected high urgency, got {urgency}"

    print(f"  extract_lead_intel: PASS  stack={stack[:5]}...  years={years}  loc={loc}  salary={salary}  urgency={urgency}")


def test_mcp_tools_via_protocol():
    from agent.mcp_server import _handle_request

    init_resp = _handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init_resp["result"]["serverInfo"]["name"] == "job-search-mcp"

    list_resp = _handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert "score_job_fit" in tool_names
    assert "evaluate_lead_quality" in tool_names
    assert "extract_lead_intel" in tool_names

    fit_resp = _handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "score_job_fit",
            "arguments": {
                "job_description": STRONG_AI_JD,
                "candidate_skills": ["python", "torch", "k8s", "langchain", "fastapi"]
            }
        }
    })
    assert fit_resp["result"]["isError"] is False
    fit_data = json.loads(fit_resp["result"]["content"][0]["text"])
    assert fit_data["match_ratio"] > 0, "Expected some skill matches"
    assert len(fit_data["matched_skills"]) > 0

    intel_resp = _handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "extract_lead_intel",
            "arguments": {"job_description": STRONG_AI_JD}
        }
    })
    assert intel_resp["result"]["isError"] is False
    intel_data = json.loads(intel_resp["result"]["content"][0]["text"])
    assert intel_data["seniority_years"] == 5
    assert intel_data["urgency"] == "high"

    lead_resp = _handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "evaluate_lead_quality",
            "arguments": {
                "listing": {
                    "url": "https://jobs.example.com/ai-engineer",
                    "title": "Senior AI Engineer",
                    "company": "AcmeCorp",
                    "description": STRONG_AI_JD,
                    "location": "Remote",
                    "date_posted": "2026-05-20",
                }
            }
        }
    })
    assert lead_resp["result"]["isError"] is False
    lead_data = json.loads(lead_resp["result"]["content"][0]["text"])
    assert lead_data["verdict"] == "PASS", f"Strong JD should pass: {lead_data}"

    print(f"  MCP protocol tools: PASS  match_ratio={fit_data['match_ratio']}  verdict={lead_data['verdict']}")


def run_all(tmp_path=None):
    import tempfile
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    from pathlib import Path
    tmp_path = Path(tmp_path)

    print("\n=== E2E Ranking Engine Tests ===")
    test_taxonomy_resolution()
    test_taxonomy_categories()
    test_adjacency()
    test_quality_gate_strong_jd()
    test_quality_gate_thin_jd()
    test_quality_gate_red_flags()
    test_feedback_ranker_cycle(tmp_path)
    test_stack_extraction_from_jd()
    test_mcp_tools_via_protocol()
    print("=== ALL TESTS PASSED ===\n")


if __name__ == "__main__":
    run_all()
