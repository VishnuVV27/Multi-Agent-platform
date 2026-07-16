# CLAUDE.md — Multi-Agent AI Platform (Full Architecture Reference)

This file gives Claude Code complete context on the system being built. It contains the full design across all 11 architecture components. Read the relevant section before implementing that piece — don't re-derive design decisions that are already specified here.

This is a **solo portfolio build**. Prioritize working end-to-end vertical slices over building every layer as a separate service on day one. Where noted, collapse infra for the MVP and split into real services later.

---

## 0. Core Architecture (the whole system, high level)

**Stack:** Kafka + Temporal + Redis + PostgreSQL + Vector DB

**High-level flow:**
```
User → FastAPI (API Gateway) → Temporal (Workflow Orchestrator)
  → Supervisor Agent (decides which agents + task dependencies)
  → Temporal executes task graph → {Research / Coding / Analysis / Writer} Agents
  → Agents publish events to Kafka (observability only, not control flow)
  → Redis (short-term state) + PostgreSQL (permanent) + Vector DB (long-term memory)
```

**Component responsibilities:**
- **FastAPI**: receive prompts, auth, create workflow requests, return workflow ID, stream status
- **Temporal**: "the brain" — orchestrates task DAGs with explicit dependency management, retries, failures, timeouts, workflow state. Reads task graph from Supervisor; executes in order respecting dependencies
- **Supervisor Agent**: analyzes user prompt, decides which agents are needed and in what order, returns task DAG with dependencies. Example: user request → Supervisor → `{tasks: [{id: "t1", agent: "research"}, {id: "t2", agent: "analysis", depends_on: "t1"}]}`
- **Kafka**: event bus for observability/audit (fire-and-forget). Topics: `agent.started`, `agent.progress`, `agent.completed`, `agent.failed`, `workflow.completed`. NOT used for control flow between agents — Temporal owns that
- **Agent Workers**: independent services, each with `worker.py`, `prompts/`, `memory.py`, `tools.py`. Flow: Receive Task from Temporal → Load Memory → Execute LLM+Tools → Save Memory → Publish Kafka Event (for observability)
- **Redis**: short-term state (current task state, active sessions, agent checkpoints, rate limits, event dedup cache)
- **PostgreSQL**: permanent storage (users, workflows, agent_runs incl. token_usage/cost/duration, results, audit history)
- **Vector DB**: semantic/long-term memory (previous conversations, documents, agent knowledge, user preferences)
- **Event Idempotency**: every Kafka event has unique `event_id`; Redis dedup check before processing: `redis.exists(event_id)`, `redis.set(event_id, "processed", expiration=86400)` prevents duplicate processing
- **Observability**: every request carries `request_id`, `workflow_id`, `agent_id`; monitoring stack = OpenTelemetry + Prometheus + Grafana

**Complete execution flow:** User sends prompt → FastAPI creates workflow → Temporal starts workflow → Supervisor Agent analyzes request → Supervisor returns task DAG (which agents, which order, dependencies) → Temporal reads DAG → Temporal executes task 1 (Research Agent) → waits for completion → Temporal executes task 2 (Analysis Agent, because task 1 is done) → Agent publishes "agent.completed" event to Kafka (observability) → Temporal continues DAG → Final agent (Writer) creates result → Result stored in PostgreSQL → Memory stored in Vector DB → User receives answer.

**Temporal Orchestration Model (production-grade):**
```
Supervisor outputs: {tasks: [{id: "t1", agent: "B"}, {id: "t2", agent: "C", depends_on: "t1"}]}
                        ↓
Temporal reads DAG:  for task in graph:
                       execute(task)
                       wait_for_completion()
                       move_to_next_task()
                        ↓
Agent B executes → publishes event to Kafka (observability, not control)
                        ↓
Temporal sees completion → executes Agent C (explicit scheduling, not event-driven)
```

**Why Temporal orchestrates (not Kafka for control flow):**
- Temporal owns the DAG; it decides when to schedule Agent C based on Agent B's completion
- Agents don't poll Kafka or listen for events; they receive tasks directly from Temporal
- This gives Temporal full control over retries, saga patterns, dependency resolution, failure handling
- Kafka is for broadcast observability (many consumers can listen to "agent.completed"), not for agent-to-agent handoff

**Failure handling flow:**
```
Agent Task → Agent Execution → Failed?
  --No--> Publish event to Kafka → Observability consumes
  --Yes--> Temporal Retry Policy (decides retry/backoff) → Retry Agent
                                 → (on exhaustion) → Publish failure event to Kafka
```
Retry/backoff handled by Temporal; Kafka is observability only.

**Expanded flow (updated_flow.md) adds:** Auth Service (between API and Temporal), Agent Registry (Temporal → Registry → Agents), LLM Gateway (Agents → LLM), Tool Gateway (Agents → Tools), S3/Object Storage, Evaluation Pipeline. Full wiring: `USER→API→AUTH→TEMPORAL→REGISTRY→AGENTS→{LLM, TOOLS, KAFKA, VECTOR, S3, EVAL}`, `KAFKA→TEMPORAL`, `TEMPORAL→REDIS/POSTGRES`, `AGENTS→OBS`.

---

## 0.5 Supervisor Agent (Task Planning & DAG Creation)

**Definition:** A special agent whose job is to analyze the user's request and decide which agents are needed, in what order, and with what dependencies. It creates a task DAG (directed acyclic graph) that Temporal then executes.

