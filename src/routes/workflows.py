from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
from temporalio.common import RetryPolicy

from src.infrastructure.temporal_client import get_temporal_client
from src.workflows.supervisor_workflow import SupervisorWorkflow, SupervisorWorkflowInput
from src.workflows.orchestrator_workflow import OrchestratorWorkflow, OrchestratorWorkflowInput
from src.config import settings
from src.llm.gateway import get_llm_gateway
from src.rate_limiting.rate_limiter import get_rate_limiter
from src.rate_limiting.budget_manager import get_budget_manager
from src.workflow_store import (
    create_workflow_record,
    get_workflow_record,
    get_workflow_thread,
    list_workflow_records,
    list_agent_runs,
)
import json as _json

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


class WorkflowCreateRequest(BaseModel):
    """Request to create a new workflow."""
    prompt: str
    context: Optional[Dict[str, Any]] = None
    user_id: str = "default_user"
    user_tier: str = "free"
    # HIG: pause after Supervisor planning until a human approves the plan
    require_approval: bool = False
    # Thread continuation: run this prompt as a follow-up that inherits the
    # parent workflow's final output as context
    parent_workflow_id: Optional[str] = None
    # Output token limiter: when set, caps max output tokens of every LLM
    # call in this workflow (clamped 100-4000)
    output_token_limit: Optional[int] = None
    # Enabled skills: restricts which agents the Supervisor may plan with.
    # None/empty = all skills available.
    enabled_skills: Optional[List[str]] = None


class WorkflowCreateResponse(BaseModel):
    """Response after creating a workflow."""
    workflow_id: str
    status: str
    message: str


class WorkflowStatusResponse(BaseModel):
    """Response with workflow status."""
    workflow_id: str
    status: str
    user_id: Optional[str] = None
    prompt: Optional[str] = None
    agents_selected: List[str] = []
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None
    execution_time_ms: Optional[int] = None
    quality_score: Optional[float] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


