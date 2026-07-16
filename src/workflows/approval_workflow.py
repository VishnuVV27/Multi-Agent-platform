"""
Approval Workflow: Temporal workflow that pauses for human approval.

Flow:
1. Agent requests approval
2. Workflow creates approval request
3. Workflow waits for approval signal from API
4. Human approves/rejects via API
5. Workflow receives signal and either continues or fails
"""

from temporalio import workflow, activity
from dataclasses import dataclass
from typing import Dict, Any, Optional
import asyncio

from src.approval.service import get_approval_service
from src.approval.models import ApprovalRisk


@dataclass
class ApprovalWorkflowInput:
    """Input to approval workflow."""
    workflow_id: str
    task_id: str
    agent_id: str
    action: str
    description: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class ApprovalWorkflowOutput:
    """Output from approval workflow."""
    workflow_id: str
    task_id: str
    approved: bool
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None


# Activity: Create approval request
@activity.defn
async def create_approval_activity(input_data: ApprovalWorkflowInput) -> str:
    """Create an approval request and return its ID."""
    service = get_approval_service()
    approval = await service.create_approval_request(
        workflow_id=input_data.workflow_id,
        task_id=input_data.task_id,
        agent_id=input_data.agent_id,
        action=input_data.action,
        description=input_data.description,
        context=input_data.context,
    )
    return approval["approval_id"]


# Workflow: Approval
@workflow.defn
class ApprovalWorkflow:
    """
    Temporal workflow for requesting and waiting on human approval.

    Flow:
    1. Create approval request (activity)
    2. Wait for approval signal (workflow pause point)
    3. Resume based on approval/rejection
    """

    def __init__(self):
        """Initialize workflow."""
        self._approval_signal = None

    @workflow.signal
    def approval_signal(self, approval_data: Dict[str, Any]) -> None:
        """
        Signal workflow with approval decision.

        Args:
            approval_data: {
                "approved": bool,
                "approved_by": str (if approved),
                "rejection_reason": str (if rejected)
            }
        """
        self._approval_signal = approval_data

    @workflow.run
    async def execute(self, input_data: ApprovalWorkflowInput) -> ApprovalWorkflowOutput:
        """
        Execute approval workflow.

        Pauses waiting for approval signal from API.
        """
        workflow_id = input_data.workflow_id
        task_id = input_data.task_id

        try:
            # Step 1: Create approval request (activity)
            approval_id = await workflow.execute_activity(
                create_approval_activity,
                input_data,
                start_to_close_timeout=300,
            )

            # Step 2: Wait for approval signal (blocking)
            # This is where the workflow pauses waiting for human approval
            await workflow.wait_condition(lambda: self._approval_signal is not None, timeout=3600)

            if self._approval_signal is None:
                # Timeout waiting for approval
                return ApprovalWorkflowOutput(
                    workflow_id=workflow_id,
                    task_id=task_id,
                    approved=False,
                    rejection_reason="Approval request timed out",
                )

            # Step 3: Check if approved or rejected
            approval_data = self._approval_signal
            approved = approval_data.get("approved", False)

            if approved:
                return ApprovalWorkflowOutput(
                    workflow_id=workflow_id,
                    task_id=task_id,
                    approved=True,
                    approved_by=approval_data.get("approved_by"),
                )
            else:
                return ApprovalWorkflowOutput(
                    workflow_id=workflow_id,
                    task_id=task_id,
                    approved=False,
                    rejection_reason=approval_data.get("reason", "Approval rejected"),
                )

        except Exception as e:
            return ApprovalWorkflowOutput(
                workflow_id=workflow_id,
                task_id=task_id,
                approved=False,
                rejection_reason=f"Approval workflow error: {str(e)}",
            )
