# Step 6: Enhanced Tool Gateway

This step significantly expands the Tool Gateway with multiple tools, Role-Based Access Control (RBAC), and comprehensive metrics tracking.

## What's Implemented

### 1. New Tools (4 total)

#### Web Search (existing, enhanced)
- Search capability for information gathering
- Used by Research Agent
- Risk Level: LOW

#### Document Reader (new)
- Read and extract text from documents
- Supports: TXT, MD, JSON (extensible to PDF, DOCX)
- Safe content extraction
- Risk Level: LOW

#### Database Query (new)
- Execute SQL queries safely
- SELECT only (prevents data modification)
- Max 1000 row limit
- Timeout enforcement (30 sec)
- SQL injection prevention
- Risk Level: HIGH

#### Code Executor (new)
- Execute Python code in sandbox
- Blocks: imports, file I/O, network, exec/eval
- Timeout enforcement (10 sec)
- Output capture
- Risk Level: HIGH

### 2. Role-Based Access Control (RBAC)

Five agent roles with different permission levels:

```python
RESEARCHER
  └─ Can use: web_search, document_reader
  └─ Agent: research_agent

ANALYST
  └─ Can use: web_search, document_reader, database_query
  └─ Agent: analysis_agent

DEVELOPER
  └─ Can use: all tools (web_search, document_reader, database_query, code_executor)
  └─ Agent: (future coding agent)

WRITER
  └─ Can use: document_reader
  └─ Agent: writer_agent

SUPERVISOR
  └─ Can use: no tools
  └─ Agent: supervisor_agent
```

**How it Works:**
```python
# Mapping
Agent → Role → Allowed Tools

research_agent (RESEARCHER) → [web_search, document_reader]
analysis_agent (ANALYST) → [web_search, document_reader, database_query]
```

### 3. Tool Metrics & Monitoring

Tracks execution statistics:

```json
{
  "total_calls": 127,
  "successful_calls": 119,
  "failed_calls": 5,
  "permission_denied": 3,
  "by_tool": {
    "web_search": {
      "calls": 50,
      "success": 48,
      "failed": 2
    },
    "database_query": {
      "calls": 30,
      "success": 28,
      "failed": 2
    }
  },
  "by_agent": {
    "research_agent": {
      "calls": 55,
      "success": 54,
      "failed": 1
    },
    "analysis_agent": {
      "calls": 72,
      "success": 65,
      "failed": 4
    }
  }
}
```

### 4. Tool Safety Features

**Database Query Tool:**
- Only SELECT queries allowed (no INSERT, UPDATE, DELETE)
- No DROP, ALTER, TRUNCATE
- No SQL comments (prevents injection)
- Result limit: 1000 rows
- Timeout: 30 seconds

**Code Executor Tool:**
- Blocks dangerous imports (os, sys, socket, urllib)
- Blocks file I/O (open, read, write)
- Blocks exec/eval
- Blocks network access
- Timeout: 10 seconds
- Output capture and limiting

**Document Reader Tool:**
- No path traversal (later implementation)
- Safe file reading
- Format validation

## API Endpoints

### Tool Discovery
```bash
# List all tools
GET /api/tools

# Get specific tool metadata
GET /api/tools/{tool_id}

# List by category
GET /api/tools/by-category/{category}
# Categories: information, action, compute

# List by risk level
GET /api/tools/by-risk/{risk_level}
# Levels: low, medium, high, critical
```

### Permissions & Access
```bash
# Get tools allowed for agent
GET /api/tools/permissions/{agent_id}

# Example response:
{
  "agent_id": "analysis_agent",
  "allowed_tools": ["web_search", "document_reader", "database_query"],
  "tool_count": 3
}
```

### Metrics
```bash
# Get tool execution metrics
GET /api/tools/metrics/summary

# Response shows:
# - Total calls, success/failure rates
# - Per-tool statistics
# - Per-agent statistics
```

## Usage Examples

