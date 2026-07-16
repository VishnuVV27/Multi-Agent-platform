"""
Approval Service: Business logic for approval workflow.

Handles:
- Creating approval requests
- Routing based on risk level
- Approving/rejecting
- Temporal workflow coordination
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.approval import ApprovalRequest, ApprovalStatus, ApprovalRisk, ApprovalPolicy
from src.infrastructure.redis_client import cache_set, cache_get, cache_delete


class ApprovalPolicyEngine:
    """Determine approval requirements based on action."""

    # Default policies (MVP: hardcoded, later in DB)
    POLICIES = {
        "database_write": {
            "risk_level": ApprovalRisk.HIGH,
            "required_approvers": 1,
            "timeout_minutes": 60,
        },
        "production_deploy": {
            "risk_level": ApprovalRisk.CRITICAL,
            "required_approvers": 2,
            "timeout_minutes": 120,
        },
        "send_email": {
            "risk_level": ApprovalRisk.MEDIUM,
            "required_approvers": 1,
            "timeout_minutes": 30,
        },
        "data_access": {
            "risk_level": ApprovalRisk.HIGH,
            "required_approvers": 1,
            "timeout_minutes": 60,
        },
        "code_execution": {
            "risk_level": ApprovalRisk.CRITICAL,
            "required_approvers": 2,
            "timeout_minutes": 120,
        },
    }

    @staticmethod
    def get_policy(action: str) -> Dict[str, Any]:
        """Get approval policy for an action."""
        return ApprovalPolicyEngine.POLICIES.get(
            action,
            {
                "risk_level": ApprovalRisk.MEDIUM,
                "required_approvers": 1,
                "timeout_minutes": 60,
            }
        )


class ApprovalService:
    """Manage approval requests and workflow."""

    CACHE_PREFIX = "approval:"
    CACHE_TTL = 3600  # 1 hour

    async def create_approval_request(
        self,
        workflow_id: str,
        task_id: str,
        agent_id: str,
        action: str,
        description: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an approval request.

        Args:
            workflow_id: Workflow ID
            task_id: Task ID
            agent_id: Agent requesting approval
            action: Action requiring approval
            description: Description of the action
            context: Full context (for display to approver)

        Returns:
            Approval request details
        """
        # Get policy for this action
        policy = ApprovalPolicyEngine.get_policy(action)

        approval_id = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(
            minutes=policy["timeout_minutes"]
        )

        approval_data = {
            "approval_id": approval_id,
            "workflow_id": workflow_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "action": action,
            "description": description,
            "risk_level": policy["risk_level"].value,
            "status": ApprovalStatus.PENDING.value,
            "required_approvers": policy["required_approvers"],
            "context": context or {},
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "approved_by": None,
            "approved_at": None,
        }

        # Cache the approval request
        cache_key = f"{self.CACHE_PREFIX}{approval_id}"
        await cache_set(cache_key, str(approval_data), ttl=self.CACHE_TTL)

        # TODO: Store in database for persistence

        return approval_data

    async def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get an approval request."""
        cache_key = f"{self.CACHE_PREFIX}{approval_id}"
        data = await cache_get(cache_key)
        if data:
            import ast
            return ast.literal_eval(data)
        return None

    async def approve(
        self,
        approval_id: str,
        approved_by: str,
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve a request.

        Args:
            approval_id: Approval ID
            approved_by: User ID approving
            comments: Optional approval comments

        Returns:
            Updated approval details
        """
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        if approval["status"] != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval already {approval['status']}")

        if approval["expires_at"]:
            expires = datetime.fromisoformat(approval["expires_at"])
            if datetime.utcnow() > expires:
                approval["status"] = ApprovalStatus.EXPIRED.value
                raise ValueError("Approval request expired")

        # Update approval
        approval["status"] = ApprovalStatus.APPROVED.value
        approval["approved_by"] = approved_by
        approval["approved_at"] = datetime.utcnow().isoformat()

        # Cache updated approval
        cache_key = f"{self.CACHE_PREFIX}{approval_id}"
        await cache_set(cache_key, str(approval), ttl=self.CACHE_TTL)

        # TODO: Update database

        return approval

    async def reject(
        self,
        approval_id: str,
        rejected_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Reject a request.

        Args:
            approval_id: Approval ID
            rejected_by: User ID rejecting
            reason: Reason for rejection

        Returns:
            Updated approval details
        """
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        if approval["status"] != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval already {approval['status']}")

        # Update approval
        approval["status"] = ApprovalStatus.REJECTED.value
        approval["rejected_by"] = rejected_by
        approval["rejection_reason"] = reason

        # Cache updated approval
        cache_key = f"{self.CACHE_PREFIX}{approval_id}"
        await cache_set(cache_key, str(approval), ttl=self.CACHE_TTL)

        # TODO: Update database

        return approval

    async def list_pending(self) -> List[Dict[str, Any]]:
        """List all pending approvals."""
        # TODO: Query from database
        # For MVP: return empty list
        return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get approval statistics."""
        return {
            "total_approvals": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0,
        }


# Global service instance
_approval_service = None


def get_approval_service() -> ApprovalService:
    """Get the global approval service."""
    global _approval_service
    if _approval_service is None:
        _approval_service = ApprovalService()
    return _approval_service
