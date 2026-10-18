"""
API routes for approval workflow.

Endpoints:
- POST /api/approvals - Create approval request
- GET /api/approvals/{id} - Get approval status
- POST /api/approvals/{id}/approve - Approve request
- POST /api/approvals/{id}/reject - Reject request
- GET /api/approvals - List pending approvals
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional

from src.approval.service import get_approval_service
from src.approval.models import (
    CreateApprovalRequest, ApproveRequest, RejectRequest,
    ApprovalResponse, ApprovalStatusResponse
)
from src.infrastructure.temporal_client import get_temporal_client

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])


async def _signal_orchestrator(
    workflow_id: Optional[str],
    approved: bool,
    decided_by: str,
    reason: Optional[str] = None,
) -> bool:
    """
    Signal the paused OrchestratorWorkflow with the human decision so it
    resumes (approved) or terminates cleanly (rejected).

    Standalone approval requests may not have a live workflow behind them —
    a failed signal is logged, not raised, so the DB decision still lands.
    """
    if not workflow_id:
        return False
    try:
        client = get_temporal_client()
        handle = client.get_workflow_handle(f"orchestrator-{workflow_id}")
        await handle.signal(
            "approval_signal",
            {"approved": approved, "approved_by": decided_by, "reason": reason},
        )
        return True
    except Exception as e:
        print(f"Could not signal workflow orchestrator-{workflow_id}: {e}")
        return False


@router.post("/", response_model=ApprovalResponse)
async def create_approval(request: CreateApprovalRequest) -> Dict[str, Any]:
    """
    Create an approval request.

    This pauses a Temporal workflow waiting for human approval.

    Args:
        request: Approval request details

    Returns:
        Created approval with ID and status
    """
    try:
        service = get_approval_service()
        approval = await service.create_approval_request(
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            agent_id=request.agent_id,
            action=request.action,
            description=request.description,
            context=request.context,
        )
        return approval
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{approval_id}", response_model=ApprovalStatusResponse)
async def get_approval_status(approval_id: str) -> Dict[str, Any]:
    """
    Get the status of an approval request.

    Args:
        approval_id: Approval ID

    Returns:
        Current status and details
    """
    try:
        service = get_approval_service()
        approval = await service.get_approval(approval_id)

        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        return {
            "approval_id": approval_id,
            "status": approval["status"],
            "approved": approval["status"] == "approved",
            "approved_by": approval.get("approved_by"),
            "approved_at": approval.get("approved_at"),
            "rejected_by": approval.get("rejected_by"),
            "rejection_reason": approval.get("rejection_reason"),
            "workflow_can_resume": approval["status"] == "approved",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/approve")
async def approve_request(approval_id: str, request: ApproveRequest) -> Dict[str, Any]:
    """
    Approve an approval request.

    Signals Temporal workflow to resume execution.

    Args:
        approval_id: Approval ID
        request: Approval details

    Returns:
        Updated approval status
    """
    try:
        service = get_approval_service()
        approval = await service.approve(
            approval_id=approval_id,
            approved_by=request.approved_by,
            comments=request.comments,
        )

        signaled = await _signal_orchestrator(
            workflow_id=approval.get("workflow_id"),
            approved=True,
            decided_by=request.approved_by,
        )

        return {
            "approval_id": approval_id,
            "status": "approved",
            "workflow_resumed": signaled,
            "message": f"Approved by {request.approved_by}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{approval_id}/reject")
async def reject_request(approval_id: str, request: RejectRequest) -> Dict[str, Any]:
    """
    Reject an approval request.

    Signals Temporal workflow with rejection and failure.

    Args:
        approval_id: Approval ID
        request: Rejection details

    Returns:
        Updated approval status
    """
    try:
        service = get_approval_service()
        approval = await service.reject(
            approval_id=approval_id,
            rejected_by=request.rejected_by,
            reason=request.reason,
        )

        signaled = await _signal_orchestrator(
            workflow_id=approval.get("workflow_id"),
            approved=False,
            decided_by=request.rejected_by,
            reason=request.reason,
        )

        return {
            "approval_id": approval_id,
            "status": "rejected",
            "reason": request.reason,
            "workflow_notified": signaled,
            "message": f"Rejected by {request.rejected_by}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_pending_approvals() -> Dict[str, Any]:
    """
    List all pending approval requests.

    Returns:
        List of pending approvals waiting for action
    """
    try:
        service = get_approval_service()
        pending = await service.list_pending()
        stats = await service.get_statistics()

        return {
            "total": stats["total_approvals"],
            "pending": stats["pending"],
            "approved": stats["approved"],
            "rejected": stats["rejected"],
            "requests": pending,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/")
async def get_approval_statistics() -> Dict[str, Any]:
    """Get approval workflow statistics."""
    try:
        service = get_approval_service()
        stats = await service.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
