from __future__ import annotations

import json
import os

import pytest


@pytest.fixture()
def client():
    os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-key-for-tests")

    from agent.app import app as flask_app

    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client


def test_health_endpoint_returns_healthy(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload == {"status": "healthy"}


def test_apply_endpoint_validates_payload(client):
    response = client.post(
        "/apply",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    payload = json.loads(response.data)
    assert "error" in payload


def test_gate_response_requires_gate_id(client):
    response = client.post(
        "/gate-response/session-123",
        data=json.dumps({"response": {"ok": True}}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_app_imports_cleanly():
    from agent.app import app

    assert app.name == "agent.app"
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/health" in rules
    assert "/apply" in rules
