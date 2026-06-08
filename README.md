# 🐕 Metric Watchdog

> Reads your dashboard. Reasons through it. Diagnoses via SQL. Delivers a sourced briefing.

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-green?style=flat-square)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-red?style=flat-square)](https://streamlit.io)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-orange?style=flat-square)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue?style=flat-square)](https://docker.com)

---

## What Is This?

Every morning a data analyst opens a dashboard, scans for anomalies, investigates suspicious movements, and writes a briefing. That loop takes 2-3 hours. Metric Watchdog does it in 90 seconds — autonomously, before the team starts their day.

The agent reads a dashboard screenshot using a vision model, reasons through what it sees, writes and executes diagnostic SQL queries against your database, builds sourced evidence objects, and delivers a structured briefing to email and Slack.

**The key design principle:** Every claim in the briefing traces back to a source. Measured facts are tagged `[SQL: table, N rows]`. Co-movement patterns are tagged as inferences with confidence levels. Anything the agent couldn't verify is explicitly listed as `[UNVERIFIED]` with a suggested next step for the analyst.

---

## How It Works

```
8:00am — Scheduler triggers
         ↓
Step 1 — Vision model reads dashboard screenshot
         Extracts every metric, value, direction, and trend visible
         ↓
Step 2 — LLM reasons over what it sees
         Identifies which metrics moved enough to matter
         Identifies co-moving metrics already visible in dashboard
         Lists gaps — what the dashboard can't answer
         ↓
Step 3 — Agent writes and executes targeted SQL
         One query per gap — decomposition, segmentation, trend
         Builds Evidence objects: PROVEN (SQL) / INFERRED (co-movement)
         / HYPOTHESISED (pattern match)
         ↓
Step 4 — Narrator writes sourced briefing
         Three sections per metric:
           ✅ What we know (proven from SQL or dashboard)
           📐 What we inferred (co-movement patterns)
           ⚠️  What we couldn't check (explicit gaps + next steps)
         ↓
Step 5 — Deliver to email + Slack
         HTML briefing saved to disk
         Full audit log with every SQL query logged
```

---

## What Makes This Agent-Native

A chat window cannot do any of this:

| Capability | Chat | Metric Watchdog |
|---|---|---|
| Wakes up at 8am autonomously | ❌ | ✅ APScheduler |
| Reads a live dashboard image | ❌ | ✅ Vision LLM |
| Executes real SQL against your DB | ❌ | ✅ Postgres |
| Runs decomposition + segmentation | ❌ | ✅ Agent loop |
| Remembers yesterday's baseline | ❌ | ✅ SQLite baseline store |
| Posts to Slack itself | ❌ | ✅ Webhook delivery |
| Explicitly flags what it couldn't verify | ❌ | ✅ Evidence architecture |

---

## The Sourced Briefing

This is what lands in the analyst's inbox every morning:

```
🔴 METRIC WATCHDOG — Tuesday 3 June 2026, 08:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUMMARY: Revenue dropped 39.8% in the last 2 days driven by a
34.4% conversion rate collapse. Sessions flat — traffic is not
the issue. Something in the funnel or product mix changed.

🔴 DAILY REVENUE ($)

   ✅ WHAT WE KNOW
   • Revenue: $41,200 yesterday vs $68,400 seven-day avg [dashboard]
   • Electronics category drove 78% of the revenue drop
     [SQL: orders, n=8,432]
   • Mobile conversion: 1.9% vs desktop 3.1% [SQL: sessions, n=9,012]

   📐 WHAT WE INFERRED
   • Conversion rate and revenue moved together same 24h window
     [confidence: HIGH]
   • Session duration dropped 18% on mobile — consistent with
     checkout friction [confidence: MEDIUM]

   ⚠️  WHAT WE COULDN'T CHECK [UNVERIFIED]
   • Whether mobile checkout had a recent code deployment
     → Check deployment logs for mobile checkout, last 48 hours
   • Electronics refund spike root cause
     → Query returns table by product_category and return_reason

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 RECOMMENDED ACTIONS
   [IMMEDIATE — 15min] Check deployment logs for mobile checkout
   [TODAY — 30min] Query returns by category and reason

Run ID: watchdog_20260603_0800 | Full SQL audit: logs/
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      DELIVERY LAYER                             │
│   Streamlit UI  ──────────────────────────────────────────────► │
│   FastAPI REST  ──────────────────────────────────────────────► │
│   APScheduler   ──────────────────────────────────────────────► │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                       AGENT PIPELINE                            │
│                                                                 │
│   reader_agent      vision model → DashboardReading             │
│        ↓                                                        │
│   reasoning_agent   LLM → ReasoningOutput + InvestigationGaps   │
│        ↓                                                        │
│   diagnosis_agent   SQL writer → executor → Evidence objects    │
│        ↓                                                        │
│   narrator_agent    LLM constrained to evidence → Briefing      │
│        ↓                                                        │
│   orchestrator      runs pipeline, handles failures, logs       │
│                                                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      INFRASTRUCTURE                             │
│                                                                 │
│   Postgres          live business data, queried by agent        │
│   SQLite            run history, traces, baselines              │
│   Plain text logs   every SQL query, failure, stage timing      │
│   Groq              LLM reasoning, SQL writing, narration       │
│   Ollama / Gemini   vision — reads dashboard screenshot         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

**Dashboard is the primary source, Postgres is secondary.** The agent reasons from what it sees in the image first. It only queries Postgres to fill gaps the dashboard can't answer — decomposition and segmentation. This mirrors how a senior analyst actually works.

**Evidence objects before narration.** The narrator LLM receives a typed `EvidenceBundle` — it cannot introduce claims that don't exist in the bundle. Every sentence in the briefing maps to a proven, inferred, or explicitly unverified source. The LLM narrates, it does not originate facts.

**Semantic gap matching.** Gap metric names from the reasoning step are matched to dashboard metric names using LLM semantic understanding — "revenue" matches "Daily Revenue ($)" regardless of naming differences across dashboards.

**Two-step vision extraction.** The vision model reads the image and returns markdown. A second fast LLM call normalises the markdown to structured JSON. This makes the pipeline robust to any vision model output format.

**Provider abstraction from day one.** One environment variable switches the entire LLM stack: `LLM_PROVIDER=groq|gemini|anthropic|ollama`. Vision has its own `VISION_PROVIDER`. No code changes required.

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| LLM (reasoning, SQL, narration) | Groq `llama-3.3-70b` | Fast inference, strong reasoning |
| LLM (simple extraction) | Groq `llama-3.1-8b-instant` | Model routing — cheap for simple tasks |
| Vision (dashboard reading) | Ollama `llama3.2-vision` | Local, no quota, chart-capable |
| Database | Postgres + psycopg2 | Real production database |
| Scheduler | APScheduler | In-process, zero infrastructure |
| Email | SMTP (smtplib) | Works with Gmail |
| Slack | Incoming Webhook | One env var to enable |
| Run history | SQLite | Zero setup, portable |
| API | FastAPI | Auto-docs, Pydantic validation |
| UI | Streamlit | Run, History, Logs, Observability tabs |
| Package manager | UV | Fast, lockfile-based |
| Containerization | Docker + docker-compose | One-command deployment |

---

## Project Structure

```
metric-watchdog/
│
├── agents/
│   ├── reader_agent.py        ← vision reading
│   ├── reasoning_agent.py     ← reasons over dashboard
│   ├── diagnosis_agent.py     ← SQL writing + execution + evidence
│   ├── narrator_agent.py      ← sourced briefing writer
│   └── orchestrator.py        ← full pipeline with logging
│
├── core/
│   ├── llm.py                 ← provider router: groq|gemini|anthropic|ollama
│   ├── vision.py              ← provider router + two-step extraction
│   ├── db.py                  ← safe Postgres executor + table whitelist
│   ├── schema.py              ← SchemaContext + DDL parser + auto-discovery
│   ├── run_logger.py          ← plain text log file per day
│   ├── history_store.py       ← SQLite run history
│   ├── token_budget.py        ← schema trimming + cost tracking
│   ├── model_router.py        ← routes stages to correct model tier
│   ├── idempotency.py         ← duplicate run detection
│   └── scheduler.py           ← APScheduler daily trigger
│
├── guardrails/
│   ├── input_guard.py         ← image validation, injection detection
│   ├── output_guard.py        ← briefing validation, SQL scanning
│   └── degradation.py         ← fallback briefings for every failure mode
│
├── observability/
│   ├── tracer.py              ← span-level run tracing to SQLite
│   ├── metrics.py             ← completion rate, error rate, latency, cost
│   └── alerts.py              ← alert rules evaluated against live metrics
│
├── delivery/
│   ├── email_sender.py        ← SMTP delivery
│   └── slack_sender.py        ← webhook, one env var to switch on
│
├── api/
│   ├── main.py                ← FastAPI: /run, /runs, /metrics, /alerts
│   └── schemas.py             ← Pydantic request/response models
│
├── data/
│   ├── schema.sql             ← 5 tables: orders, sessions, refunds,
│   │                             campaign_calendar, metric_baselines
│   └── seed.py                ← 90 days synthetic e-commerce data
│                                 with anomalies injected in last 2 days
│
├── tests/evals/               ← three-level eval harness, 18/18 passing
├── config/
│   ├── settings.py
│   └── schedule.yaml
│
├── ui/app.py                  ← Streamlit: Run, History, Logs, Observability
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Quick Start

### Option 1 — Local

```bash
git clone https://github.com/sanketneuralforge/metric-watchdog.git
cd metric-watchdog

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Configure
cp .env.example .env
# Add your GROQ_API_KEY to .env

# Start Postgres
docker run --name watchdog-pg \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=watchdog \
  -p 5432:5432 -d postgres:15

# Seed synthetic data
uv run python data/seed.py

# Run
./run.sh
```

- Streamlit UI: http://localhost:8501
- FastAPI docs: http://localhost:8000/docs

### Option 2 — Docker

```bash
git clone https://github.com/sanketneuralforge/metric-watchdog.git
cd metric-watchdog
cp .env.example .env
# Add GROQ_API_KEY to .env
docker-compose up
```

---

## Environment Variables

```bash
# Required
GROQ_API_KEY=gsk_...

# LLM providers — one line to switch
LLM_PROVIDER=groq           # groq | gemini | anthropic | ollama
VISION_PROVIDER=ollama      # ollama | gemini | anthropic

# Ollama (local vision)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=llama3.2-vision

# Database
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/watchdog

# Delivery (optional)
EMAIL_ENABLED=false
SLACK_ENABLED=false
SLACK_WEBHOOK_URL=
SMTP_USER=
SMTP_PASSWORD=
ALERT_RECIPIENTS=
```

---

## API Reference

Full interactive docs at `http://localhost:8000/docs`.

```bash
GET  /health                    # system health check
POST /run                       # trigger with server-side image path
POST /run/upload                # trigger with uploaded image file
GET  /runs?limit=20             # list recent runs
GET  /runs/{run_id}             # get specific run detail
GET  /runs/{run_id}/briefing    # get HTML briefing
GET  /metrics?days=7            # production metrics
GET  /alerts?days=7             # active alerts
```

---

## Eval Harness

```bash
# Fast — structural only, no LLM calls, 0.15s
uv run python tests/evals/run_evals.py

# Full — including live LLM calls
uv run python tests/evals/run_evals.py --slow
```

**18/18 passing** across three levels — structural, behavioral, semantic.

---

## Build History

| Stage | Commit | What Was Built |
|---|---|---|
| 2 — MVP | `fd9bedb` | Schema discovery, vision reader, reasoning, diagnosis, semantic gap matching |
| 3 — Delivery | `1f4891a` | Narrator, sourced briefing, email + Slack |
| 3 — Logger | `7df92b2` | Plain text run logger, SQL logging, per-stage timing |
| 4 — Vision fix | `7710139` | Two-step extraction, markdown → JSON via LLM |
| 5 — Evals | `f55eea9` | 18-test eval harness |
| 6 — Guardrails | `62df907` | Input validation, injection defense, output scanning, degradation |
| 7 — Production | `be0bebe` | Model routing, token budget, idempotency, cost tracking |
| 8 — Observability | `2128579` | Span tracing, production metrics, alert rules, observability tab |
| 9 — Deployment | `0484827` | FastAPI REST layer, Docker, docker-compose |


---

## License

MIT — use freely, attribution appreciated.

---

*Built end-to-end across 9 stages as a portfolio demonstration of production-grade autonomous agent engineering.*