### Research Agent Using Web Search
```python
gateway = get_tool_gateway()

result = await gateway.execute_tool(
    agent_id="research_agent",
    tool_name="web_search",
    tool_input={"query": "AI trends 2024"}
)
# ✅ Allowed (RESEARCHER role has web_search)
```

### Analysis Agent Using Database
```python
result = await gateway.execute_tool(
    agent_id="analysis_agent",
    tool_name="database_query",
    tool_input={"query": "SELECT * FROM metrics LIMIT 10"}
)
# ✅ Allowed (ANALYST role has database_query)
```

### Writer Agent Attempting Database Access
```python
result = await gateway.execute_tool(
    agent_id="writer_agent",
    tool_name="database_query",
    tool_input={"query": "..."}
)
# ❌ Denied! (WRITER role only has document_reader)
# Raises: PermissionDeniedException
```

### Supervisor Attempting Any Tool
```python
result = await gateway.execute_tool(
    agent_id="supervisor_agent",
    tool_name="web_search",
    tool_input={"query": "..."}
)
# ❌ Denied! (SUPERVISOR has no tool access)
```

## Security Model

### Permission Layers
```
User Request
  ↓
Agent Identity
  ↓
Agent Role (RBAC)
  ↓
Tool Permission Check
  ↓
Input Validation
  ↓
Sandboxed Execution
  ↓
Audit Logging
```

### Audit Trail
Every tool call is logged:
- Agent ID
- Tool name
- Input parameters
- Execution status (success/failure)
- Timestamp
- Error details (if failed)

## Testing

### Unit Tests
```bash
pytest tests/unit/test_tool_gateway_enhanced.py -v
```

Tests cover:
- RBAC enforcement
- Tool registration
- Permission checks
- Metrics tracking
- Input validation
- Constraint enforcement

### Test Examples
```python
# Verify RBAC
def test_analyst_can_use_database():
    gateway = get_tool_gateway()
    allowed = gateway.list_allowed_tools("analysis_agent")
    assert "database_query" in allowed

# Verify metrics
def test_metrics_tracking():
    gateway = ToolGateway()
    gateway._record_metric("research_agent", "web_search", True)
    metrics = gateway.get_metrics()
    assert metrics["successful_calls"] == 1
```

## Configuration

### Adding New Roles
```python
# In src/tools/gateway.py
ROLE_PERMISSIONS[AgentRole.NEW_ROLE] = ["tool_1", "tool_2"]
AGENT_ROLES["new_agent"] = AgentRole.NEW_ROLE
```

### Adding New Tools
```python
# 1. Create tool class
class MyTool:
    TOOL_ID = "my_tool"
    async def execute(self, ...): ...
    def get_manifest(self): ...

# 2. Register in TOOL_REGISTRY
TOOL_REGISTRY["my_tool"] = MyTool()

# 3. Add to role permissions
ROLE_PERMISSIONS[AgentRole.DEVELOPER].append("my_tool")
```

## Next Steps

**Step 7**: Human Interaction Gateway (HIG)
- Approval workflow for sensitive actions
- Temporal signals for workflow pause/resume
- Approval request API

**Step 8**: Multi-Agent Orchestration + Kafka
- Analysis Agent
- Writer Agent
- Event publishing to Kafka

**Step 9.5**: RAG/Memory (inserted)
- Vector database integration
- Knowledge retrieval layer
- Agent memory & learning

## Monitoring & Debugging

### Check Tool Health
```bash
curl http://localhost:8000/api/tools
```

### Monitor Permissions
```bash
# See what research_agent can do
curl http://localhost:8000/api/tools/permissions/research_agent
```

### View Metrics
```bash
curl http://localhost:8000/api/tools/metrics/summary
```

### Categorize Tools
```bash
# Find all high-risk tools
curl http://localhost:8000/api/tools/by-risk/high
```

---

**Step 6 Complete!** Tool Gateway now has multiple tools, RBAC, and full metrics.

Next: Step 7 - Human-in-the-Loop Approval Workflow.
