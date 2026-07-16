# Multi-Agent AI Platform

A production-grade, orchestration-first multi-agent AI platform built with Temporal, Kafka, and industry-standard observability tools.

## Architecture

- **Orchestration**: Temporal for deterministic workflow execution
- **Event Bus**: Kafka for reliable event streaming
- **Database**: PostgreSQL for persistent storage
- **Cache**: Redis for session state and caching
- **Observability**: OpenTelemetry, Prometheus, Grafana, Langfuse
- **API**: FastAPI for the control plane

## Quick Start

### 1. Clone and Setup

```bash
cd /Users/vishnu/Documents/Multi_Agent_AI_Platform
cp .env.example .env
```

### 2. Start Services with Docker

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Kafka (port 9092)
- Temporal (port 7233, UI at 8080)
- Zookeeper (port 2181)

### 3. Install Python Dependencies

```bash
pip install -e .
```

Or with dev dependencies:
```bash
pip install -e ".[dev]"
```

### 4. Initialize Database

```bash
python -m src.main  # This will initialize the database on startup
```

### 5. Run the API

```bash
python -m src.main
```

The API will be available at `http://localhost:8000`

Check health at `http://localhost:8000/health`

API docs at `http://localhost:8000/docs`

## Project Structure

```
src/
├── main.py                 # FastAPI entry point
├── config.py               # Configuration management
├── agents/                 # Agent implementations
├── workflows/              # Temporal workflows
├── tools/                  # Tool definitions and execution
├── llm/                    # LLM gateway (LiteLLM)
├── prompts/                # Prompt templates and versioning
├── registry/               # Agent and tool registries
├── routes/                 # FastAPI endpoints
├── approval/               # Human-in-the-loop approval
├── events/                 # Event publishing
├── infrastructure/         # Database, Redis, Kafka, Temporal clients
├── rate_limiting/          # Rate limiting logic
├── security/               # Authentication/authorization
├── observability/          # Tracing and monitoring
└── models/                 # SQLAlchemy ORM models
```

## Development

### Run Tests

```bash
pytest tests/
```

### Code Quality

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
```

### View Temporal UI

Open http://localhost:8080 to see workflows in progress

## MVP Milestones

- [ ] Step 1: Infrastructure scaffold (docker-compose, FastAPI, health checks)
- [ ] Step 2: Supervisor Agent (hardcoded DAG rules)
- [ ] Step 3: Research Agent + web_search tool (end-to-end working)
- [ ] Step 4: Agent Contract as code (Pydantic base class)
- [ ] Step 5: LiteLLM integration (model routing)
- [ ] Step 6: Tool Gateway (permission enforcement)
- [ ] Step 7: Human approval workflow (Temporal signals)
- [ ] Step 8: Analysis Agent + Kafka (multi-agent DAG)
- [ ] Step 9: LLM-powered Supervisor (dynamic planning)
- [ ] Step 10: Langfuse observability (tracing + cost tracking)
- [ ] Step 11: Rate limiting + auth + prompt versioning
- [ ] Step 12: Dashboard (optional)

## Key Design Decisions

1. **Temporal orchestrates, not Kafka** - Temporal owns the task DAG; Kafka is observability only
2. **Agent Contract first** - Every agent is a Pydantic model with standardized I/O
3. **Tool Gateway enforces permissions** - No agent can call tools directly
4. **Production-grade observability** - All LLM calls traced to Langfuse with cost tracking
5. **Event-driven for visibility** - Kafka publishes all agent lifecycle events

## Contributing

Follow the conventions defined in `CLAUDE.md`:
- All agents subclass `BaseAgent`
- All tools go through `Tool Gateway`
- All LLM calls go through `LiteLLM`
- All events publish to Kafka
- Secrets in env vars, never in code

## Support

See `CLAUDE.md` for full architecture documentation and design decisions.
