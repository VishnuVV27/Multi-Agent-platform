# Step 7: Human-in-the-Loop Approval Workflow

This step implements the complete approval system allowing agents to request human approval before executing sensitive actions.

## What's Implemented

### 1. Approval Request Model

Database model for persistent approval tracking:

```python
class ApprovalRequest:
    id: UUID
    workflow_id: str
    task_id: str
    agent_id: str
    
    # What needs approval
    action: str  # database_write, production_deploy, send_email
    description: str
    risk_level: ApprovalRisk  # low, medium, high, critical
    
    # Approval details
    status: ApprovalStatus  # pending, approved, rejected, expired
    approved_by: str
    approved_at: datetime
    rejection_reason: str
    
    # Lifecycle
    created_at: datetime
    expires_at: datetime
    context: Dict  # Full context for approver
```

### 2. Approval Policy Engine

Risk-based routing for automatic approval assignment:

```python
POLICIES = {
    "database_write": {
        "risk_level": HIGH,
        "required_approvers": 1,
        "timeout_minutes": 60,
    },
    "production_deploy": {
        "risk_level": CRITICAL,
        "required_approvers": 2,
        "timeout_minutes": 120,
    },
    "send_email": {
        "risk_level": MEDIUM,
        "required_approvers": 1,
        "timeout_minutes": 30,
    },
}
```

Actions automatically routed based on risk level and required approver count.

### 3. Approval Service

Business logic for managing approvals:

```python
class ApprovalService:
    - create_approval_request()    # Agent requests approval
    - get_approval()               # Retrieve approval details
    - approve()                    # Human approves
    - reject()                     # Human rejects
    - list_pending()               # Show pending approvals
    - get_statistics()             # Approval workflow stats
```

### 4. Temporal Approval Workflow

Temporal workflow that pauses waiting for approval:

```
1. Agent executes task that requires approval
2. Workflow calls create_approval_activity
3. Workflow pauses at wait_condition (blocking)
4. Human approves/rejects via API
5. Workflow receives approval_signal
6. Workflow resumes and either continues or fails
```

### 5. FastAPI Approval Endpoints

```bash
# Create approval request
POST /api/approvals
{
    "workflow_id": "wf_123",
    "task_id": "t_1",
    "agent_id": "database_agent",
    "action": "database_write",
    "description": "Migrate user data",
    "risk_level": "high",
    "context": {...}
}
Response: {approval_id, status, expires_at, ...}

# Get approval status
GET /api/approvals/{approval_id}
Response: {status, approved, approved_by, ...}

# Approve request
POST /api/approvals/{approval_id}/approve
{
    "approved_by": "user_123",
    "comments": "Looks good"
}
Response: {status: "approved", message: "..."}

# Reject request
POST /api/approvals/{approval_id}/reject
{
    "rejected_by": "user_456",
    "reason": "Wait for next release cycle"
}
Response: {status: "rejected", reason: "..."}

# List pending approvals
GET /api/approvals
Response: {total, pending, approved, rejected, requests: [...]}

# Get statistics
GET /api/approvals/statistics/
Response: {total_approvals, pending, approved, rejected, expired}
```

## Workflow Integration

### Example: Database Agent with Approval

```python
# In Database Agent execute() method

# Step 1: Prepare database write
query = "UPDATE users SET status = 'active' WHERE id > 1000"

# Step 2: Request approval (creates approval request + waits)
approval_workflow_handle = await temporal_client.execute_workflow(
    ApprovalWorkflow.execute,
    ApprovalWorkflowInput(
        workflow_id=task_input.workflow_id,
        task_id=task_input.task_id,
        agent_id="database_agent",
        action="database_write",
        description=f"Execute: {query}",
        context={"rows_affected": 500, "table": "users"}
    )
)

# Step 3: Workflow pauses here, waiting for approval signal

# Step 4: Human approves via API:
# POST /api/approvals/{approval_id}/approve

# Step 5: Workflow receives signal and resumes
approval_result = await approval_workflow_handle.result()

if approval_result.approved:
    # Execute the database write
    result = await database_executor.execute(query)
    return TaskOutput(status=COMPLETED, result={"rows": result})
else:
    # Write was rejected
    return TaskOutput(
        status=FAILED,
        error={
            "type": "ApprovalRejected",
            "message": approval_result.rejection_reason
        }
    )
```

