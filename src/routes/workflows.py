from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid

from src.infrastructure.temporal_client import get_temporal_client
from src.workflows.supervisor_workflow import SupervisorWorkflow, SupervisorWorkflowInput
from src.workflows.orchestrator_workflow import OrchestratorWorkflow, OrchestratorWorkflowInput
from src.config import settings
from src.llm.gateway import get_llm_gateway

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


class WorkflowCreateRequest(BaseModel):
    """Request to create a new workflow."""
    prompt: str
    context: Optional[Dict[str, Any]] = None


class WorkflowCreateResponse(BaseModel):
    """Response after creating a workflow."""
    workflow_id: str
    status: str
    message: str


class WorkflowStatusResponse(BaseModel):
    """Response with workflow status."""
    workflow_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
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
        workflow_id = str(uuid.uuid4())

        client = get_temporal_client()

        # Step 1: Execute Supervisor workflow to get task DAG
        supervisor_input = SupervisorWorkflowInput(
            workflow_id=workflow_id,
            user_prompt=request.prompt,
            context=request.context or {},
        )

        supervisor_result = await client.execute_workflow(
            SupervisorWorkflow.execute,
            supervisor_input,
            id=f"supervisor-{workflow_id}",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        # Step 2: Execute Orchestrator workflow with task DAG
        # Extract agents selected from supervisor result
        agents_selected = supervisor_result.agents_selected if hasattr(supervisor_result, 'agents_selected') else []

        orchestrator_input = OrchestratorWorkflowInput(
            workflow_id=workflow_id,
            user_request=request.prompt,  # Original user request for memory
            tasks=supervisor_result.tasks,
            agents_selected=agents_selected,  # Agents selected for memory
        )

        # Start orchestrator (don't wait for completion yet)
        await client.execute_workflow(
            OrchestratorWorkflow.execute,
            orchestrator_input,
            id=f"orchestrator-{workflow_id}",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        return WorkflowCreateResponse(
            workflow_id=workflow_id,
            status="executing",
            message=f"Workflow started with {len(supervisor_result.tasks)} tasks",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """
    Get the status of a workflow.

    Args:
        workflow_id: Workflow ID to check

    Returns:
        Workflow status and results
    """
    try:
        client = get_temporal_client()

        # Get workflow execution
        try:
            execution = await client.get_workflow_handle(f"orchestrator-{workflow_id}").describe()

            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status=execution.status.name.lower(),
                result=execution.return_value if execution.status.value == 1 else None,
            )
        except Exception:
            # Workflow not found
            return WorkflowStatusResponse(
                workflow_id=workflow_id,
                status="not_found",
                error="Workflow not found",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", tags=["Workflows"])
async def list_workflows() -> Dict[str, Any]:
    """
    List recent workflows (placeholder for MVP).

    Later: Query from database for persistence.
    """
    return {
        "message": "Workflow listing not yet implemented",
        "note": "This will query from PostgreSQL once workflow storage is added",
    }


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
