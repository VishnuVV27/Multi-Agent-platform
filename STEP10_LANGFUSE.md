# Step 10: Langfuse Integration - LLM Observability & Evaluation

Production-grade observability for LLM calls, workflow execution, and agent performance.

## 🎯 What's Implemented

### **1. Langfuse Cloud Integration**

**What gets traced:**
```json
{
  "workflow_id": "wf_123",
  "agent_id": "research_agent",
  "model": "claude-3.5-sonnet",
  "prompt_version": "2.0",
  "input_tokens": 1200,
  "output_tokens": 800,
  "total_tokens": 2000,
  "cost": "$0.032",
  "latency_ms": 2500,
  "status": "completed"
}
```

### **2. Trace Hierarchy**

```
Workflow Trace
├── Agent 1 Span
│   ├── LLM Call (with tokens, cost, latency)
│   ├── Tool Call (web_search, database_query, etc)
│   └── Status (success/failure)
├── Agent 2 Span
│   ├── LLM Call
│   └── Status
└── Agent 3 Span
    ├── LLM Call
    └── Status
```

### **3. LLM Call Tracing**

**Every LLM call includes:**
- Model name (claude-3.5-sonnet, gpt-4, etc)
- Input/output tokens
- Cost calculation
- Latency
- Prompt version (for A/B testing)
- Agent context
- Workflow correlation ID

### **4. Workflow Execution Tracing**

**Trace structure:**
```
workflow:execution
├─ workflow_id
├─ user_request
├─ agents: [research_agent, analysis_agent, writer_agent]
├─ duration_ms: 12500
├─ total_cost: $0.12
├─ total_tokens: 5600
├─ success: true
└─ timestamp
```

### **5. Evaluation Metrics**

**Tracked automatically:**
- **Success rate** per agent (% workflows completed)
- **Cost trends** over time
- **Latency** per agent
- **Token usage** per model
- **Cost per workflow**
- **Prompt version performance** (v1 vs v2 comparison)

---

## 🔧 Components Built

### **LangfuseClient** (`src/observability/langfuse_client.py`)

```python
class LangfuseClient:
    async def trace_llm_call(
        workflow_id, agent_id, model, 
        prompt, output, input_tokens, output_tokens,
        cost, latency_ms, prompt_version
    )
    
    async def trace_workflow(
        workflow_id, user_request, agents,
        duration_ms, cost, tokens, success
    )
    
    async def trace_agent_execution(
        workflow_id, agent_id, task_input, task_output,
        duration_ms, success
    )
```

### **WorkflowTracer** (`src/observability/workflow_tracer.py`)

```python
class WorkflowTracer:
    start_workflow_trace()
    end_workflow_trace()
    trace_agent()
    trace_tool_call()
    flush()
```

### **EvaluationService** (`src/observability/evaluation_service.py`)

```python
class EvaluationService:
    get_workflow_metrics()         # Single workflow metrics
    get_agent_success_rate()       # Agent success rate over time
    get_cost_metrics()             # Platform-wide costs
    get_latency_metrics()          # Latency per agent
    compare_prompt_versions()      # A/B test prompts
    get_summary()                  # Overall platform health
```

### **Observability API** (`src/routes/observability.py`)

- `GET /api/observability/summary` - Overall system health
- `GET /api/observability/metrics/costs` - Cost breakdown
- `GET /api/observability/metrics/latency` - Latency by agent
- `GET /api/observability/metrics/agents/{id}` - Agent-specific metrics
- `GET /api/observability/prompts/compare` - Compare prompt versions
- `GET /api/observability/langfuse/status` - Langfuse connection status
- `POST /api/observability/langfuse/flush` - Manually flush traces

---

## 🔌 Integration Points

### **1. LLM Gateway (Automatic Tracing)**

```python
# In src/llm/gateway.py chat() method:
response = await acompletion(...)

# Automatically traces:
langfuse.trace_llm_call(
    workflow_id, agent_id, model,
    prompt, output, input_tokens, output_tokens,
    cost, latency_ms
)
```

### **2. Workflow Execution (Trace Hierarchy)**

```python
# In orchestrator_workflow.py:

# Start workflow trace
tracer.start_workflow_trace(workflow_id, user_request, agents)

# For each agent execution:
tracer.trace_agent(
    workflow_id, agent_id, task_input, task_output,
    duration_ms, cost, tokens, success
)

# End workflow trace
tracer.end_workflow_trace(
    workflow_id, duration_ms, cost, tokens, success
)
```

---

## 📊 What You Can Do with Langfuse

### **1. View Traces in Langfuse Dashboard**
- Click through each workflow trace
- See LLM calls with tokens, cost, latency
- Drill down into agent executions
- Review prompts and outputs

### **2. A/B Test Prompts**
```
Compare supervisor v1.0 vs v2.0:
- v1.0: 82% planning accuracy, $0.052 avg cost
- v2.0: 91% planning accuracy, $0.048 avg cost
→ Upgrade to v2.0 (+11% accuracy, -8% cost)
```

### **3. Monitor Costs**
- Total cost over time
- Cost per model
- Cost per agent
- Identify expensive workflows

### **4. Performance Analysis**
- Latency per agent
- Success rates
- Error patterns
- Workflow execution timeline

### **5. Debugging**
- Trace any failed workflow
- See exact LLM inputs/outputs
- Review tool call results
- Identify bottlenecks

---

## ⚙️ Setup

### **1. Create Langfuse Account**

```bash
# Go to https://cloud.langfuse.com
# Sign up → Create organization
# Get: Public Key & Secret Key
```

### **2. Set Environment Variables**

```bash
# In .env or docker-compose.yml:
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
LANGFUSE_HOST=https://cloud.langfuse.com
ENABLE_LANGFUSE_TRACING=true
```