## Risk-Based Routing

```
Action Type          Risk Level   Required Approvers   Timeout
────────────────────────────────────────────────────────────────
send_email           MEDIUM       1                    30 min
data_access          HIGH         1                    60 min
database_write       HIGH         1                    60 min
code_execution       CRITICAL     2                    120 min
production_deploy    CRITICAL     2                    120 min
```

## Approval Lifecycle

```
┌─────────────────────────────────────────────────────┐
│ 1. PENDING                                          │
│    - Approval request created                       │
│    - Waiting for human action                       │
│    - Expires after timeout                          │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   ┌─────────────┐   ┌─────────────┐
   │  APPROVED   │   │  REJECTED   │
   │  - Approved │   │  - Reason   │
   │  - By User  │   │  - By User  │
   │  - Timestamp│   │  - Timestamp│
   └─────────────┘   └─────────────┘
        │                 │
        └─────────┬───────┘
                  │
        ┌─────────▼────────┐
        │  Workflow Signal  │
        │  (Resume/Fail)    │
        └───────────────────┘
```

## Testing

### Unit Tests
```bash
pytest tests/unit/test_approval_service.py -v
```

Tests cover:
- Policy engine routing
- Approval creation
- Approval/rejection
- Lifecycle transitions
- Error handling (double-approve, double-reject)
- Context passing

### Example Test
```python
@pytest.mark.asyncio
async def test_approve_database_write():
    service = ApprovalService()
    
    # Create approval
    approval = await service.create_approval_request(
        workflow_id="wf_1",
        agent_id="db_agent",
        action="database_write",
    )
    
    # Verify it's pending
    assert approval["status"] == "pending"
    
    # Approve it
    approved = await service.approve(
        approval_id=approval["approval_id"],
        approved_by="user_123"
    )
    
    # Verify it's approved
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "user_123"
```

## Configuration

### Adding New Actions

```python
# In src/approval/service.py
POLICIES = {
    ...existing...
    
    "custom_action": {
        "risk_level": ApprovalRisk.HIGH,
        "required_approvers": 1,
        "timeout_minutes": 90,
    }
}
```

### Changing Risk Levels

```python
# Modify existing policy
POLICIES["send_email"]["risk_level"] = ApprovalRisk.HIGH
POLICIES["send_email"]["required_approvers"] = 2
```

## Monitoring & Debugging

### Check Pending Approvals
```bash
curl http://localhost:8000/api/approvals
```

### Get Specific Approval
```bash
curl http://localhost:8000/api/approvals/{approval_id}
```

### View Statistics
```bash
curl http://localhost:8000/api/approvals/statistics/
```

### Approve via API
```bash
curl -X POST http://localhost:8000/api/approvals/{approval_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "user_123", "comments": "Approved"}'
```

### Reject via API
```bash
curl -X POST http://localhost:8000/api/approvals/{approval_id}/reject \
  -H "Content-Type: application/json" \
  -d '{"rejected_by": "user_456", "reason": "Not ready yet"}'
```

## Next Steps

**Step 8**: Multi-Agent Orchestration + Kafka
- Analysis Agent (uses approval for database reads)
- Writer Agent (uses approval for content generation)
- Event publishing to Kafka

**Step 9**: LLM-Powered Supervisor
- Dynamic DAG generation with approval requirements
- Risk assessment before approval

**Step 9.5**: RAG/Memory (inserted)
- Learn from past approvals
- Suggest approvers based on history

---

**Step 7 Complete!** Agents can now request human approval for sensitive actions.

Workflows pause safely, humans approve/reject via API, and workflows resume intelligently.
