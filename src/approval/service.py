"""
Approval Service: Business logic for approval workflow.

Handles:
- Creating approval requests
- Routing based on risk level
- Approving/rejecting
- Temporal workflow coordination

Persists to PostgreSQL (approval_requests table) so requests survive
restarts and can be listed/aggregated for the dashboard.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import uuid4

from src.infrastructure.database import get_db
from src.models.approval import ApprovalRequest as ApprovalRequestORM, ApprovalStatus, ApprovalRisk


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


def _to_dict(row: ApprovalRequestORM) -> Dict[str, Any]:
    """Convert an ORM row to the dict shape the routes layer expects."""
    return {
        "id": str(row.id),
        "approval_id": str(row.id),
        "workflow_id": row.workflow_id,
        "task_id": row.task_id,
        "agent_id": row.agent_id,
        "action": row.action,
        "description": row.description,
        "risk_level": row.risk_level.value if row.risk_level else None,
        "status": row.status.value if row.status else None,
        "required_approvers": row.required_approvers,
        "context": row.context or {},
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "rejected_by": row.approved_by if row.status == ApprovalStatus.REJECTED else None,
        "rejection_reason": row.rejection_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


class ApprovalService:
    """Manage approval requests and workflow."""

    async def create_approval_request(
        self,
        workflow_id: str,
        task_id: str,
        agent_id: str,
        action: str,
        description: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and persist an approval request."""
        policy = ApprovalPolicyEngine.get_policy(action)
        expires_at = datetime.utcnow() + timedelta(minutes=policy["timeout_minutes"])

        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(
            None,
            self._create_sync,
            workflow_id, task_id, agent_id, action, description,
            policy["risk_level"], policy["required_approvers"], context, expires_at,
        )
        return _to_dict(row)

    def _create_sync(
        self, workflow_id, task_id, agent_id, action, description,
        risk_level, required_approvers, context, expires_at,
    ) -> ApprovalRequestORM:
        db = get_db()
        try:
            row = ApprovalRequestORM(
                id=uuid4(),
                workflow_id=workflow_id,
                task_id=task_id,
                agent_id=agent_id,
                action=action,
                description=description,
                risk_level=risk_level,
                status=ApprovalStatus.PENDING,
                required_approvers=required_approvers,
                context=context or {},
                created_at=datetime.utcnow(),
                expires_at=expires_at,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        finally:
            db.close()

    async def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get an approval request by ID."""
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(None, self._get_sync, approval_id)
        return _to_dict(row) if row else None

    def _get_sync(self, approval_id: str) -> Optional[ApprovalRequestORM]:
        db = get_db()
        try:
            return db.query(ApprovalRequestORM).filter(
                ApprovalRequestORM.id == approval_id
            ).first()
        finally:
            db.close()

    async def approve(
        self,
        approval_id: str,
        approved_by: str,
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a request."""
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(None, self._decide_sync, approval_id, ApprovalStatus.APPROVED, approved_by, None)
        return _to_dict(row)

    async def reject(
        self,
        approval_id: str,
        rejected_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Reject a request."""
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(None, self._decide_sync, approval_id, ApprovalStatus.REJECTED, rejected_by, reason)
        return _to_dict(row)

    def _decide_sync(
        self, approval_id: str, new_status: ApprovalStatus, decided_by: str, reason: Optional[str],
    ) -> ApprovalRequestORM:
        db = get_db()
        try:
            row = db.query(ApprovalRequestORM).filter(
                ApprovalRequestORM.id == approval_id
            ).first()
            if not row:
                raise ValueError(f"Approval {approval_id} not found")

            if row.status != ApprovalStatus.PENDING:
                raise ValueError(f"Approval already {row.status.value}")

            if row.is_expired():
                row.status = ApprovalStatus.EXPIRED
                db.commit()
                raise ValueError("Approval request expired")

            row.status = new_status
            row.approved_by = decided_by
            row.completed_at = datetime.utcnow()
            if new_status == ApprovalStatus.APPROVED:
                row.approved_at = datetime.utcnow()
            else:
                row.rejection_reason = reason

            db.commit()
            db.refresh(row)
            return row
        finally:
            db.close()

    async def list_pending(self) -> List[Dict[str, Any]]:
        """List all pending approval requests, most recent first."""
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, self._list_pending_sync)
        return [_to_dict(r) for r in rows]

    def _list_pending_sync(self) -> List[ApprovalRequestORM]:
        db = get_db()
        try:
            return (
                db.query(ApprovalRequestORM)
                .filter(ApprovalRequestORM.status == ApprovalStatus.PENDING)
                .order_by(ApprovalRequestORM.created_at.desc())
                .limit(100)
                .all()
            )
        finally:
            db.close()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get approval workflow statistics."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_statistics_sync)

    def _get_statistics_sync(self) -> Dict[str, Any]:
        db = get_db()
        try:
            counts = {status: 0 for status in ApprovalStatus}
            rows = db.query(ApprovalRequestORM.status, ApprovalRequestORM.id).all()
            for status, _ in rows:
                counts[status] = counts.get(status, 0) + 1

            return {
                "total_approvals": len(rows),
                "pending": counts.get(ApprovalStatus.PENDING, 0),
                "approved": counts.get(ApprovalStatus.APPROVED, 0),
                "rejected": counts.get(ApprovalStatus.REJECTED, 0),
                "expired": counts.get(ApprovalStatus.EXPIRED, 0),
            }
        finally:
            db.close()


# Global service instance
_approval_service = None


def get_approval_service() -> ApprovalService:
    """Get the global approval service."""
    global _approval_service
    if _approval_service is None:
        _approval_service = ApprovalService()
    return _approval_service