**Why needed:** Without it, workflows are hardcoded (`if user_request contains "analyze": run research + analysis agents`). With Supervisor, the workflow is dynamic — different user requests trigger different agent pipelines.

**Architecture:** User Prompt → Supervisor Agent (analyzes) → Task DAG Output → Temporal (orchestrates)

**Example:**
- User: "Research competitors and write a detailed report"
- Supervisor analyzes: "I need research_agent to gather info, analysis_agent to compare, writer_agent to generate report"
- Supervisor returns:
```json
{
  "workflow_id": "wf_123",
  "tasks": [
    {"id": "t1", "agent": "research_agent", "input": "Gather competitor data"},
    {"id": "t2", "agent": "analysis_agent", "input": "Analyze competitors", "depends_on": ["t1"]},
    {"id": "t3", "agent": "writer_agent", "input": "Write report", "depends_on": ["t2"]}
  ]
}
```
- Temporal reads this DAG and executes: t1 → (wait) → t2 → (wait) → t3

**Supervisor Contract:**
```json
{
  "agent_id": "supervisor_agent",
  "input": {
    "user_prompt": "string",
    "context": "object"
  },
  "output": {
    "tasks": [
      {
        "id": "string",
        "agent": "string (agent_id from Agent Registry)",
        "input": "string (task instruction)",
        "depends_on": ["array of task ids, optional"]
      }
    ]
  }
}
```

**Supervisor Responsibilities:**
1. **Request Analysis** — understand what the user actually wants
2. **Agent Selection** — identify which agents have the capabilities needed (consults Agent Registry)
3. **Dependency Resolution** — decide task order (e.g., research must complete before analysis)
4. **Parallelization** — identify tasks that can run in parallel (e.g., if no dependencies, all run simultaneously)
5. **Constraint Handling** — respect user constraints (budget, time, approval requirements)

**Supervisor as an Agent (not special code):**
- Supervisor IS an agent; it follows the Agent Contract just like Research/Coding/Writer agents
- It runs on the same infrastructure (LiteLLM for LLM calls, Tool Gateway for any tools needed)
- It can use tools to inspect Agent Registry, check user preferences, look up past workflows
- Its prompt instructs it to output structured DAG JSON (enforced via output schema validation)

**Output Validation:**
- Temporal validates the DAG before execution: no circular dependencies, all task IDs are unique, all `depends_on` references are valid
- Invalid DAG → error back to user ("Supervisor created invalid plan")

**MVP Implementation:**
- Supervisor prompt: hardcoded instructions to analyze request and output JSON DAG
- Output validation: JSON schema check in Temporal before DAG execution
- No dynamic capability matching yet (hardcode which agents exist); Agent Registry lookup comes later

**Production Implementation:**
- Supervisor uses Agent Registry to dynamically discover available agents and their capabilities
- Supervisor can query user preferences, past workflows, team constraints
- Supervisor can explain its reasoning: "I chose research_agent because it has web_search capability"

---

## 1. Agent Registry

**Definition:** Service discovery system for AI agents — a directory of agents, not the agent's brain. Answers: what agents exist, what can each do, which tools/model, which version is active, availability, how orchestrator discovers/uses them.

**Why needed:** Without it, workflow engine hardcodes `if task=="research": use_research_agent()` — unmanageable at scale with multiple versions/teams.

**Architecture:** User Request → Temporal Workflow Engine → Agent Registry (DB) → {Research Agent, Coding Agent, SQL Agent, Writer Agent}

**What it stores (example):**
```json
{
  "agent_id": "...", "name": "...", "description": "...", "version": "...",
  "status": "...", "capabilities": [], "tools": [],
  "model": {"provider": "...", "name": "..."},
  "prompt_template": "...", "memory": {"enabled": true, "type": "..."},
  "endpoint": "..."
}
```

**Responsibilities:**
1. **Agent Discovery** — find correct agent for a task
2. **Agent Lifecycle Management** — status: Created, Running, Healthy, Unavailable, Deprecated (with heartbeat timestamps)
3. **Version Management** — multiple versions coexist (v1.0 basic → v2.0 +verification → v3.0 +reasoning); registry decides active version
4. **Capability Matching** — agents declare capabilities; registry/supervisor matches task requirement → capability → agent

**Agent Registry vs Prompt Registry vs Memory:**
- **Agent Registry** = *who* the agent is + what it can do (identity, capabilities, tools, version, status, model, endpoint) — static
- **Prompt Registry** = *how* the agent behaves (system prompts, instructions, rules, examples, templates)
- **Memory System** = *what* the agent remembers (learned info: user prefs, past research)

**Suggested DB schema:** `agents` table (id, agent_name, version, description, status, endpoint, created_at, updated_at), `capabilities` table (id, agent_id, capability), `agent_tools` table (id, agent_id, tool_name)

**Registration/Selection flows:**
- Registration: Agent Worker → Register Agent → Agent Registry (stores metadata, loops on heartbeat) → Send Heartbeat; Temporal → Discover Agent → Registry → Return Available Agent
- Selection: User → "Analyze competitors" → Temporal → Find agent with capability `competitor_analysis` → Registry → Return Research Agent → Temporal → Execute Task → Agent → Return Result → Temporal → User

**Recommended implementation:** Initial version = PostgreSQL + Redis Cache. Future scale (thousands of dynamic agents): Consul, etcd, Kubernetes Service Discovery.

---

## 2. Agent Contract

