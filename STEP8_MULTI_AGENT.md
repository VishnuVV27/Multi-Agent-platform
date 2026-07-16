# Step 8: Multi-Agent Orchestration + Kafka

This step adds two new agents (Analysis, Writer) and enables real Kafka event streaming for observability across all agents.

## What's Implemented

### 1. Analysis Agent

Analyzes data and generates insights:

```python
class AnalysisAgent:
    - Queries databases using Tool Gateway
    - Uses LLM to analyze data patterns
    - Generates insights and recommendations
    
    Tools: database_query, web_search
    Capabilities: data_analysis, web_search, document_analysis
```

**Example flow:**
```
Input: "Analyze user engagement metrics"
  ↓
Generates/receives SQL query
  ↓
Executes via database_query tool
  ↓
LLM analyzes results
  ↓
Output: Insights + recommendations
```

### 2. Writer Agent

Generates professional written content:

```python
class WriterAgent:
    - Takes research/analysis as input
    - Generates professional reports
    - Supports multiple formats (report, summary, documentation)
    
    Capabilities: writing
```

**Example flow:**
```
Input: "Write a comprehensive report on market trends"
  ↓
Receives research/analysis context
  ↓
LLM generates structured content
  ↓
Extracts sections from generated content
  ↓
Output: Professional report with sections
```

### 3. Expanded Supervisor Rules

Supervisor now generates multi-agent DAGs:

```python
KEYWORD_RULES = {
    "research and analyze": ["research_agent", "analysis_agent"],
    "research analyze and write": ["research_agent", "analysis_agent", "writer_agent"],
    "analyze and write": ["analysis_agent", "writer_agent"],
    ...
}
```

**Example DAG generation:**

```
User: "Research competitors and write a detailed report"
  ↓
Supervisor matches keywords
  ↓
Generates DAG:
  t1: research_agent (depends_on: [])
  t2: writer_agent (depends_on: [t1])
  ↓
Returns to Orchestrator for execution
```

### 4. Temporal Workflows for New Agents

**AnalysisWorkflow:**
```python
@workflow.defn
class AnalysisWorkflow:
    @workflow.run
    async def execute(input_data):
        output = await workflow.execute_activity(run_analysis_activity, input_data)
        return output
```

**WriterWorkflow:**
```python
@workflow.defn
class WriterWorkflow:
    @workflow.run
    async def execute(input_data):
        output = await workflow.execute_activity(run_writer_activity, input_data)
        return output
```

### 5. Orchestrator Enhancements

Orchestrator now dispatches to all agent types:

```python
async def _execute_agent_workflow(agent_id, ...):
    if agent_id == "research_agent":
        return await execute_child_workflow(ResearchWorkflow, ...)
    elif agent_id == "analysis_agent":
        return await execute_child_workflow(AnalysisWorkflow, ...)
    elif agent_id == "writer_agent":
        return await execute_child_workflow(WriterWorkflow, ...)
```

### 6. Kafka Event Consumer

Listens to agent events for observability:

```python
class EventConsumer:
    - Subscribes to Kafka topics
    - Handles agent lifecycle events
    - Buffers events for retrieval
    - Provides filtering and search
    
    Events:
    - agent.started
    - agent.completed
    - agent.failed
    - agent.progress
```

## Multi-Agent Workflows

### Workflow 1: Research + Write
```
User: "Research AI trends and write a report"
  ↓
Supervisor: ["research_agent", "writer_agent"]
  ↓
Temporal:
  Task 1: research_agent
    ├─ Search web
    ├─ Aggregate findings
    └─ Return summary
  ↓ (T1 complete)
  Task 2: writer_agent
    ├─ Receive research findings
    ├─ Generate report
    └─ Return formatted content
  ↓
User: Professional report with research + writing
```

### Workflow 2: Research + Analyze + Write
```
User: "Research competitors, analyze data, write a comprehensive report"
  ↓
Supervisor: ["research_agent", "analysis_agent", "writer_agent"]
  ↓
Temporal:
  Task 1: research_agent (find competitor info)
  Task 2: analysis_agent (query DB, analyze metrics)
  Task 3: writer_agent (combine all, write report)
  ↓
User: Comprehensive analysis report
```

