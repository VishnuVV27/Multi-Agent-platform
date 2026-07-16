# 🧪 Testing Guide - Multi-Agent AI Platform

Complete testing strategy: Unit → Integration → Manual → E2E

---

## **Phase 1: Setup Local Environment**

### **1.1 Install Dependencies**

```bash
# Backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"

# Frontend
cd dashboard
npm install
cd ..
```

### **1.2 Environment Variables**

```bash
# Create .env file
cat > .env << 'EOF'
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=multi_agent_ai

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Temporal
TEMPORAL_HOST=localhost
TEMPORAL_PORT=7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=ai_agents

# LLM
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Langfuse (optional for tracing)
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# API
API_ENVIRONMENT=development
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=INFO

# Feature flags
ENABLE_APPROVAL_WORKFLOW=true
ENABLE_KAFKA_OBSERVABILITY=true
ENABLE_LANGFUSE_TRACING=true
EOF
```

### **1.3 Start Infrastructure (Docker)**

```bash
# Start all services (PostgreSQL, Redis, Kafka, Temporal)
docker-compose up -d

# Verify services are healthy
docker-compose ps
# Should show all services as "healthy" or "running"

# Check database
docker-compose exec postgres psql -U postgres -d multi_agent_ai -c "\dt"

# Check Redis
docker-compose exec redis redis-cli ping
# Should respond: PONG

# Check Kafka
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Check Temporal UI
# Open http://localhost:8080 in browser
```

---

## **Phase 2: Unit & Integration Tests**

### **2.1 Run Unit Tests**

```bash
# Memory system tests
pytest tests/unit/test_memory.py -v

# Rate limiting tests
pytest tests/unit/test_rate_limiting.py -v

# Budget manager tests
pytest tests/unit/test_budget.py -v

# Run all unit tests
pytest tests/unit/ -v --cov=src --cov-report=html
```

**Expected Output:**
```
test_memory.py::test_embedding_generation PASSED
test_memory.py::test_bm25_search PASSED
test_memory.py::test_dense_search PASSED
test_memory.py::test_reranking PASSED
test_rate_limiting.py::test_token_bucket PASSED
test_rate_limiting.py::test_budget_enforcement PASSED
```

### **2.2 Run Integration Tests**

```bash
# Full workflow integration
pytest tests/integration/test_memory_integration.py -v

# Supervisor agent planning
pytest tests/integration/test_supervisor.py -v

# Orchestrator execution
pytest tests/integration/test_orchestrator.py -v

# Rate limiting integration
pytest tests/integration/test_rate_limiting_integration.py -v

# Run all integration tests
pytest tests/integration/ -v
```

**Expected Output:**
```
test_memory_integration.py::test_save_and_retrieve PASSED
test_supervisor.py::test_plan_with_memory PASSED
test_orchestrator.py::test_dag_execution PASSED
test_rate_limiting_integration.py::test_budget_enforcement PASSED
```

### **2.3 Test Coverage Report**

```bash
# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html
```

Expected: **>80% coverage** on core modules

---

## **Phase 3: Manual API Testing**

### **3.1 Start Backend Server**

```bash
# Terminal 1: Start API server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Should see:
# ✅ All services initialized
# ✅ Uvicorn running on http://0.0.0.0:8000
```

### **3.2 Test Health Check**

```bash
# Terminal 2: Test basic health
curl http://localhost:8000/health

# Expected response:
{
  "status": "operational",
  "services": {
    "database": "healthy",
    "redis": "healthy"
  },
  "environment": "development"
}
```

### **3.3 Test API Endpoints**

#### **A. Create Workflow**

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Research AI trends and write a report"
  }'

# Expected response:
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Workflow created"
}

# Save workflow_id for next calls
WORKFLOW_ID="550e8400-e29b-41d4-a716-446655440000"
```

#### **B. Get Workflow Status**

```bash
curl http://localhost:8000/api/workflows/$WORKFLOW_ID

# Expected response:
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "tasks": 2,
    "agents": ["research_agent", "writer_agent"],
    "cost": 0.08,
    "tokens": 2400
  }
}
```

#### **C. Test Rate Limiting**

```bash
# Check rate limit
curl http://localhost:8000/api/rate-limiting/check/user123