### **3. LLM Calls Auto-Trace**

✅ Automatic - no code changes needed!
- Every `llm_gateway.chat()` call is traced
- Every `llm_gateway.generate()` call is traced
- Tokens, cost, latency included automatically

### **4. Workflow Tracing (Optional)**

For detailed workflow visualization:

```python
from src.observability.workflow_tracer import WorkflowTracer

tracer = WorkflowTracer()

# Trace workflow execution
tracer.start_workflow_trace(workflow_id, user_request, agents)
# ... execute agents ...
tracer.end_workflow_trace(workflow_id, duration_ms, cost, tokens, success)
```

---

## 📈 Metrics Available

**Via `/api/observability/`:**

```json
{
  "summary": {
    "total_cost": "$45.23",
    "total_tokens": 125600,
    "request_count": 342,
    "agents_monitored": 4
  },
  "costs": {
    "total_cost": "$45.23",
    "cost_by_model": {
      "claude-3.5-sonnet": "$32.15",
      "gpt-4": "$13.08"
    }
  },
  "latency": {
    "research_agent": {
      "avg_latency_ms": 8500,
      "min_latency_ms": 2000,
      "max_latency_ms": 15000
    },
    "analysis_agent": {
      "avg_latency_ms": 6200
    }
  },
  "agents": {
    "research_agent": {
      "total_runs": 125,
      "successful_runs": 123,
      "success_rate": 0.984
    }
  }
}
```

---

## 🎯 What's Traced at Langfuse

**LLM Calls:**
- ✅ Model name
- ✅ Input/output tokens
- ✅ Cost
- ✅ Latency
- ✅ Prompt text
- ✅ Generated output
- ✅ Prompt version
- ✅ Workflow context

**Workflow Executions:**
- ✅ User request
- ✅ Agents used
- ✅ Total duration
- ✅ Total cost
- ✅ Total tokens
- ✅ Success/failure status
- ✅ Execution timeline

**Agent Runs:**
- ✅ Agent ID
- ✅ Task input
- ✅ Task output
- ✅ Duration
- ✅ Success status
- ✅ Cost per agent
- ✅ Tokens per agent

---

## 🔍 Example Traces

### **Trace 1: Successful Workflow**

```
workflow:execution (id: wf_abc123)
├── user_request: "Research AI trends and write report"
├── agents: [research_agent, writer_agent]
├── duration_ms: 12500
├── cost: $0.12
├── success: true
└── Spans:
    ├── agent:research_agent
    │   ├── duration_ms: 8000
    │   ├── cost: $0.08
    │   ├── tokens: 3600
    │   └── LLM calls:
    │       ├── llm_generation:claude-3.5-sonnet
    │       │   ├── input_tokens: 1200
    │       │   ├── output_tokens: 800
    │       │   ├── cost: $0.032
    │       │   ├── latency_ms: 2500
    │       └── tool:web_search
    │           ├── duration_ms: 4000
    │
    └── agent:writer_agent
        ├── duration_ms: 4500
        ├── cost: $0.04
        ├── tokens: 2000
        └── LLM calls:
            └── llm_generation:claude-3.5-sonnet
                ├── input_tokens: 2800
                ├── output_tokens: 1200
                ├── cost: $0.04
```

### **Trace 2: Failed Workflow**

```
workflow:execution (id: wf_xyz789)
├── user_request: "Deploy to production"
├── agents: [deployment_agent]
├── duration_ms: 3000
├── cost: $0.015
├── success: false
├── error: "Approval required"
└── Spans:
    └── agent:deployment_agent
        ├── duration_ms: 3000
        ├── cost: $0.015
        ├── success: false
        ├── error_message: "Deployment blocked by approval_agent"
        └── LLM calls:
            └── llm_generation:claude-3.5-sonnet
                ├── error: "Timeout waiting for approval"
```

---

## 📊 Dashboard in Langfuse

**You'll see:**
1. **Traces table** - Every workflow, sortable by cost/latency/success
2. **Trace details** - Click any workflow to drill down
3. **LLM calls** - Every model call with tokens/cost
4. **Cost breakdown** - Cost by model, agent, agent combo
5. **Performance chart** - Latency trends over time
6. **Success rates** - By agent, by agent combo
7. **Token usage** - By model, total per workflow

---

## 🚀 Next: Use Cases

**Now that you're tracing everything:**

1. **Identify bottlenecks** - Which agent is slowest?
2. **Optimize costs** - Which prompts waste tokens?
3. **Test prompts** - Compare v1 vs v2 with real data
4. **Monitor health** - Success rates over time
5. **Debug failures** - Review exact LLM inputs/outputs
6. **Track improvements** - See if memory RAG actually helps

---

## ✅ Implementation Status

**LLM Tracing:**
- ✅ LangfuseClient built
- ✅ Auto-traces all LLM calls (via gateway)
- ✅ Includes tokens, cost, latency, model

**Workflow Tracing:**
- ✅ WorkflowTracer built
- ✅ Traces agent executions
- ✅ Traces tool calls (optional)

**Metrics & Evaluation:**
- ✅ EvaluationService built
- ✅ Cost metrics API
- ✅ Latency metrics API
- ✅ Agent success rates
- ✅ Prompt comparison endpoint

**Configuration:**
- ✅ Langfuse settings in config.py
- ✅ Enable/disable via ENABLE_LANGFUSE_TRACING flag
- ✅ Cloud endpoint configurable

**API Endpoints:**
- ✅ 7 observability endpoints
- ✅ Metrics aggregation
- ✅ Langfuse status check
- ✅ Manual flush control

---

**Step 10 Complete!** All LLM calls now traced to Langfuse Cloud with full evaluation metrics.

Next: Step 11 (Rate Limiting & Budget Control)
