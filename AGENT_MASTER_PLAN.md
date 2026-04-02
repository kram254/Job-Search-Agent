# Automated Job Application Agent — Master Plan

## Executive Summary

Locally-deployed, Python-based AI agent that ingests job listings from `jobs_raw.json` (or a fresh URL), uses **Playwright** for browser automation, **Claude API** as the reasoning/mapping layer, and a **lightweight local Flask web UI** for Human-in-the-Loop (HITL) gates. The agent never submits an application, enters credentials, or completes sensitive fields without explicit human approval.

---

## 1. System Architecture

### 1.1 High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR LAYER                        │
│  agent/orchestrator.py  — main state machine, task dispatcher   │
└────────────┬────────────────────────────────────────────────────┘
             │
    ┌────────┴──────────┬──────────────┬──────────────┐
    │                   │              │               │
┌───▼───┐         ┌─────▼────┐  ┌─────▼────┐   ┌─────▼────┐
│BROWSER│         │  LLM     │  │  HITL    │   │ TRACKER  │
│MODULE │         │  MODULE  │  │  GATE    │   │  MODULE  │
│       │         │          │  │  MODULE  │   │          │
│Playwright        │Claude API│  │ Flask UI │   │SQLite DB │
│session │         │field map │  │+ CLI     │   │+ JSON log│
└───────┘         └──────────┘  └──────────┘   └──────────┘
    │
┌───▼──────────┐
│ PLATFORM     │
│ HANDLERS     │
│ (per-ATS)    │
└──────────────┘
```

### 1.2 Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Browser automation | Playwright (Python, async) | Superior async support; iframe handling; network interception; stealth-friendly |
| LLM reasoning | Anthropic API (claude-sonnet-4-6) | Native tool use; structured JSON output; strong HTML reading |
| HITL UI | Flask + htmx (local, port 5555) | Zero-dependency local web UI; real-time updates via SSE; no build step |
| State persistence | SQLite + JSON files | File-based; survives process restarts |
| Credential storage | Python `keyring` | OS-native secrets vault; never stored in plaintext |
| Deployment | Local Windows machine | Matches existing setup |

### 1.3 State Management

Each session = UUID. State checkpointed to `data/sessions/{uuid}/state.json` after every significant action. Supports full resume after crash or HITL pause.

---

## 2. Agent Capabilities

### 2.1 Input Modes
1. Raw URL string (e.g. `https://grnh.se/10titkdq1us`)
2. Job ID from `jobs_raw.json` (agent looks up `applyUrl`)
3. Batch run over all unprocessed entries in `jobs_raw.json`

### 2.2 Platform Fingerprinting

```
Priority order:
1. URL hostname match → greenhouse, linkedin, workday, lever, icims, taleo, bamboohr, mercor
2. Page title / meta tag analysis
3. DOM structure heuristics (known class names / data attributes)
4. LLM full-page snapshot analysis (fallback)
```

### 2.3 Form Field Detection

Full DOM inventory on each page load:
- `<input>` elements: type, name, id, placeholder, aria-label, required, label text
- `<select>` elements: all options
- `<textarea>` elements with label context
- Checkbox and radio groups
- `<input type="file">` upload targets
- Custom components: detected by ARIA roles and known class patterns
- iFrame-embedded fields (Playwright handles natively)

### 2.4 Smart Field Mapping (LLM)

Claude receives: field inventory + candidate profile + job description → returns mapping JSON:

```json
{
  "mappings": [
    {
      "field_id": "applicant_first_name",
      "candidate_value": "Emmanuel",
      "confidence": 0.99,
      "action": "fill",
      "requires_hitl": false
    },
    {
      "field_id": "desired_salary",
      "candidate_value": null,
      "confidence": 0.0,
      "action": "skip",
      "requires_hitl": true,
      "hitl_reason": "salary_negotiation",
      "hitl_category": "hard_gate"
    }
  ]
}
```

### 2.5 Platform Handlers

| Platform | Detection | Key Quirks |
|---|---|---|
| LinkedIn Easy Apply | `linkedin.com/jobs` | Modal multi-step; typeahead; saved resume |
| Greenhouse | `grnh.se` / `boards.greenhouse.io` | Clean HTML; EEOC at end |
| Lever | `jobs.lever.co` | Single-page; custom question blocks |
| Workday | `myworkdayjobs.com` | Heavy JS; custom widgets; bot-resistant |
| Taleo | `taleo.net` | Legacy; iframe-heavy; slow |
| iCIMS | `icims.com` | Account creation required |
| BambooHR | `bamboohr.com` | Simple; clean structure |
| Mercor | `t.mercor.com` | Startup ATS; custom flows |
| **Generic fallback** | all others | LLM-guided; screenshot-based decision loop |

### 2.6 Resume & Cover Letter