@router.post("/", response_model=WorkflowCreateResponse)
async def create_workflow(request: WorkflowCreateRequest) -> WorkflowCreateResponse:
    """
    Create and execute a new workflow.

    Flow:
    1. Create Supervisor workflow to generate task DAG
    2. Create Orchestrator workflow to execute DAG
    3. Return workflow ID to client

    Args:
        request: {prompt, context}

    Returns:
        Workflow ID for tracking
    """
    try:
        # Step 0: Enforce rate limit + budget before spending anything on this request
        rate_limiter = get_rate_limiter()
        allowed, rate_info = rate_limiter.check_rate_limit(request.user_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {rate_info.get('current')}/{rate_info.get('limit')} requests per minute",
            )

        budget_manager = get_budget_manager()
        budget_ok, budget_info = budget_manager.check_budget(
            request.user_id, requested_cost=0.0, user_tier=request.user_tier
        )
        if not budget_ok:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly budget exceeded: ${budget_info.get('used')}/${budget_info.get('monthly_budget')}",
            )

        workflow_id = str(uuid.uuid4())

        client = get_temporal_client()

        # Step 0.5: Follow-up threads — pull the parent's final output so
        # this run continues previous work instead of starting fresh
        initial_context: Optional[Dict[str, Any]] = None
        root_workflow_id: Optional[str] = None
        supervisor_context = dict(request.context or {})
        skill_instructions = None
        if request.enabled_skills:
            supervisor_context["enabled_skills"] = request.enabled_skills
            from src.skills.catalog import instructions_by_agent
            skill_instructions = instructions_by_agent(request.enabled_skills) or None
        output_token_limit = (
            max(100, min(request.output_token_limit, 4000))
            if request.output_token_limit
            else None
        )
        if request.parent_workflow_id:
            parent = await get_workflow_record(request.parent_workflow_id)
            if not parent:
                raise HTTPException(status_code=404, detail="Parent workflow not found")
            # Threads stay flat: always anchor to the root of the chain
            root_workflow_id = parent.get("parent_workflow_id") or parent["workflow_id"]

            parent_runs = await list_agent_runs(request.parent_workflow_id)
            last_output = next(
                (r.get("task_output") for r in reversed(parent_runs) if r.get("success") and r.get("task_output")),
                None,
            )
            previous_work: Dict[str, Any] = {}
            if last_output:
                try:
                    previous_work = _json.loads(last_output)
                except (TypeError, ValueError):
                    previous_work = {"content": str(last_output)}
            initial_context = {
                "previous_results": {"previous_work": previous_work},
                "follow_up": True,
            }
            supervisor_context["follow_up"] = True

        # Step 1: Execute Supervisor workflow to get task DAG
        supervisor_input = SupervisorWorkflowInput(
            workflow_id=workflow_id,
            user_prompt=request.prompt,
            context=supervisor_context,
        )

        supervisor_result = await client.execute_workflow(
            SupervisorWorkflow.execute,
            supervisor_input,
            id=f"supervisor-{workflow_id}",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            # Retries are handled inside run_supervisor_activity itself;
            # without this, Temporal's default workflow retry policy retries
            # the whole workflow (effectively unbounded) on top of that.
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        # Step 2: Persist the workflow record before dispatching execution
        await create_workflow_record(
            workflow_id=workflow_id,
            user_id=request.user_id,
            prompt=request.prompt,
            agents_selected=supervisor_result.agents_selected,
            parent_workflow_id=root_workflow_id,
        )

        # Step 3: Start the Orchestrator workflow WITHOUT waiting for it to
        # finish — this can run for minutes, and the HTTP caller (dashboard)
        # should get the workflow_id back immediately and poll for status.
        orchestrator_input = OrchestratorWorkflowInput(
            workflow_id=workflow_id,
            user_request=request.prompt,  # Original user request for memory
            tasks=supervisor_result.tasks,
            agents_selected=supervisor_result.agents_selected,  # Agents selected for memory
            user_id=request.user_id,  # For budget tracking
            require_approval=request.require_approval,  # HIG plan approval
            initial_context=initial_context,  # Follow-up thread inheritance
            output_token_limit=output_token_limit,  # User's output cap
            skill_instructions=skill_instructions,  # Enabled skill modules per agent
        )

        await client.start_workflow(
            OrchestratorWorkflow.execute,
            orchestrator_input,
            id=f"orchestrator-{workflow_id}",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            # Retries are handled per-task inside the orchestrator itself;
            # retrying the whole DAG here would silently redo already
            # completed (and paid for) tasks.
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        if request.require_approval:
            return WorkflowCreateResponse(
                workflow_id=workflow_id,
                status="waiting_approval",
                message=(
                    f"Plan created with {len(supervisor_result.tasks)} tasks — "
                    "waiting for approval before execution"
                ),
            )
        return WorkflowCreateResponse(
            workflow_id=workflow_id,
            status="running",
            message=f"Workflow started with {len(supervisor_result.tasks)} tasks",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """
    Get the status of a workflow.

    The workflows table (updated by the orchestrator's activities) is the
    source of truth here rather than querying Temporal directly, since it
    already carries cost/token/agent info the dashboard needs.

    Args:
        workflow_id: Workflow ID to check

    Returns:
        Workflow status and results
    """
    try:
        record = await get_workflow_record(workflow_id)
        if not record:
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status="not_found",
                error="Workflow not found",
            )
        return WorkflowStatusResponse(**record)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/stream", tags=["Workflows"])
async def stream_progress(workflow_id: str):
    """
    Server-Sent Events stream of live agent progress for a workflow.

    Sends the current progress snapshot (Redis hash) immediately so
    late-joining clients catch up, then forwards real-time events from the
    Redis pub/sub channel that agents publish to while they work.
    """
    from fastapi.responses import StreamingResponse
    import redis.asyncio as aioredis

    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"progress_channel:{workflow_id}")
        try:
            # Snapshot first — the browser may connect mid-run
            snapshot = await r.hgetall(f"progress:{workflow_id}")
            for data in snapshot.values():
                yield f"data: {data}\n\n"

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                if message and message.get("type") == "message":
                    yield f"data: {message['data']}\n\n"
                elif message is None:
                    # Keepalive comment so proxies don't kill the connection
                    yield ": keepalive\n\n"
        finally:
            await pubsub.close()
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{workflow_id}/thread", tags=["Workflows"])
async def get_thread(workflow_id: str) -> Dict[str, Any]:
    """
    The full conversation thread this workflow belongs to: the root run plus
    every follow-up, oldest first.
    """
    try:
        runs = await get_workflow_thread(workflow_id)
        return {"workflow_id": workflow_id, "thread": runs, "count": len(runs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/agents", tags=["Workflows"])
async def get_workflow_agents(workflow_id: str) -> Dict[str, Any]:
    """List each agent execution recorded for this workflow, in order."""
    try:
        runs = await list_agent_runs(workflow_id)
        return {"workflow_id": workflow_id, "agents": runs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", tags=["Workflows"])
async def list_workflows(limit: int = 50) -> Dict[str, Any]:
    """List recent workflows, most recent first."""
    try:
        records = await list_workflow_records(limit=limit)
        return {"workflows": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/summary", tags=["Costs"])
async def get_cost_summary() -> Dict[str, Any]:
    """
    Get overall cost summary for all workflows.

    Returns:
        Cost statistics including total cost, token usage, request count
    """
    llm_gateway = get_llm_gateway()
    summary = llm_gateway.get_cost_summary()
    return {
        "summary": summary,
        "message": "Cost tracking enabled via LLM Gateway",
    }


@router.get("/{workflow_id}/cost", tags=["Costs"])
async def get_workflow_cost(workflow_id: str) -> Dict[str, Any]:
    """
    Get cost for a specific workflow.

    Args:
        workflow_id: Workflow ID

    Returns:
        Total cost for the workflow
    """
    llm_gateway = get_llm_gateway()
    cost = llm_gateway.get_workflow_cost(workflow_id)
    return {
        "workflow_id": workflow_id,
        "total_cost": round(cost, 6),
        "currency": "USD",
    }