**Definition:** API specification for AI agents — the standard interface every agent must follow. Answers: how does an agent receive a task, what format does it return results in, what events does it publish, what tools can it access.

**Why needed:** Without it, every agent has a different input/output shape (Research Agent: `{question}`, Coding Agent: `{code_request}`, SQL Agent: `{query}`) → workflow engine tightly coupled to every agent individually. With a contract, Temporal only needs to know "Agent Contract," not each agent's format.

**Architecture:** Temporal Workflow Engine → Agent Contract Interface → {Research Agent, Coding Agent, SQL Agent, Writer Agent}

**8-Part Contract Structure:**
1. **Agent Identity** — unique id/name/version
2. **Input Contract** — `task_id`, `workflow_id`, `instruction`, `context{}`, `constraints{max_tokens, deadline}`
3. **Output Contract** — `task_id`, `status`, `result{summary, data}`, `metadata{tokens_used, execution_time}`
4. **Agent Lifecycle Events** — `agent.started`, `agent.progress` (with % and message), `agent.completed` (with result), `agent.failed` (with structured `error{type, message}`)
5. **Capability Contract** — agents declare `capabilities[]` (e.g. `web_search`, `document_analysis`); Registry uses for discovery matching
6. **Tool Permission Contract** — `tools[{name, permission: allowed/denied}]` — security, access control, auditing
7. **Memory Contract** — `memory{short_term{enabled, storage:"redis"}, long_term{enabled, storage:"vector_db"}}`
8. **Error Handling Contract** — `{status:"failed", error:{code:"LLM_TIMEOUT", message, retryable:true/false}}` — workflow engine decides retry vs terminate based on `retryable`

**Example contract:** agent_id, version, capabilities[], input_schema{task, context}, output_schema{result, confidence}, events[], tools[]

**Relationship with other components:** Agent Registry → Agent Contract → {Prompt Registry, LLM Gateway, Tool Gateway, Memory System, Evaluation System}

