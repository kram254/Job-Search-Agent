# CI/CD Documentation

## Overview

This project uses **GitHub Actions** for CI and **Render** for hosting/deployment.

---

## Workflows

### `ci.yml` — Continuous Integration

Triggers on every push and pull request to `main`.

| Job | Blocking? | What it checks |
|-----|-----------|----------------|
| Lint | Advisory (non-blocking) | `ruff check .` code style |
| Tests | Advisory (non-blocking) | `pytest tests/` |
| Build Check | **Blocking** | `import agent.app` succeeds |
| Validate render.yaml | **Blocking** | `render.yaml` exists and is valid YAML |

### `deploy.yml` — Continuous Deployment

Triggers on every push to `main`.

1. Fires the Render deploy hook (`RENDER_DEPLOY_HOOK_URL` secret)
2. Waits 90 seconds for Render to spin up the new instance
3. Polls `GET /health` up to 10 times (30s apart) — fails the job if service doesn't return HTTP 200

---

## Required Secrets

Add these in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Required | Where to get it |
|--------|----------|-----------------|
| `RENDER_DEPLOY_HOOK_URL` | ✅ Yes | Render dashboard → Service → Settings → Deploy Hook |
| `RENDER_API_KEY` | Optional | Render dashboard → Account → API Keys |
| `RENDER_SERVICE_ID` | Optional | Render dashboard → Service → Settings (shown in URL) |
| `CODECOV_TOKEN` | Optional | codecov.io after connecting the repo |

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Lint
ruff check .

# Verify import
python3 -c "import agent.app; print('OK')"

# Start server locally
gunicorn agent.app:app --bind 0.0.0.0:5000
```

---

## Render Services

Defined in `render.yaml`:

| Service | Type | Description |
|---------|------|-------------|
| `job-search-backend` | Web service | Flask + Playwright API |
| `job-search-frontend` | Static site | Next.js frontend |
