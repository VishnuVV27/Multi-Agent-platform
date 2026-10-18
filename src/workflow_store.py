"""
Workflow Store: Lightweight persistence for workflow execution records.

Used by the API layer (create/list/get) and by the orchestrator's Temporal
activity (to mark a workflow completed/failed once execution finishes).
Temporal remains the source of truth for live execution; this table exists
so the dashboard can list/query workflow history without talking to Temporal.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.infrastructure.database import get_db
from src.models.workflow import WorkflowORM


def _to_dict(row: WorkflowORM) -> Dict[str, Any]:
    return {
        "workflow_id": row.workflow_id,
        "user_id": row.user_id,
        "parent_workflow_id": row.parent_workflow_id,
        "prompt": row.prompt,
        "status": row.status,
        "agents_selected": row.agents_selected or [],
        "total_cost": row.total_cost,
        "total_tokens": row.total_tokens,
        "execution_time_ms": row.execution_time_ms,
        "error_message": row.error_message,
        "quality_score": row.quality_score,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def create_workflow_record(
    workflow_id: str,
    user_id: str,
    prompt: str,
    agents_selected: List[str],
    parent_workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a new workflow row with status=running."""
    loop = asyncio.get_event_loop()
    row = await loop.run_in_executor(
        None, _create_sync, workflow_id, user_id, prompt, agents_selected,
        parent_workflow_id,
    )
    return _to_dict(row)


def _create_sync(workflow_id, user_id, prompt, agents_selected, parent_workflow_id) -> WorkflowORM:
    db = get_db()
    try:
        row = WorkflowORM(
            id=uuid4(),
            workflow_id=workflow_id,
            user_id=user_id,
            parent_workflow_id=parent_workflow_id,
            prompt=prompt,
            status="running",
            agents_selected=agents_selected or [],
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


async def get_workflow_thread(workflow_id: str) -> List[Dict[str, Any]]:
    """
    Return the full conversation thread this workflow belongs to, oldest
    first: the root workflow plus every follow-up that points at that root.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_thread_sync, workflow_id)


def _get_thread_sync(workflow_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    try:
        row = db.query(WorkflowORM).filter(WorkflowORM.workflow_id == workflow_id).first()
        if not row:
            return []
        root_id = row.parent_workflow_id or row.workflow_id
        rows = (
            db.query(WorkflowORM)
            .filter(
                (WorkflowORM.workflow_id == root_id)
                | (WorkflowORM.parent_workflow_id == root_id)
            )
            .order_by(WorkflowORM.created_at.asc())
            .all()
        )
        return [_to_dict(r) for r in rows]
    finally:
        db.close()


async def get_workflow_record(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Look up a single workflow by its workflow_id."""
    loop = asyncio.get_event_loop()
    row = await loop.run_in_executor(None, _get_sync, workflow_id)
    return _to_dict(row) if row else None


def _get_sync(workflow_id: str) -> Optional[WorkflowORM]:
    db = get_db()
    try:
        return db.query(WorkflowORM).filter(WorkflowORM.workflow_id == workflow_id).first()
    finally:
        db.close()


async def list_workflow_records(limit: int = 50) -> List[Dict[str, Any]]:
    """List workflows, most recent first."""
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _list_sync, limit)
    return [_to_dict(r) for r in rows]


def _list_sync(limit: int) -> List[WorkflowORM]:
    db = get_db()
    try:
        return (
            db.query(WorkflowORM)
            .order_by(WorkflowORM.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


async def set_workflow_status(workflow_id: str, status: str) -> bool:
    """Update only the workflow's status (e.g. waiting_approval → running).

    Unlike mark_workflow_finished, this does not touch completed_at or the
    cost/token totals — it's for in-flight state transitions.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _set_status_sync, workflow_id, status)


def _set_status_sync(workflow_id: str, status: str) -> bool:
    db = get_db()
    try:
        row = db.query(WorkflowORM).filter(WorkflowORM.workflow_id == workflow_id).first()
        if not row:
            return False
        row.status = status
        db.commit()
        return True
    finally:
        db.close()


async def mark_workflow_finished(
    workflow_id: str,
    status: str,
    total_cost: float = 0.0,
    total_tokens: int = 0,
    execution_time_ms: int = 0,
    error_message: Optional[str] = None,
    quality_score: Optional[float] = None,
) -> bool:
    """Mark a workflow as completed or failed with final metrics."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _mark_finished_sync, workflow_id, status,
        total_cost, total_tokens, execution_time_ms, error_message,
        quality_score,
    )


def _mark_finished_sync(
    workflow_id, status, total_cost, total_tokens, execution_time_ms, error_message,
    quality_score,
) -> bool:
    db = get_db()
    try:
        row = db.query(WorkflowORM).filter(WorkflowORM.workflow_id == workflow_id).first()
        if not row:
            return False
        row.status = status
        row.total_cost = total_cost
        row.total_tokens = total_tokens
        row.execution_time_ms = execution_time_ms
        row.error_message = error_message
        row.quality_score = quality_score
        row.completed_at = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()


async def list_agent_runs(workflow_id: str) -> List[Dict[str, Any]]:
    """List each agent execution recorded for a workflow, in order."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list_agent_runs_sync, workflow_id)


def _list_agent_runs_sync(workflow_id: str) -> List[Dict[str, Any]]:
    from src.models.agent_run import AgentRun

    db = get_db()
    try:
        rows = (
            db.query(AgentRun)
            .filter(AgentRun.workflow_id == workflow_id)
            .order_by(AgentRun.created_at.asc())
            .all()
        )
        return [
            {
                "agent_id": r.agent_id,
                "agent_name": r.agent_name,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "cost": r.cost,
                "tokens_used": r.tokens_used,
                "success": r.success,
                "error_message": r.error_message,
                "prompt_version": r.prompt_version,
                "task_input": r.task_input,
                "task_output": r.task_output,
            }
            for r in rows
        ]
    finally:
        db.close()
