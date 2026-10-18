# Multi-Agent AI Platform

A production-grade, orchestration-first multi-agent AI platform. A Supervisor agent plans a task DAG from a natural-language prompt, **Temporal** executes it with explicit dependency management and retries, and specialized agents (Research, Analysis, Coding, Critic, Writer) carry out the work — with a human approval gate for anything risky.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![Temporal](https://img.shields.io/badge/orchestration-Temporal-000000)
![Next.js](https://img.shields.io/badge/dashboard-Next.js%2014-black)
![Status](https://img.shields.io/badge/status-active%20development-yellow)

---

## Why this exists

Most "multi-agent" demos hardcode which agent runs when. This platform separates **planning** from **execution**: a Supervisor agent decides *what* needs to happen and in what order, and Temporal — not the agents themselves — decides *when* each step actually runs, with retries, timeouts, and failure handling for free. Kafka sits alongside purely for observability; it never drives control flow.

```
User → FastAPI → Temporal Workflow
          │
          ▼
   Supervisor Agent  (plans a task DAG)
          │
          ▼
   Temporal executes the DAG, respecting dependencies
          │
   ┌──────┼───────┬─────────┬─────────┐
   ▼      ▼       ▼         ▼         ▼
Research Analysis Coding   Critic   Writer
   │      │       │         │         │
   └──────┴───────┴─────────┴─────────┘
          │ (lifecycle events — observability only)
          ▼
        Kafka → Langfuse / Prometheus / Grafana

Agents also read/write:
  Redis (short-term state) · PostgreSQL (durable state) · pgvector (long-term memory)

Risky actions pause the workflow and raise a Human-in-the-Loop
approval request, resumed via a Temporal signal once a human decides.
```

## Features

- **Dynamic task planning** — the Supervisor agent turns a free-text prompt into a dependency-aware task DAG; Temporal validates it (no cycles, unique IDs, valid references) before running it
- **Five specialized agents** — Research (web search), Analysis, Coding, Critic (reviews the Coding agent's output), Writer — all subclassing one `BaseAgent` contract
- **Human-in-the-Loop approvals** — risky agent actions suspend the Temporal workflow and create a dynamic approval request; a human approves/rejects from the dashboard and the workflow resumes exactly where it left off
- **Tool Gateway** — agents never call tools directly; every call (web search, DB query, code execution, document read) goes through a permission-checked gateway with an audit trail
- **LLM Gateway via LiteLLM** — provider-agnostic model routing with per-call cost and token tracking
- **Prompt registry** — versioned prompt templates (`src/prompts/templates/`) per agent/task, decoupled from code
- **Skills library** — reusable task skills (TDD, debugging, frontend design, docx/pptx/xlsx/pdf generation, MCP builder, etc.) agents can draw on
- **Long-term memory** — hybrid retrieval over pgvector embeddings so agents can recall prior runs
- **Full observability** — Langfuse tracing, cost tracking, and a live Next.js dashboard for workflows, approvals, memory, and rate limits
- **Rate limiting & budget control** — per-user/agent/workflow limits enforced upstream of the LLM Gateway

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| Orchestration | Temporal |
| Event bus (observability) | Kafka |
| Durable storage | PostgreSQL |
| Short-term state / cache | Redis |
| Long-term memory | pgvector |
| LLM routing | LiteLLM |
| Tracing & cost | Langfuse |
| Dashboard | Next.js 14, Tailwind, Recharts, React Flow |

## Quick start

### 1. Clone and configure

```bash
cd Multi-Agent-platform
cp .env.example .env   # fill in your LLM provider keys, etc.
```

### 2. Start infrastructure

```bash
docker compose up -d
```

Brings up:

| Service | Port |
|---|---|
| PostgreSQL (pgvector) | 5432 |
| Redis | 6379 |
| Kafka | 9092 |
| Zookeeper | 2181 |
| Temporal (+ UI) | 7233 / 8080 |

### 3. Install dependencies and run the API

```bash
pip install -r requirements.txt
python -m src.main
```

| Resource | URL |
|---|---|
| API | http://localhost:8000 |
| Health check | http://localhost:8000/health |
| Interactive API docs | http://localhost:8000/docs |
| Temporal UI | http://localhost:8080 |

### 4. Run the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard at http://localhost:3000 — workflow list/detail, approvals, memory browser, metrics, and rate limiting.

## API surface

| Prefix | Covers |
|---|---|
| `/api/workflows` | Create/inspect workflows, trigger the Supervisor → agent DAG |
| `/api/tools` | Tool Gateway introspection |
| `/api/approvals` | Human-in-the-loop approval requests and decisions |
| `/api/memory` | Long-term (vector) memory read/search |
| `/api/observability` | Traces, cost, token usage |
| `/api/rate-limiting` | Usage and budget status |
| `/api/prompts` | Prompt template registry |
| `/api/skills` | Skills library catalog |

## Project structure

```
src/
├── main.py                 # FastAPI entry point
├── config.py                # Settings (pydantic-settings, env-driven)
├── agents/                  # research, analysis, coding, critic, writer, supervisor
├── workflows/                # Temporal workflows — one per agent + the orchestrator
├── workers/                  # Temporal worker process
├── tools/                    # web_search, database_query, code_executor, document_reader + gateway
├── llm/                       # LiteLLM gateway, cost tracker, model config
├── prompts/                   # Versioned prompt registry + templates
├── skills/                    # Skills library + catalog
├── approval/                  # HIG approval service and models
├── memory/                    # Embedding service + hybrid (vector) retriever
├── infrastructure/            # Postgres, Redis, Temporal/Kafka clients
├── observability/             # Langfuse client, evaluation service, progress tracking
├── routes/                    # FastAPI routers (see API surface above)
└── models/                    # SQLAlchemy ORM models

dashboard/                   # Next.js 14 dashboard (workflows, approvals, memory, metrics)
```

## Development

```bash
pytest tests/                        # run tests
black src/ tests/ && isort src/ tests/   # format
flake8 src/ tests/ && mypy src/          # lint + type-check
```

## Design decisions

1. **Temporal orchestrates, Kafka only observes** — Temporal owns the task DAG and schedules every agent explicitly; Kafka broadcasts lifecycle events to monitoring consumers and never drives control flow
2. **Agent Contract first** — every agent subclasses `BaseAgent` with a standardized input/output shape, so Temporal only needs to know the contract, not each agent's internals
3. **Tool Gateway enforces permissions** — no agent calls a tool directly; every call is permission-checked and audited
4. **Prompts are data, not code** — prompt templates are versioned files, not hardcoded strings, so behavior changes don't require a redeploy
5. **Risk-based human approval** — low-risk actions (search, summarize) run autonomously; higher-risk ones pause the workflow for a human decision via a Temporal signal

Full architecture rationale (all 11 subsystems, including ones still being layered in) lives in [`CLAUDE.md`](CLAUDE.md).

## Contributing

- All agents subclass `BaseAgent` — no agent invents its own input/output shape
- All tool calls go through the Tool Gateway
- All LLM calls go through LiteLLM
- All agent lifecycle events publish to Kafka, even in local dev
- Secrets live in `.env` (gitignored), never in code or prompts