**CV Selection Logic:**
- LLM reads job description → selects from 3 CV variants:
  - `SoftwareDevCV.pdf` → AI/ML/LLM roles
  - `My CVc.pdf` → General/concise
  - `Soft Dev CV.pdf` → Standard software engineering
- Selection shown in soft HITL gate before upload

**Cover Letter:**
- LLM generates tailored letter from job description + candidate profile + company info
- Always shown in `GATE_COVER_LETTER_REVIEW` (human can edit inline before agent inserts it)

### 2.7 CAPTCHA Detection (Multi-Signal)

1. DOM: `<div class="g-recaptcha">`, `<iframe src="*hcaptcha*">`, Cloudflare Turnstile
2. Visual: screenshot → Claude Vision checks for CAPTCHA images
3. Network: intercept requests to `recaptcha.net`, `hcaptcha.com`, `challenges.cloudflare.com`

→ On detection: **Hard Gate** fires, browser window brought to foreground, human solves, agent resumes.

### 2.8 Bot Evasion

- Human-like typing: random 30–120ms delays between keystrokes
- Mouse `hover()` before `click()`
- Random 2–8s delays between sections
- Persistent browser profile (real cookies/history)
- Realistic viewport (1280×800)
- Headed mode for bot-resistant platforms (Workday)
- Playwright stealth config (webdriver flags disabled)

---

## 3. Human-in-the-Loop (HITL) Gate Design

### 3.1 Hard Gates — Always require human, cannot be bypassed

| Gate ID | Trigger | Required Action |
|---|---|---|
| `GATE_FINAL_SUBMIT` | About to click Submit | Human reviews full screenshot, explicitly clicks "Submit" in HITL UI with confirmation modal |
| `GATE_CAPTCHA` | Any CAPTCHA detected | Human solves in live browser, clicks "Done" in HITL UI |
| `GATE_LOGIN` | Login / account creation wall | Human authenticates manually, clicks "Resume" |
| `GATE_SALARY_ENTRY` | Any salary/compensation field | Human enters or approves agent suggestion |
| `GATE_PAYMENT` | Any payment / credit card field | Human handles; agent stops entirely |
| `GATE_SSN_EIN` | Social Security / Tax ID / Gov ID | Human fills; agent never touches these |
| `GATE_REFERENCES` | Reference names / contact info requested | Human confirms pre-stored references before release |

### 3.2 Soft Gates — Human by default, can be pre-authorized in config

| Gate ID | Trigger | Pre-auth Available |
|---|---|---|
| `GATE_COVER_LETTER_REVIEW` | Agent generates cover letter | Yes — "auto-approve LLM cover letters" |
| `GATE_ESSAY_QUESTION` | Open-ended text (>100 char expected) | Yes — "use LLM draft without review" (not recommended) |
| `GATE_CV_SELECTION` | Agent picks CV variant | Yes — "always use SoftwareDevCV.pdf" |
| `GATE_CONSENT_CHECKBOX` | Legal / background check consent | Yes — "auto-approve standard consent" |
| `GATE_PORTFOLIO_LINKS` | GitHub / LinkedIn / portfolio fields | Yes — links stored in candidate profile |
| `GATE_WORK_AUTHORIZATION` | Work auth status questions | Yes — set per-country in config |

### 3.3 Configurable Gates

Any field name pattern can be marked for review in `config/hitl_config.json`:
```json
{
  "review_fields": ["cover_letter", "summary", "why_*", "additional_information"]
}
```

### 3.4 HITL Approval UI (Flask, port 5555)

- **Split view**: left = live screenshot of current form | right = approval panel
- Text fields: editable textarea pre-populated with LLM draft
- File uploads: shows which file will be uploaded, with "Change file" option
- Final submission: full-page screenshot + prominent "Submit Application" button behind a confirmation modal
- Notifications: Windows toast + sound alert when any gate fires
- **Paused Sessions queue**: all sessions waiting for action are listed; human can resume any

### 3.5 Timeout Handling

Default timeout: **30 minutes** per gate.

| Gate | On Timeout |
|---|---|
| `GATE_FINAL_SUBMIT` | NOT submitted. Session saved. User notified. |
| `GATE_CAPTCHA` | Session paused. Marked `needs_captcha` in tracker. |
| Soft gates | LLM draft used, warning flag set in tracker. |
| All other hard gates | Session paused, saved, agent shuts down gracefully. |

### 3.6 Pause-and-Wait Mechanism

```
1. Orchestrator calls hitl_gate.pause(gate_id, context)
2. State written to disk (data/sessions/{uuid}/state.json)
3. Notification sent to human
4. Agent polls: data/gates/{gate_id}_{uuid}.response
5. HITL UI writes response file when human approves/edits/rejects
6. Orchestrator reads response, resumes
```
File-based polling = agent and UI are separate processes; agent crash does not lose pending gates.