# Expected response:
{
  "allowed": true,
  "remaining": 19,
  "reset_in_seconds": 60,
  "limit": 20
}

# Check budget
curl http://localhost:8000/api/rate-limiting/budget/user123

# Expected response:
{
  "allowed": true,
  "monthly_budget": 10.0,
  "used": 0.08,
  "remaining": 9.92,
  "percentage_used": 0.8
}
```

#### **D. Test Memory/RAG**

```bash
# Retrieve similar workflows
curl -X POST http://localhost:8000/api/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "research and write report",
    "top_k": 3
  }'

# Expected response:
{
  "results": [
    {
      "workflow_id": "...",
      "user_request": "...",
      "score": 0.92,
      "success": true,
      "cost": 0.08
    }
  ],
  "execution_time_ms": 45
}
```

#### **E. Test Approvals**

```bash
# Create approval request
curl -X POST http://localhost:8000/api/approvals \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "coding_agent",
    "action": "Deploy to production",
    "risk_level": "CRITICAL",
    "description": "Deploy version 2.1.0"
  }'

# Expected response:
{
  "request_id": "apr_001",
  "status": "pending",
  "created_at": "2026-07-17T10:30:00"
}

# Approve request
curl -X POST http://localhost:8000/api/approvals/apr_001/approve

# Expected response:
{
  "status": "approved",
  "approved_at": "2026-07-17T10:31:00"
}
```

#### **F. Test Observability**

```bash
# Get summary
curl http://localhost:8000/api/observability/summary

# Expected response:
{
  "total_workflows": 5,
  "completed": 5,
  "failed": 0,
  "average_cost": 0.072,
  "total_tokens": 12000
}

# Get cost metrics
curl http://localhost:8000/api/observability/metrics/costs

# Get latency metrics
curl http://localhost:8000/api/observability/metrics/latency
```

### **3.4 Test with Postman/Insomnia**

```
Import collection from:
docs/postman_collection.json

Or create manually:

Method: POST
URL: http://localhost:8000/api/workflows
Headers: Content-Type: application/json
Body: {
  "prompt": "Research competitors and write analysis"
}

Method: GET
URL: http://localhost:8000/api/workflows/{workflow_id}
```

---

## **Phase 4: Frontend Dashboard Testing**

### **4.1 Start Frontend Server**

```bash
# Terminal 3: Start dashboard
cd dashboard
npm run dev

# Should see:
# ✅ Local: http://localhost:3000
```

### **4.2 Test Dashboard Pages**

#### **A. Workflows Page (http://localhost:3000)**
- [ ] Displays list of workflows
- [ ] Click workflow to see details
- [ ] Status badges show correct colors (running=blue, completed=green, failed=red)
- [ ] Shows cost per workflow
- [ ] Shows agent tags

#### **B. Metrics Page (http://localhost:3000/metrics)**
- [ ] Shows summary cards (cost, count, success rate, latency)
- [ ] Cards display correct values
- [ ] Charts render (placeholder for now)

#### **C. Approvals Page (http://localhost:3000/approvals)**
- [ ] Displays approval cards
- [ ] Cards have correct risk colors:
  - [ ] CRITICAL = RED ✅
  - [ ] HIGH = ORANGE ✅
  - [ ] MEDIUM = AMBER ✅
  - [ ] LOW = EMERALD ✅
- [ ] **NO VIOLET anywhere** ✅
- [ ] Approval buttons work (click Approve → green checkmark animation)
- [ ] Rejection buttons work (click Reject → red X animation)
- [ ] Stats cards update (Pending/Completed counts)
- [ ] Empty state shows when all approved
- [ ] Glassmorphism effect visible (backdrop blur)
- [ ] Bento Grid responsive:
  - [ ] Desktop: 3 columns
  - [ ] Tablet: 2 columns
  - [ ] Mobile: 1 column

#### **D. Budget Page (http://localhost:3000/rate-limiting)**
- [ ] Shows budget progress bar
- [ ] Shows requests per minute
- [ ] Shows daily token usage
- [ ] Tier info displayed (Free/Pro/Enterprise)

### **4.3 Test Responsiveness**

```bash
# Test on different screen sizes
# Chrome DevTools → Toggle Device Toolbar