### Workflow 3: Analyze + Write
```
User: "Analyze user engagement and write a summary"
  ↓
Supervisor: ["analysis_agent", "writer_agent"]
  ↓
Temporal:
  Task 1: analysis_agent (query DB, analyze trends)
  Task 2: writer_agent (write summary with analysis)
  ↓
User: Engagement summary report
```

## Event Flow

```
Agent 1: research_agent
  └─ publishes: agent.started
  └─ publishes: agent.completed
      ↓
    Kafka Topic: multi_agent.agent.started
                 multi_agent.agent.completed
      ↓
    EventConsumer
      ├─ stores event
      ├─ calls handler
      └─ makes available via API
```

## Testing

### Unit Tests
```bash
pytest tests/integration/test_multi_agent_workflow.py -v
```

Tests cover:
- Multi-agent DAG generation
- Supervisor rule matching
- Agent initialization
- DAG dependency ordering
- Manifest validation

### Example Test
```python
async def test_research_analyze_write_workflow():
    supervisor = SupervisorAgent()
    task = TaskInput(
        workflow_id="wf_1",
        instruction="Research trends, analyze data, write report"
    )
    
    output = await supervisor.execute(task)
    tasks = output.result["tasks"]
    
    assert tasks[0]["agent"] == "research_agent"
    assert tasks[1]["agent"] == "analysis_agent"
    assert tasks[2]["agent"] == "writer_agent"
```

## API Usage

### Trigger Multi-Agent Workflow
```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Research AI trends and write a comprehensive report"
  }'

Response:
{
  "workflow_id": "wf_123",
  "status": "executing",
  "message": "Workflow started with 3 tasks"
}
```

### Monitor Agent Events
```bash
# Get workflow status
curl http://localhost:8000/api/workflows/{workflow_id}

# Check cost as agents execute
curl http://localhost:8000/api/workflows/{workflow_id}/cost
```

## Agent Capabilities & Tools

### Research Agent
```
Capabilities: web_search, document_analysis
Tools: web_search
Role: RESEARCHER
Output: Aggregated findings + summary
```

### Analysis Agent
```
Capabilities: data_analysis, web_search, document_analysis
Tools: database_query, web_search
Role: ANALYST
Output: Data insights + patterns + recommendations
```

### Writer Agent
```
Capabilities: writing
Tools: document_reader
Role: WRITER
Output: Formatted report / documentation
```

## Context Passing

Agents receive context from previous tasks:

```python
# Task 1: Research Agent
research_output = {
    "query": "AI trends",
    "findings": [...],
    "summary": "..."
}

# Task 2: Analysis Agent
task_input.context["research_findings"] = research_output["summary"]

# Task 3: Writer Agent
task_input.context["research_findings"] = ...
task_input.context["analysis_insights"] = ...
```

## Monitoring Multi-Agent Workflows

### Dashboard Metrics
- Total tasks in workflow
- Completed tasks
- Current executing agent
- Task duration
- Agent success rate

### Event Monitoring
- agent.started → Agent execution started
- agent.progress → Task progress (%)
- agent.completed → Task finished
- agent.failed → Task failed

## Next Steps

**Step 9**: LLM-Powered Supervisor
- Replace hardcoded rules with LLM planning
- Dynamic DAG generation based on request semantics
- Cost optimization (choose agents based on task)

**Step 9.5**: RAG/Memory (inserted)
- Learn from past workflows
- Suggest optimal agent combinations
- Cache successful patterns

**Step 10**: Langfuse Integration
- Full tracing of multi-agent execution
- Cost tracking per agent
- Performance analysis

---

**Step 8 Complete!** Multi-agent workflows with Kafka observability.

Platform now supports:
✓ 3 AI agents (Research, Analysis, Writer)
✓ Dynamic DAG generation (Supervisor)
✓ Sequential + parallel task execution (Temporal)
✓ Context passing between agents
✓ Kafka event observability
✓ Multi-step workflows (research → analyze → write)