---

## 4. Candidate Profile Data Store

File: `data/candidate_profile.json`

Key sections:
- `personal`: name, email, phone (multiple formats), location, remote_only flag
- `work_authorization`: per-country status (Kenya=citizen; all others → HITL required)
- `professional_profiles`: LinkedIn, GitHub, Medium
- `cv_variants`: paths to all 3 CV pairs (md + pdf), with `best_for` role tags
- `education`: structured degree/institution/year data
- `skills`: primary and secondary skill lists
- `sensitive_fields`: salary → `__HITL_REQUIRED__`, SSN → `__HITL_REQUIRED__`, references (with `release_approved: false` flag)

**Format Normalizer**: Converts phone/date/degree name to platform-specific format automatically.

**Sentinel values**: Any field set to `"__HITL_REQUIRED__"` in the profile automatically triggers the appropriate hard gate — the LLM field mapper is instructed to never auto-fill sentinels.

---

## 5. Application Tracking

### SQLite Schema (`data/applications.db`)

```
applications: id, job_id, job_title, company, apply_url, final_url,
              platform, cv_id, status, submitted_at, field_values (JSON),
              hitl_events (JSON), screenshot_dir, error_message, notes

hitl_events:  id, application_id, gate_id, triggered_at, resolved_at,
              resolution (approved/rejected/edited/timed_out),
              human_input, agent_proposal
```

### Status Values
`pending` → `in_progress` → `paused` | `submitted` | `failed` | `skipped`

### applications_log.json
Human-readable JSON log with summary stats + per-application detail (compatible with future dashboard).

---

## 6. Error Handling

| Error Class | Recovery Strategy |
|---|---|
| `PageLoadError` | Retry 3x with exponential backoff; fail after 3 |
| `UnexpectedLayoutError` | LLM re-analysis; fallback to generic handler; HITL if stuck |
| `SessionTimeoutError` | Detect login redirect; trigger `GATE_LOGIN`; resume |
| `ValidationError` | LLM analyzes error; self-correct once; HITL on second failure |
| `BotDetectionError` | Pause + log warning; flag for manual completion |
| `RateLimitError` | Exponential backoff with jitter |
| `FileUploadError` | Retry with alternate format (PDF/DOC); HITL if persists |
| `SubmitFailedError` | Screenshot + check for error message; HITL for human verification |

---

## 7. Complete Workflow

```
[INPUT] User provides job URL or selects job_id
    │
    ▼
[1] URL Resolution → follow redirects → check if already applied
    │
    ▼
[2] Platform Fingerprinting → load appropriate handler
    │
    ▼
[3] Login/Account Detection
    ├─ Login required → [HARD GATE: GATE_LOGIN] → human authenticates → resume
    │
    ▼
[4] CV Selection → LLM picks variant → [SOFT GATE: GATE_CV_SELECTION]
    │
    ▼
[5] Form Discovery → enumerate all steps → build field inventory
    │
    ▼
[6] LLM Field Mapping → confidence scores → flag HITL fields
    │
    ▼
[7] Cover Letter Generation (if applicable)
    └─ [SOFT GATE: GATE_COVER_LETTER_REVIEW] → human edits/approves
    │
    ▼
[8] Form Filling Loop (per section)
    ├─ Hard gate field → [HARD GATE] → human fills → continue
    ├─ Soft gate field → [SOFT GATE] unless pre-authorized
    ├─ High confidence (>0.85) → agent fills automatically
    ├─ Low confidence → LLM re-analysis → [CONFIGURABLE GATE] if still low
    ├─ CAPTCHA detected → [HARD GATE: GATE_CAPTCHA] → human solves → resume
    ├─ Validation error → LLM self-corrects once → HITL on 2nd failure
    ├─ Screenshot captured after each section
    ├─ State checkpointed to disk
    └─ Click "Next" / "Continue"
    │
    ▼
[9] Review Gate → HITL UI shows all filled values → human can flag corrections
    │
    ▼
[10] Final Submission → full-page screenshot
    └─ [HARD GATE: GATE_FINAL_SUBMIT] → human reviews + clicks Submit in UI
    │
    ▼
[11] Confirmation → detect success page → screenshot → alert if no confirmation in 30s
    │
    ▼
[12] Logging → write to DB + JSON log → archive screenshots → mark job processed
```

---

## 8. Implementation Phases

### Phase 1 — MVP (2–3 weeks)
**Goal**: Fill one real application, human completes rest.