Widths to test:
- 375px (iPhone SE)
- 768px (iPad)
- 1024px (iPad Pro)
- 1920px (Desktop)

Verify:
- [ ] Layouts adapt properly
- [ ] Text readable on all sizes
- [ ] Buttons/inputs remain usable
- [ ] No horizontal scrolling on mobile
```

---

## **Phase 5: End-to-End Workflow Testing**

### **5.1 Complete Workflow Execution**

**Scenario: "Research AI trends and write a comprehensive report"**

```bash
# Step 1: Create workflow
WORKFLOW_ID=$(curl -s -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Research AI trends and write a comprehensive report"}' \
  | jq -r '.workflow_id')

echo "Created workflow: $WORKFLOW_ID"

# Step 2: Poll for completion (max 5 minutes)
for i in {1..60}; do
  STATUS=$(curl -s http://localhost:8000/api/workflows/$WORKFLOW_ID | jq -r '.status')
  echo "[$i/60] Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 5
done

# Step 3: Check final result
curl http://localhost:8000/api/workflows/$WORKFLOW_ID | jq .

# Expected:
# - status: "completed"
# - tasks_completed: 2+
# - total_cost: > 0.05
# - tokens: > 1000
```

### **5.2 Test Approval Flow**

**Scenario: Require approval before deployment**

```bash
# 1. Submit workflow that needs approval
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Deploy version 2.0 to production",
    "requires_approval": true
  }'

# 2. Workflow should pause waiting for approval
# Check approvals page (http://localhost:3000/approvals)

# 3. Approve/Reject in UI
# Click "Approve" or "Reject" button

# 4. Workflow should resume or fail
curl http://localhost:8000/api/workflows/$WORKFLOW_ID

# Expected: status changes to "completed" or "failed"
```

### **5.3 Test Rate Limiting**

**Scenario: Exceed rate limit**

```bash
# Make 25 requests rapidly (exceeds limit of 20/min)
for i in {1..25}; do
  echo "Request $i"
  curl -s http://localhost:8000/api/rate-limiting/check/testuser \
    | jq '.allowed'
  sleep 0.2
done

# Expected:
# First 20: allowed=true
# Next 5: allowed=false
```

### **5.4 Test Budget Enforcement**

**Scenario: Exceed monthly budget**

```bash
# User has $10 budget
# Each workflow costs ~$0.50

# Make 21 workflows (total $10.50 > budget)
for i in {1..21}; do
  echo "Workflow $i"
  
  # Check budget first
  ALLOWED=$(curl -s http://localhost:8000/api/rate-limiting/budget/user123 \
    | jq '.allowed')
  
  if [ "$ALLOWED" = "false" ]; then
    echo "❌ Budget exceeded at workflow $i"
    break
  fi
  
  curl -X POST http://localhost:8000/api/workflows \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Test workflow"}' \
    | jq '.workflow_id'
  
  sleep 1
done

# Expected: 20th workflow succeeds, 21st fails with "Budget exceeded"
```

---

## **Phase 6: Performance & Load Testing**

### **6.1 Load Testing with Apache Bench**

```bash
# Install ab
brew install httpd  # macOS
# or apt-get install apache2-utils  # Linux

# Test API under load
ab -n 1000 -c 10 http://localhost:8000/health
# n = requests, c = concurrent

# Expected:
# - Requests per second: > 100
# - Failed requests: 0
# - Avg response time: < 100ms
```

### **6.2 Load Testing with Locust**

```bash
pip install locust

# Create locustfile.py
cat > locustfile.py << 'EOF'
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def health_check(self):
        self.client.get("/health")
    
    @task
    def create_workflow(self):
        self.client.post("/api/workflows", json={
            "prompt": "Research and analyze"
        })
    
    @task
    def check_rate_limit(self):
        self.client.get("/api/rate-limiting/check/user1")
EOF

# Run load test
locust -f locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10

# Open http://localhost:8089 to view dashboard
```

### **6.3 Memory Usage**

```bash
# Monitor memory while running workflows
# Terminal 4:
watch -n 1 'ps aux | grep uvicorn | grep -v grep'

# Expected:
# - Initial: ~200MB
# - Under load: < 500MB (no memory leak)
```

---

## **Phase 7: Database & Vector Search Testing**

### **7.1 Test Vector Index**

```bash
# Connect to PostgreSQL
psql postgresql://postgres:postgres@localhost:5432/multi_agent_ai

# Check if pgvector installed
\dx vector

# Check vector index
SELECT indexname, indexdef FROM pg_indexes 
WHERE tablename='workflow_memories' AND indexname LIKE '%embedding%';

# Expected: Shows HNSW index on request_embedding

# Check existing memories
SELECT workflow_id, user_request, success 
FROM workflow_memories LIMIT 5;
```

### **7.2 Test Hybrid Search**

```bash
# Retrieve similar workflows (RPC call through API)
curl -X POST http://localhost:8000/api/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "research trends analysis",
    "top_k": 5,
    "min_similarity": 0.6,
    "filter_success_only": true
  }' | jq .