**Benefits:** Standardization, Scalability (new agents don't require workflow engine changes), Observability, Security, Reliability.

---

## 3. LLM Gateway / Model Router

**Definition:** Centralized intelligence routing layer between agents and LLMs. Unified interface so agents don't need to know provider, hosting location, auth, failure handling, cost calc. **Uses LiteLLM as the model gateway layer.**

**Why needed:** Without it — every agent directly calls its own provider, manages own API keys, no centralized cost tracking, no fallback strategy.

**Architecture:** Agent Workers → Agent Contract → LiteLLM Gateway → Model Router → {OpenAI, Anthropic, Google, Self-Hosted Models}

**7 Responsibilities:**
1. **Model Routing** — based on task requirements (`reasoning:"high"` → GPT-5-class model; `reasoning:"low"` → cheaper model)
2. **Provider Abstraction** — agent sends generic request (`model: "best_reasoning_model"`); gateway maps internally
3. **Model Fallbacks** — Request → primary model → (failure) → fallback model → Success, transparently to the agent
4. **Cost Management** — every request tracked: `{agent, model, input_tokens, output_tokens, cost}`
5. **Token Management** — max_input_tokens, max_output_tokens, context limits per request
6. **Rate Limiting** — per-user and per-agent limits (e.g. User A: 100 req/min, Agent B: 500 req/hour)
7. **Observability** — `{workflow_id, agent_id, model, latency, tokens, cost}` → OpenTelemetry + Prometheus + Grafana

**LLM Request Flow:** Agent → Send LLM Request → LiteLLM Gateway → Select Best Model → Router → Forward Request → Model → Response → Router → Gateway → Agent

**Example routing rules (YAML):**
```yaml
models:
  reasoning: {provider: openai, model: gpt-5}
  coding: {provider: anthropic, model: claude}
  fast: {provider: local, model: llama}
```

**model_registry table:**
```sql
CREATE TABLE model_registry (
  id UUID PRIMARY KEY,
  provider VARCHAR(50),
  model_name VARCHAR(100),
  capability JSON,
  cost_per_token FLOAT,
  status VARCHAR(20)
);
```

**Recommended stack:** LiteLLM (gateway + routing), Vault/Cloud Secret Manager (secrets), OpenTelemetry/Prometheus/Grafana (monitoring).

---

## 4. Tool Execution Layer

**Definition:** The controlled action layer allowing agents to interact with external systems. An LLM can reason but cannot perform real-world actions without tools.

**Why needed:** Without a dedicated tool layer, agents have direct access to Internet/Database/Production Server → no permission control, no auditing, no validation, no security boundary, difficult to monitor.

**Better architecture:** Agent Worker → Agent Contract → Tool Execution Gateway → {Search Tool, Database Tool, Code Sandbox, External APIs}. **The agent does not directly access external systems.**

**What is a tool (example):**
```json
{
  "name": "web_search", "description": "Search the internet",
  "input_schema": {"query": "string"},
  "output_schema": {"results": "array"}
}
```
Agent requests: `{"tool": "web_search", "arguments": {"query": "..."}}`

**5 Tool Gateway Responsibilities:**
1. **Tool Discovery** — maintains available tools (web_search, document_reader, database_query, python_executor, email_sender, api_connector)
2. **Permission Enforcement** — agents only access approved tools. Example: `{"agent_id": "research_agent", "allowed_tools": ["web_search", "document_reader"]}`. Agent cannot call `production_database`/`payment_api` unless explicitly allowed.
3. **Input Validation** — every tool request validated: is the agent allowed? is the query safe? is the schema allowed? is the user authorized?
4. **Execution Isolation** — dangerous tools (e.g. `python_executor`) require sandboxing: Docker, Firecracker, or Kubernetes isolated workloads
5. **Auditing** — every tool call generates an audit record: `{agent_id, tool, input, status, execution_time}`

**3 Tool Categories:**
- **Information Tools** (read-only, low risk): web_search, document_reader, knowledge_base_search, vector_database_query — used by Research/Analyst Agents
- **Action Tools** (modifies external systems, require stronger controls): send_email, create_ticket, update_database, deploy_application
- **Compute Tools** (used for processing): python_executor, sql_engine, code_runner

**Tool Registry (metadata, similar to Agent Registry):**
```json
{
  "tool_id": "web_search", "description": "Search web content",
  "category": "information", "permissions": ["read_only"], "risk_level": "low"
}
```
**Relationship with Agent Registry:** Agent Registry stores which tools an agent has; Tool Registry stores what each tool actually is (its own metadata/risk profile). Reference by ID rather than duplicating.

**Relationship with Agent Contract:** Agent Contract defines "what tools can this agent use?" (`allowed_tools` list) — Tool Gateway enforces this rule at runtime.

**Relationship with Security Layer:** Final permission flow = `User Permission → Agent Permission → Tool Permission → Tool Execution`.

**Tool Execution Data Model:**
```sql
CREATE TABLE tools (
  id UUID PRIMARY KEY, name VARCHAR(100), description TEXT,
  category VARCHAR(50), risk_level VARCHAR(20), status VARCHAR(20)
);

CREATE TABLE tool_permissions (
  id UUID PRIMARY KEY, agent_id UUID, tool_id UUID, permission VARCHAR(50)
);
```

**Recommended Architecture:** Agent Workers → Agent Contract → Tool Execution Gateway → {Tool Registry, Execution Sandbox, External Systems}

**Recommended Technology Stack:**
| Component | Technology |
|---|---|
| Tool Gateway | Custom Service |
| Tool Protocol | MCP-style interface |
| Sandbox | Docker / Firecracker |
| Browser Automation | Playwright |
| Database Access | Restricted SQL Layer |
| Secrets | Vault / Cloud Secret Manager |
| Events | Kafka |
| Audit Storage | PostgreSQL |

**Final definition:** "The secure bridge between AI agents and external capabilities. It provides controlled access to tools while enforcing permissions, validation, isolation, and auditing."

---

## 5. Human Interaction Gateway (HIG) / Human-in-the-Loop Approval

**Definition:** The interface layer between AI agents and human users. Allows agents to request human attention for: Approval, Clarification, Additional information, Decision making, Exception handling. The system dynamically creates agent interaction cards/bots in the UI based on active requests (not a static approval page).

**Why needed:** Autonomous agents can do research/analysis/coding/DB ops/communication/deployment — but some actions require human judgment (deploy to production, send customer comms, access sensitive data, approve financial transactions). Agent should not silently execute these; it should ask: "I need your approval before continuing."

**Core Idea:** Agents never directly communicate with humans.
**Flow:** `Agent → creates approval request → Approval Service → Human Interaction Gateway → Dynamic UI Bot → Human Decision`

**High-Level Architecture:**
```
Agents / Sub Agents → Temporal Workflow ⇄ Approval Service ⇄ Event Bus ⇄ Human Interaction Gateway ⇄ Dynamic Agent UI ⇄ Human User
```

**Approval Request Lifecycle (sequence):** Agent → Request approval → Temporal → Create approval request → Approval Service → Publish interaction request → HIG → Show dynamic agent bot → User → Approve/Reject → HIG → Store decision → Approval Service → Resume workflow → Temporal → Continue execution → Agent

**Dynamic Agent Bots** — UI has no predefined bots; generated dynamically.
Backend sends:
```json
{
  "request_id": "apr_123", "agent_id": "coding_agent", "agent_name": "Coding Agent",
  "request_type": "approval", "action": "production_deployment", "risk": "high"
}
```
Frontend renders a card: Coding Agent — "Needs approval: Deploy version 2.1.0" — Risk: HIGH — [Approve] [Reject]

**Multiple Agents Requesting Approval:** system supports any number of active requests simultaneously (e.g. Research Agent needs private document access, SQL Agent needs to run a production query, Coding Agent needs to deploy, Email Agent needs to send something — all shown as separate cards).

**Agent Interaction Data Model:**
```sql
CREATE TABLE approval_requests (
  id UUID PRIMARY KEY, workflow_id VARCHAR(100), agent_id VARCHAR(100),
  request_type VARCHAR(50), action VARCHAR(100), description TEXT,
  risk_level VARCHAR(20), status VARCHAR(20),
  created_at TIMESTAMP, completed_at TIMESTAMP
);
```

**Example full approval request payload:**
```json
{
  "request_id": "apr_123", "workflow_id": "wf_456",
  "agent": {"id": "deployment_agent", "name": "Deployment Agent"},
  "action": {"type": "deploy", "target": "production"},
  "reason": "Deploy payment service fix", "risk": "high",
  "context": {"changes": ["API update", "Database migration"], "tests_passed": true}
}
```

**4 Approval Types:**
1. **Action Approval** — before performing an action (e.g. "I want to send this email. Approve?")
2. **Plan Approval** — before executing a whole workflow (e.g. agent plan: 1. Collect data 2. Analyze competitors 3. Generate report)
3. **Data Access Approval** — before accessing sensitive info (e.g. customer database access for sales analysis)
4. **Output Approval** — before publishing AI-generated content (e.g. legal document — human review required)

**Risk-Based Approval Rules** — not every action needs approval:
| Action | Risk | Approval |
|---|---|---|
| Summarize document | Low | No |
| Search web | Low | No |
| Generate report | Low | No |
| Send email | Medium | Yes |
| Database modification | High | Yes |
| Production deployment | Critical | Yes |

**Approval Policy Engine (config-driven):**
```yaml
approval_rules:
  production_deployment:
    required: true
    approver: [engineering_team]
  database_write:
    required: true
    approver: [database_admin]
  web_search:
    required: false
```

**Real-Time Communication:** UI needs live updates. `Kafka → Backend Consumer → WebSocket/Server Sent Events → Frontend UI`. Example events: `approval.created`, `approval.waiting`, `approval.approved`, `approval.rejected`.

**Temporal Integration:** Temporal handles workflow suspension.
```
Workflow: Step 1: Analyze request → Step 2: Generate solution
  → Step 3: WAIT FOR HUMAN APPROVAL → Step 4: Execute action
```
Workflow can wait minutes to hours.

**Security Considerations** — HIG should verify: Who approved? Which agent requested it? What action was approved? Was approval still valid?
```json
{"approved_by": "user_123", "approval_time": "2026-07-16T10:30:00", "agent": "coding_agent", "action": "deployment"}
```

**Recommended Technology Stack:**
| Component | Technology |
|---|---|
| Workflow Engine | Temporal |
| Approval API | FastAPI |
| Event Bus | Kafka |
| Real-time Updates | WebSocket |
| UI | React / Next.js |
| Database | PostgreSQL |
| Notifications | Slack / Teams / Email |

**Final definition:** "The dynamic communication layer that allows AI agents to request human decisions with full context. It creates temporary interaction cards in the UI, collects human responses, and safely resumes workflows."

---

## 6. Prompt Management System

**Definition:** The centralized layer responsible for creating, storing, versioning, testing, approving, and deploying agent prompts. Prompts define: agent behavior, reasoning approach, constraints, rules, output format, personality, decision-making style. Acts like a **configuration and behavior management platform for AI agents**.

**Why needed:** Without it — prompt changes require code deployment, no version history, no rollback, no testing process, difficult to compare improvements, no ownership tracking.

**Better Architecture:** Agent → Prompt Management Service → {Prompt Registry → Prompt Database, LLM Gateway}. The agent retrieves the correct prompt dynamically.

**Core Concept — Separation:**
```
Agent Identity → Agent Contract → Prompt Configuration → LLM Execution
```
The agent should know only: `{"agent_id": "research_agent", "prompt_id": "research_prompt"}`. It should NOT contain the actual system_prompt text hardcoded.

**Prompt Structure:** Identity → Role Definition → Instructions → Constraints → Tools Usage Rules → Output Format

**Example Agent Prompt:**
```
You are a Research Agent.
Your responsibilities:
1. Collect reliable information.
2. Verify facts.
3. Analyze available data.
4. Provide structured conclusions.

Rules:
- Do not invent information.
- Mention uncertainty.
- Provide confidence scores.

Output format: JSON.
```

**Prompt Versioning:** every prompt change creates a new version.
Example: `research_agent_prompt` — v1.0 (Basic research instructions) → v1.1 (Added source verification) → v2.0 (Added confidence scoring)

**Prompt Version Model:**
```json
{
  "prompt_id": "research_agent", "version": "2.0", "status": "approved",
  "created_by": "ai_team", "created_at": "2026-07-16"
}
```

**Prompt Lifecycle:** Create Prompt → Test Prompt → Evaluate Performance → Human Approval → Production Release → Monitor

**Prompt Templates** — support dynamic variables `{{role}}`, `{{task}}`, `{{context}}`. Runtime values fill in at execution time to produce the generated prompt.

**Prompt Components:**
1. **System Instructions** — defines agent identity (e.g. "You are a financial analysis agent.")
2. **Behavioral Rules** — defines how the agent should act (e.g. "Always explain assumptions. Never provide unsupported conclusions.")
3. **Tool Instructions** — defines tool usage (e.g. "Use web search before answering market questions.")
4. **Output Schema** — defines response format: `{"summary": "string", "confidence": "number", "sources": []}`

**Prompt Storage Model:**
```sql
CREATE TABLE prompts (
  id UUID PRIMARY KEY, prompt_id VARCHAR(100), version VARCHAR(20),
  content TEXT, status VARCHAR(20), created_by VARCHAR(100), created_at TIMESTAMP
);
```

**Prompt Deployment States:** Draft → Testing → Approved → Production → Deprecated

**Prompt Approval Flow:** Developer Creates Prompt → Test Environment → Evaluation Pipeline → Human Review → Production. Not every prompt should go directly to production.

**Relationship With Agent Registry:** Agent Registry answers "Who is the agent?" `{agent_id, capabilities, tools}`. Prompt Registry answers "How should the agent behave?" `{prompt_id, ...}`.

**Relationship With Agent Contract:** Agent Contract defines what an agent can do. Prompt defines how the agent should behave. Example: Agent Contract: `{allowed_tools: [web_search]}` — Prompt: `{version: "2.0"}`.

**Relationship With LLM Gateway (execution flow):** Agent → Request Prompt → Prompt Service → Return Versioned Prompt → Agent → Send Prompt + Task → LiteLLM → Execute → Model → Response → Result → Agent.

**Relationship With Evaluation Pipeline:** every prompt update should be measured. Example: Prompt Version 1 — Accuracy 82%. Prompt Version 2 — Accuracy 91%. Decision: Deploy Version 2.

**Recommended Technology Stack:**
| Component | Technology |
|---|---|
| Prompt API | FastAPI |
| Storage | PostgreSQL |
| Cache | Redis |
| Version Control | Git-style versioning |
| Experiment Tracking | Langfuse |
| Evaluation | Custom Evaluation Pipeline |
| Deployment | CI/CD Pipeline |

**Prompt Management Benefits:** Version Control (track every behavior change), Rollback (return to previous working prompts), Experimentation (test multiple prompt versions), Governance (approve production changes), Consistency (all agents use managed behavior definitions).

**Final definition:** "The behavior control layer of the agent platform. It manages prompt creation, versioning, testing, approval, and deployment while keeping agent behavior separate from application code."

**Overall architecture summary (as stated in this doc):**
- Agent Registry: Who exists?
- Agent Contract: How does the agent communicate?
- Prompt Management: How should the agent behave?
- LLM Gateway: Which intelligence model executes the behavior?
- Tool Layer: What actions can the agent perform?

---

## 7. Evaluation & Observability Platform

**Definition:** Measures the quality, reliability, and performance of AI agents and workflows. Answers: Did the agent complete the task successfully? Which prompt and model were used? How long did the workflow take? How much did it cost? Why did a workflow fail? How can we improve agent performance?

**Architecture:** `{Agents, Temporal} → Kafka Events → Observability Platform → Evaluation Engine → Metrics Store → Dashboards`

**Responsibilities:**

**Evaluation** (measures agent quality): Task Success Rate, Accuracy, Human Feedback, LLM-as-a-Judge, Prompt Comparison

**Observability** (monitors platform health): Workflow Duration, Agent Latency, Token Usage, Tool Usage, Cost Tracking, Error Rate, Retry Count

**Data Captured (example):**
```json
{
  "workflow_id": "wf_123", "agent": "research_agent", "model": "gpt-5",
  "prompt_version": "v2.1", "duration_ms": 4200, "tokens": 5600,
  "cost": 0.08, "status": "completed"
}
```

**Recommended Stack (Kafka + Industry-Standard Monitoring):**

Event Source → Kafka Event Bus → Monitoring Consumers:

| Component | Technology | Role |
|---|---|---|
| **Event Bus** | Apache Kafka | Agents publish events (agent.started, agent.completed, agent.failed). Kafka durably stores and broadcasts to all consumers |
| **Distributed Tracing** | OpenTelemetry | Consumes Kafka events + instruments agents/tools; tracks request flow across services |
| **Metrics** | Prometheus | Consumes Kafka events; builds metrics (latency, error rates, token usage) |
| **Dashboards** | Grafana | Queries Prometheus/Loki; visualizes real-time system state |
| **Log Aggregation** | Loki / Elasticsearch | Consumes Kafka events + application logs; searchable log UI |
| **LLM-Specific Tracing** | Langfuse | Consumes Kafka events; tracks prompts, models, costs, versions |
| **Time-Series Storage** | PostgreSQL / ClickHouse | Stores metrics, traces, logs (Prometheus → remote storage) |

**Event Flow (Kafka's role in observability):**
```
Agent executes task
  → publishes event to Kafka: {event_type: "agent.completed", agent_id: "...", tokens: 5600, cost: 0.08}
  ↓
Kafka (durable, ordered, replayed)
  ├→ OpenTelemetry consumer → trace repository
  ├→ Prometheus consumer → metrics store
  ├→ Loki consumer → log aggregation
  ├→ Langfuse consumer → LLM tracking UI
  ├→ Audit logger → compliance records
  └→ Data warehouse → analytics
```

**Why Kafka for observability:**
- **Durability**: if a monitoring system goes down, events stay in Kafka; systems catch up on restart
- **Broadcast**: one event → multiple consumers (add new monitoring without changing agents)
- **Replay**: need to reprocess historical events for debugging? Kafka has them
- **Ordering**: events stay ordered per partition (important for workflow state reconstruction)
- **Decoupling**: agents don't know or care what's monitoring them

**Final definition:** "Continuously measures agent quality, workflow performance, and system health via Kafka event stream and industry-standard monitoring tools, enabling visibility, debugging, optimization, and continuous improvement of the AI platform."

**Note for implementation — current (2026) evaluation practice to layer in beyond what's spec'd above:**
- Run evaluation at 3 levels, not just end-to-end: **end-to-end** (task success), **trajectory-level** (were the tool calls/plan reasonable), **component-level** (isolate a single sub-agent/tool/retriever)
- Run eval at 3 lifecycle points: offline (curated dataset), online (sampled live traffic — catches drift that offline misses), pre-merge in CI
- Build golden datasets from real production logs and known failures, not synthetic examples — start with ~100 high-quality examples
- Consider DeepEval alongside Langfuse: Langfuse handles tracing/prompt versioning, DeepEval is a PyTest-style assertion library that lives in CI

---

## 8. Security Layer

**Definition:** Ensures agents, tools, workflows, and users operate within defined security boundaries. Provides authentication, authorization, secret management, auditing, and policy enforcement across the platform.

**Architecture:**
```
User → Authentication → Authorization → Policy Engine → {Agents → Audit Logs, Tool Gateway → Secrets Manager}
```

**Responsibilities:**

**Authentication** — verify identity of users and services. Examples: OAuth2, OpenID Connect (OIDC), JWT

**Authorization** — control what users and agents are allowed to do. Examples: Role-Based Access Control (RBAC), Attribute-Based Access Control (ABAC)

**Policy Enforcement** — define platform-wide security rules. Examples: which agent can access which tools, which workflows require approval, allowed models for specific agents. **This is the canonical policy source — Tool Gateway and HIG's approval rules should consume from here, not maintain separate config.**

**Secrets Management** — securely manage API Keys, Database Credentials, Cloud Credentials, Third-party Tokens. **Secrets should never be hardcoded into prompts or application code.**

**Audit Logging** — record security-sensitive events. Examples: Login, Agent execution, Tool invocation, Approval decisions, Permission changes.

**Recommended Stack:**
| Component | Technology |
|---|---|
| Authentication | Keycloak / Auth0 |
| Authorization | OPA (Open Policy Agent) / Casbin |
| Secrets | HashiCorp Vault / Cloud Secret Manager |
| Audit Logs | PostgreSQL + Kafka |
| Identity | JWT / OAuth2 / OIDC |

**Final definition:** "Protects the AI platform by enforcing identity, permissions, policies, secret management, and auditing across users, agents, tools, and workflows."

---

## 9. Workflow State Visualization

**Definition:** Provides a real-time view of workflow execution, agent activities, approvals, and task progress. Enables users and operators to monitor, debug, and inspect running or completed workflows.

**Architecture:** `Temporal → Kafka Events → Workflow State Service → Workflow Dashboard`

**Responsibilities:**

**Workflow Monitoring** — track lifecycle. States: Pending, Running, Waiting for Approval, Completed, Failed, Cancelled

**Agent Monitoring** — display: Active Agent, Completed Agents, Failed Agents, Waiting Agents

**Progress Tracking** — monitor: Completed Tasks, Remaining Tasks, Execution Percentage, Estimated Completion Time

**Human Interaction Status** — display pending requests from agents. Examples: Approval Required, User Input Required, Waiting for Decision

**Execution Timeline** — maintain chronological history of events:
```
10:00 Workflow Started
10:01 Research Agent Started
10:04 Research Agent Completed
10:05 Coding Agent Started
10:08 Waiting for Human Approval
10:15 Approved
10:18 Deployment Completed
```

**Dashboard Components:** Active Workflows, Workflow Graph, Agent Status, Approval Requests, Execution Timeline, Logs, Metrics

**Recommended Stack:**
| Component | Technology |
|---|---|
| Workflow Engine | Temporal |
| Event Streaming | Kafka |
| Backend | FastAPI |
| Real-time Updates | WebSocket |
| Frontend | React / Next.js |
| Visualization | React Flow / Mermaid |

**Final definition:** "Provides a live operational view of workflows, agent execution, approvals, and system state, enabling monitoring, debugging, and operational visibility across the AI platform."

---

## 10. Rate Limiting & Budget Control

**Definition:** Manages API usage, token consumption, and spending across users, agents, workflows, and LLM providers. Ensures fair resource usage while preventing excessive costs and service abuse.

**Architecture:** `Agent Request → Rate Limiter → Budget Manager → LLM Gateway → Usage Store` (Rate Limiter and Budget Manager both also write directly to Usage Store)

**This layer sits upstream of the LLM Gateway** — it's the policy/tracking layer; the LLM Gateway's own rate limiting is the downstream enforcement point. They are not duplicates.

**Responsibilities:**

**Rate Limiting** — control request frequency. Examples: Per User, Per Agent, Per Workflow, Per API Key

**Token Management** — track: Input Tokens, Output Tokens, Total Tokens, Daily Usage

**Budget Control** — manage spending limits. Examples: User Budget, Team Budget, Workflow Budget, Monthly Budget

**Provider Quotas** — monitor provider-specific limits. Examples: Requests per Minute (RPM), Tokens per Minute (TPM), Daily Quotas

**Cost Tracking** — track costs by: User, Agent, Workflow, Model, Provider

**Example Budget Policy (YAML):**
```yaml
users:
  free:
    requests_per_minute: 20
    monthly_budget: 10
  enterprise:
    requests_per_minute: 500
    monthly_budget: unlimited

agents:
  research_agent:
    max_tokens: 50000

workflows:
  max_cost: 5.00
```

**Dashboard Metrics:** Requests per Minute, Token Usage, Cost per Workflow, Cost per Agent, Daily Spend, Monthly Spend, Provider Utilization

**Recommended Stack:**
| Component | Technology |
|---|---|
| Rate Limiting | Redis |
| Budget Tracking | PostgreSQL |
| Caching | Redis |
| Monitoring | Prometheus |
| Dashboards | Grafana |

**Final definition:** "Manages request rates, token usage, provider quotas, and spending limits to ensure efficient, predictable, and cost-effective operation of the AI platform."

---

## 11. Data Layer Separation

**Definition:** Defines how different types of data are stored and managed within the AI platform. Instead of storing everything in a single database, each data type is isolated based on its purpose, lifecycle, and access pattern.

**Architecture:** `Agents → {PostgreSQL, Redis, Vector Database, Object Storage, Kafka}`

**Responsibilities:**

**Operational Data** — stores platform metadata. Examples: Users, Workflows, Agents, Approvals, Configurations. **Recommended: PostgreSQL**

**Memory** — stores temporary execution state. Examples: Active Sessions, Workflow Cache, Short-Term Agent Memory. **Recommended: Redis**

**Knowledge & Embeddings** — stores semantic information. Examples: Document Embeddings, Knowledge Base, Long-Term Agent Memory. **Recommended: pgvector / Milvus / Qdrant**

**File Storage** — stores large files. Examples: PDFs, Images, Reports, Generated Files. **Recommended: S3 / MinIO**

**Event Streaming** — stores and distributes events. Examples: Agent Started, Agent Completed, Approval Requested, Workflow Failed. **Recommended: Kafka**

**Data Ownership (canonical table — check this before storing any new data type anywhere):**
| Data Type | Storage |
|---|---|
| Users | PostgreSQL |
| Agents | PostgreSQL |
| Workflows | PostgreSQL |
| Short-Term Memory | Redis |
| Long-Term Memory | Vector Database |
| Documents | Object Storage |
| Events | Kafka |

**Recommended Stack:**
| Component | Technology |
|---|---|
| Relational Data | PostgreSQL |
| Cache | Redis |
| Vector Database | pgvector / Qdrant / Milvus |
| Object Storage | MinIO / AWS S3 |
| Event Streaming | Kafka |

**Final definition:** "Organizes operational data, memory, knowledge, files, and events into purpose-built storage systems, ensuring scalability, maintainability, and high performance across the AI platform."

---

## MVP Build Order (collapse for solo build, split later)

Do not build all 11 components as separate services on day one. Build vertically — get one full workflow (supervisor → agent → tool → approval → result) working before adding complexity.

1. Scaffold: FastAPI + Temporal worker + Postgres + Redis via docker-compose
2. Supervisor Agent (the entry point): takes user prompt, returns task DAG. Start simple: hardcoded rules, no LLM yet (just JSON logic to decide which agents to use). Output format: `{tasks: [{id, agent, input, depends_on}]}`
3. One agent (Research Agent), one tool (web_search), Temporal workflow executes the DAG from Supervisor
4. Agent Contract as code: a Pydantic base class every agent subclasses (`agent_id`, `input_schema`, `output_schema`, `capabilities`, `allowed_tools`) — collapses Agent Registry + Agent Contract into code for MVP
5. Swap direct LLM calls for LiteLLM (Supervisor + Research Agent both use it)
6. Tool Gateway: wrap tool calls with `agent_id → allowed_tools` permission check (no DB yet, just a dict)
7. HIG: one Temporal signal + one FastAPI approval endpoint + minimal approval page
8. Second agent (Analysis Agent) + Kafka: adds multi-agent sequential handoff. Kafka publishes events for observability. Temporal orchestrates the DAG (Agent A → wait → Agent B)
9. Supervisor becomes LLM-powered: use an LLM to analyze requests and generate task DAGs dynamically (not hardcoded rules)
10. Observability: Langfuse tracing on every agent/supervisor call
11. Prompt versioning (files + version string is fine before a full DB-backed system), rate limiting, basic auth
12. Workflow visualization dashboard — last, least interview-signal value until everything else works

## Conventions

- All agent code subclasses the shared `BaseAgent` contract — no agent invents its own input/output shape
- Agents never call tools directly — always through the Tool Gateway permission check
- Agents never call LLM providers directly — always through LiteLLM
- Every agent lifecycle event (`agent.started`, `agent.completed`, `agent.failed`) publishes to Kafka, even in local dev
- Secrets never appear in prompts, code, or config files — env vars / local `.env` (gitignored) for now, Vault later
- Every tool call and approval decision gets an audit log row in Postgres
- Check the Data Ownership table (Section 11) before storing any new data type anywhere

## Design Decisions (locked in)

- **Supervisor Agent at workflow entry point** — analyzes user prompt, returns task DAG (with dependencies). Temporal then orchestrates DAG execution. This enables dynamic multi-agent workflows without hardcoding
- **Temporal orchestrates control flow** — Temporal owns the task DAG and decides when to schedule each agent based on dependencies. Production-grade (used at Uber, Netflix). Agents don't wait for Kafka events; they receive tasks directly from Temporal
- **Kafka + Industry-Standard Monitoring (the observability backbone)** — agents publish events to Kafka; industry-standard tools (OpenTelemetry, Prometheus, Grafana, Loki, Langfuse) consume and visualize. Kafka provides durability, broadcast, replay, ordering, decoupling. NOT used for agent-to-agent control flow — Temporal orchestrates that. This setup avoids tight coupling while maintaining operational visibility
- **Agent Registry is Postgres tables (MVP)** — future scale (thousands of dynamic agents): Consul / etcd / K8s Service Discovery
- **Tool metadata deduplication** — single `tools` table + `tool_permissions` join table, referenced by ID everywhere else. No duplication across Agent Registry, Agent Contract, Tool Registry

## Open Design Questions (resolve as you go, don't block on these)

- Supervisor agent behavior on complex requests (e.g., agent selection from a large pool, dynamic parallelization, constraint optimization) — start simple (hardcoded DAG logic), add LLM-powered planning when needed
- Whether to add a "Supervisor Approval" step before Temporal executes a DAG (e.g., user reviews the plan before agents run) — flag when needed