- `data/candidate_profile.json` (extracted from CVs)
- `agent/browser/playwright_wrapper.py` (launch, navigate, click, type, screenshot)
- `agent/llm/field_mapper.py` (Claude → mapping JSON)
- `agent/hitl/gate.py` (blocking CLI HITL)
- `agent/tracker/logger.py` (JSON log)
- `agent/orchestrator.py` (linear flow)
- `agent/platforms/greenhouse.py` ← **first target: NISC job** (`grnh.se/10titkdq1us`)
- `agent/platforms/generic.py` (fallback)

### Phase 2 — Platform Handlers + Flask HITL UI (3–4 weeks)
- `agent/hitl/flask_ui.py` (port 5555 with screenshot viewer + approval panel)
- `agent/hitl/notification.py` (Windows toast + sound)
- `agent/platforms/linkedin.py` (LinkedIn Easy Apply)
- `agent/platforms/mercor.py` (Taskify AI job)
- State checkpoint/resume logic
- Batch queue processing from `jobs_raw.json`
- Cover letter generation pipeline
- SQLite tracker

### Phase 3 — Full Intelligence Layer (4–6 weeks)
- `agent/platforms/workday.py` (highest complexity)
- `agent/platforms/taleo.py`, `icims.py`
- Multi-signal CAPTCHA detector
- Bot evasion module
- LLM error recovery
- LLM essay writer for open-ended questions
- International format normalizer

### Phase 4 — Advanced Features (ongoing)
- Rich tracking dashboard (application funnel, response rates)
- A/B testing: different cover letter styles + CV variants per job
- Pre-application scoring (should we even apply?)
- Interview scheduling link detection from email
- Anti-duplicate guard
- Session replay timeline
- Docker packaging

---

## 9. Directory Structure

```
E:\Models\Claude code\Leads\Job Search\
├── jobs_raw.json
├── CVs\
│   ├── My CVc.md / .pdf
│   ├── Soft Dev CV.md / .pdf
│   └── SoftwareDevCV.md / .pdf
│
├── agent\
│   ├── orchestrator.py                    ← central state machine
│   ├── browser\
│   │   ├── playwright_wrapper.py
│   │   ├── form_inventory.py
│   │   ├── file_uploader.py
│   │   ├── captcha_detector.py
│   │   └── bot_evasion.py
│   ├── llm\
│   │   ├── client.py
│   │   ├── field_mapper.py
│   │   ├── cover_letter_generator.py
│   │   ├── essay_writer.py
│   │   ├── platform_classifier.py
│   │   └── error_analyzer.py
│   ├── hitl\
│   │   ├── gate.py                        ← safety foundation
│   │   ├── flask_ui.py
│   │   ├── notification.py
│   │   └── gate_definitions.py
│   ├── platforms\
│   │   ├── base.py
│   │   ├── greenhouse.py                  ← build first
│   │   ├── linkedin.py
│   │   ├── lever.py
│   │   ├── workday.py
│   │   ├── taleo.py
│   │   ├── icims.py
│   │   ├── bamboohr.py
│   │   ├── mercor.py
│   │   └── generic.py
│   └── tracker\
│       ├── database.py
│       └── logger.py
│
├── data\
│   ├── candidate_profile.json             ← build first
│   ├── applications.db
│   ├── applications_log.json
│   ├── sessions\{uuid}\
│   │   ├── state.json
│   │   └── screenshots\
│   └── gates\{gate_id}_{uuid}.response
│
├── config\
│   ├── agent_config.json
│   └── hitl_config.json                   ← gate pre-auth settings
│
└── requirements.txt
    # playwright, anthropic, flask, sqlite3, plyer, keyring, httpx, pydantic
```

---

## 10. Key Design Decisions

| Decision | Rationale |
|---|---|
| Playwright over Selenium | Better async, iframe handling, network interception, auto-wait, stealth support |
| Flask UI over CLI | Screenshots inline; safe confirmation modal before submit; far harder to accidentally submit |
| File-based gate signaling | Agent and UI are separate processes; crash-safe; pending gates survive restarts |
| 3 CV variants | Job description → CV matching increases relevance per application |
| Sentinel `__HITL_REQUIRED__` | Prevents LLM from ever auto-filling sensitive fields regardless of confidence score |
| Playwright (headed) for Workday | Workday's bot detection is sophisticated; headless mode is reliably flagged |
| Claude API over Computer Use API | DOM extraction + field mapping is faster than screenshot-per-action loop for structured forms; Computer Use reserved as visual fallback |

---

## Critical First Steps (Build Order)

1. **`data/candidate_profile.json`** — everything depends on this structured data
2. **`config/hitl_config.json`** — define all gate behaviors before writing automation
3. **`agent/hitl/gate.py`** — safety layer must be solid before any form-filling is built
4. **`agent/platforms/greenhouse.py`** — first real target (NISC: `grnh.se/10titkdq1us`) validates the full architecture
5. **`agent/orchestrator.py`** — wire everything together