# Expected:
# - Returns 3-5 workflows
# - Each has score > 0.6
# - All have success=true
# - Sorted by relevance score
```

### **7.3 Test Cache (Redis)**

```bash
# Connect to Redis
redis-cli

# Check embeddings cache
KEYS "embedding:*"

# Check rate limit keys
KEYS "rate_limit:*"

# Check budget keys
KEYS "budget:*"

# Verify TTLs
TTL "embedding:some_hash"

# Expected:
# - Embedding cache TTL: 604800 (7 days)
# - Rate limit TTL: 60 (1 minute)
# - Budget TTL: time until next month
```

---

## **Phase 8: Observability Testing**

### **8.1 Test Langfuse Integration**

```bash
# If Langfuse keys configured, traces should appear in:
# https://cloud.langfuse.com/dashboard

# Check Langfuse status
curl http://localhost:8000/api/observability/langfuse/status

# Expected:
{
  "enabled": true,
  "connected": true,
  "traces_sent": 42
}

# Flush pending traces
curl -X POST http://localhost:8000/api/observability/langfuse/flush
```

### **8.2 Test Kafka Event Streaming**

```bash
# Monitor Kafka topics
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic multi_agent.agent.completed \
  --from-beginning

# Expected: See JSON events:
# {"workflow_id": "...", "agent_id": "...", "status": "completed"}

# Monitor multiple topics
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Should show:
# multi_agent.agent.started
# multi_agent.agent.completed
# multi_agent.agent.failed
# multi_agent.workflow.completed
```

### **8.3 Test Prometheus Metrics** *(optional)*

```bash
# If Prometheus configured:
curl http://localhost:9090/api/v1/query?query=http_requests_total

# Expected: Returns metric data
```

---

## **Phase 9: Error & Edge Case Testing**

### **9.1 Test Missing Environment Variables**

```bash
# Remove API key and test
unset OPENAI_API_KEY

# Try to create workflow
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# Expected: Graceful error (fallback or clear message)
```

### **9.2 Test Database Connection Failure**

```bash
# Stop PostgreSQL
docker-compose stop postgres

# Try API call
curl http://localhost:8000/health

# Expected: 
# {
#   "status": "degraded",
#   "services": {
#     "database": "unhealthy: connection refused"
#   }
# }

# Restart
docker-compose start postgres
```

### **9.3 Test Invalid Approval Request**

```bash
curl -X POST http://localhost:8000/api/approvals/invalid_id/approve

# Expected: 404 error with clear message
```

### **9.4 Test Malformed JSON**

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{invalid json}'

# Expected: 422 validation error
```

---

## **Phase 10: Security Testing**

### **10.1 Test Rate Limiting Enforcement**

```bash
# Exceeded rate limit should return 429
for i in {1..30}; do
  curl -s http://localhost:8000/api/rate-limiting/check/user \
    | jq '.allowed'
done

# Expected: Last 10 should return false
```

### **10.2 Test Budget Enforcement**

```bash
# Exceeded budget should block workflow creation
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"prompt": "expensive query"}' \
  -u user_over_budget

# Expected: 402 Payment Required or 429 Too Many Requests
```

