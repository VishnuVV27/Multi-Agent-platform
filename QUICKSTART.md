# Quick Start Guide: Testing the MVP End-to-End

This guide walks you through running the first working workflow: **User Prompt → Supervisor (DAG) → Research Agent → Results**

## Prerequisites

- Docker & Docker Compose installed
- Python 3.10+ installed
- `pip install -e .` run in the project directory

## Step 1: Start Services (Docker)

```bash
docker-compose up -d
```

Wait for all services to be healthy:
```bash
docker-compose ps

# Should show:
# postgres     - healthy
# redis        - healthy
# zookeeper    - started
# kafka        - healthy
# temporal     - healthy
```

Check service health:
```bash
curl http://localhost:8000/health
# Should return: {"status": "operational", ...}
```

Access Temporal UI:
```
Open: http://localhost:8080
(Shows all workflows in progress)
```

## Step 2: Start the FastAPI App

In **Terminal 1**:
```bash
python -m src.main
```

You should see:
```
✅ Database initialized
✅ Redis connected
✅ Temporal connected
✅ Kafka initialized
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Start the Temporal Worker

In **Terminal 2**:
```bash
python -m src.workers.temporal_worker
```

You should see:
```
🚀 Temporal worker started on task queue: ai_agents
   Workflows: SupervisorWorkflow, ResearchWorkflow, OrchestratorWorkflow
   Temporal: localhost:7233
```

The worker is now listening for tasks.

## Step 4: Trigger a Workflow

In **Terminal 3**, create a new workflow:

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Research AI trends in 2024",
    "context": {}
  }'
```

Response:
```json
{
  "workflow_id": "f1234567-89ab-cdef-0123-456789abcdef",
  "status": "executing",
  "message": "Workflow started with 1 tasks"
}
```

## Step 5: Monitor Execution

**Check workflow status:**
```bash
curl http://localhost:8000/api/workflows/{workflow_id}
```

**Watch in Temporal UI:**
1. Go to http://localhost:8080
2. Click on the workflow ID
3. See the task execution timeline, logs, and results

**Watch in Terminal 2 (Worker):**
```
[Task Execution Log]
[AUDIT] research_agent executed web_search
Research Agent completed: 3 results found
```

## Step 6: View Results

Once the workflow completes, check the status again:
```bash
curl http://localhost:8000/api/workflows/{workflow_id}
```

Response shows:
```json
{
  "workflow_id": "...",
  "status": "completed",
  "result": {
    "tasks_completed": 1,
    "tasks_failed": 0,
    "results": {
      "t1": {
        "status": "completed",
        "result": {
          "query": "AI trends in 2024",
          "findings": [
            {
              "position": 1,
              "title": "Result 1: ...",
              "url": "...",
              "snippet": "..."
            }
          ],
          "summary": "Research Summary..."
        }
      }
    }
  }
}
```

## Testing Different Prompts

Try various prompts to test the Supervisor's DAG generation:

### Single Agent (Research)
```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search for information about machine learning"}'
```

### Multi-Agent (Research + Analysis)
```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Research and analyze competitor strategies"}'
```

### With Context
```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Research market trends",
    "context": {
      "industry": "SaaS",
      "region": "US",
      "max_results": 10
    }
  }'
```

## Debugging

### Check API Health
```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs  # Swagger UI
```

### Check Database Connection
```bash
docker exec -it multi_agent_ai_platform-postgres-1 \
  psql -U postgres -d multi_agent_ai -c "SELECT 1"
```

### Check Kafka
```bash
docker exec -it multi_agent_ai_platform-kafka-1 \
  kafka-broker-api-versions --bootstrap-server localhost:9092
```

### View Logs
```bash
# API logs
# (Check Terminal 1)

# Worker logs
# (Check Terminal 2)

# Docker logs
docker-compose logs -f temporal
docker-compose logs -f postgres
docker-compose logs -f kafka
```

## What's Happening (Architecture Flow)

```
1. Client sends: POST /api/workflows
   "Research AI trends"
                ↓
2. FastAPI creates workflow_id
   Starts SupervisorWorkflow
                ↓
3. Supervisor Agent executes:
   - Matches keywords ("research") → [research_agent]
   - Builds task DAG → [{id: "t1", agent: "research_agent", input: "..."}]
                ↓
4. OrchestratorWorkflow receives DAG
   For each task:
   - Publishes "agent.started" event to Kafka
   - Executes ResearchWorkflow (child workflow)
                ↓
5. Research Agent executes:
   - Calls Tool Gateway with "web_search" request
   - Tool Gateway checks permission ✓
   - Calls WebSearchTool (returns mock results)
   - Processes + aggregates results
   - Returns TaskOutput
                ↓
6. Orchestrator publishes "agent.completed" to Kafka
   Aggregates all task results
                ↓
7. Workflow completes
   Client polls GET /api/workflows/{workflow_id}
   Receives full results
```

## Next Steps

Once this is working:
1. **Step 4**: Formalize Agent Contract (done, verify tests)
2. **Step 5**: Swap LLM calls for LiteLLM
3. **Step 6**: Enhance Tool Gateway with real tools
4. **Step 7**: Add human approval workflow
5. **Step 8**: Add Analysis Agent + Kafka observability
6. **Step 9**: LLM-power the Supervisor for dynamic DAG generation

## Troubleshooting

**"Workflow not found"**
- Worker might not have picked up the task
- Check that Terminal 2 is running and says "Temporal worker started"

**"Database connection failed"**
- Postgres might not be healthy
- Run: `docker-compose logs postgres`

**"Kafka error"**
- Not critical for MVP; observability will be added in Step 10
- Kafka is optional; can disable with ENABLE_KAFKA_OBSERVABILITY=false

**Port conflicts**
- Change ports in docker-compose.yml and .env
- FastAPI defaults to 8000, Temporal to 7233, etc.

---

**Everything working?** 🎉 You've completed Steps 1-3!

The MVP scaffold is now functional with a complete workflow execution pipeline.