### **10.3 Test Tool Permissions**

```bash
# Try to access tool not permitted for agent
curl -X GET http://localhost:8000/api/tools/permissions/research_agent

# Expected: Returns only permitted tools (no sensitive/production tools)
```

---

## **Testing Checklist**

```markdown
## Unit Tests ✓
- [ ] Memory embedding tests
- [ ] BM25 search tests
- [ ] Dense search tests
- [ ] Reranking logic tests
- [ ] Rate limiting algorithm tests
- [ ] Budget calculation tests

## Integration Tests ✓
- [ ] Full workflow execution
- [ ] Memory save and retrieve
- [ ] Supervisor planning with memory
- [ ] Orchestrator DAG execution
- [ ] Rate limiting enforcement
- [ ] Budget enforcement

## API Endpoint Tests ✓
- [ ] POST /api/workflows (create)
- [ ] GET /api/workflows/{id} (status)
- [ ] POST /api/approvals (create)
- [ ] POST /api/approvals/{id}/approve
- [ ] POST /api/approvals/{id}/reject
- [ ] GET /api/rate-limiting/check
- [ ] GET /api/rate-limiting/budget
- [ ] POST /api/memory/retrieve
- [ ] GET /api/observability/summary
- [ ] All other endpoints from API audit

## Dashboard Tests ✓
- [ ] Workflows page loads and displays data
- [ ] Metrics page shows summary cards
- [ ] Approvals page shows cards with correct colors
- [ ] Budget page shows progress bars
- [ ] All pages responsive (mobile/tablet/desktop)
- [ ] NO VIOLET COLORS anywhere

## E2E Tests ✓
- [ ] Complete workflow execution
- [ ] Approval flow (create → approve → execute)
- [ ] Rate limiting blocks excessive requests
- [ ] Budget enforcement prevents overspend
- [ ] Memory system learns from workflows
- [ ] Observability traces workflows

## Performance Tests ✓
- [ ] API responds in < 200ms
- [ ] Memory doesn't leak under load
- [ ] Vector search < 100ms
- [ ] Rate limiting < 10ms

## Error Handling ✓
- [ ] Missing environment variables handled
- [ ] Database connection failures handled
- [ ] Invalid input rejected properly
- [ ] Malformed JSON caught
- [ ] Rate limit exceeded returns 429
- [ ] Budget exceeded returns 402

## Security Tests ✓
- [ ] Rate limiting enforced
- [ ] Budget enforcement works
- [ ] Tool permissions checked
- [ ] Approval workflow required
```

---

## **Troubleshooting**

### **"Connection refused" errors**
```bash
# Check if services are running
docker-compose ps

# Restart services
docker-compose restart postgres redis kafka temporal

# Check logs
docker-compose logs postgres
```

### **"pgvector not installed"**
```bash
docker-compose exec postgres psql -U postgres -d multi_agent_ai \
  -c "CREATE EXTENSION IF NOT EXISTS vector"
```

### **"Temporal not responding"**
```bash
# Wait for Temporal to be ready
docker-compose logs temporal | grep "Started"

# Check UI
curl http://localhost:8080
```

### **Slow vector search**
```bash
# Ensure HNSW index exists
psql postgresql://postgres:postgres@localhost:5432/multi_agent_ai \
  -c "SELECT * FROM pg_indexes WHERE tablename='workflow_memories'"

# Recreate if missing
psql postgresql://postgres:postgres@localhost:5432/multi_agent_ai \
  -c "CREATE INDEX workflow_memories_embedding_idx ON workflow_memories \
      USING hnsw (request_embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
```

---

## **Running Tests in CI/CD**

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=src
      - run: npm ci && npm run build
```

---

**Testing is complete when:**
✅ All unit tests pass
✅ All integration tests pass
✅ All API endpoints respond correctly
✅ Dashboard pages render and function
✅ Complete E2E workflows execute successfully
✅ Rate limiting enforces limits
✅ Budget enforcement prevents overspend
✅ No memory leaks under load
✅ Vector search completes in <100ms
✅ All error cases handled gracefully
