"""
Unit tests for Approval Service.

Tests approval creation, routing, approval/rejection, and lifecycle.
"""

import pytest
from src.approval.service import (
    ApprovalService, ApprovalPolicyEngine, get_approval_service
)
from src.models.approval import ApprovalStatus, ApprovalRisk


class TestApprovalPolicyEngine:
    """Tests for approval policy routing."""

    def test_database_write_policy(self):
        """Database write requires high risk approval."""
        policy = ApprovalPolicyEngine.get_policy("database_write")
        assert policy["risk_level"] == ApprovalRisk.HIGH
        assert policy["required_approvers"] == 1

    def test_production_deploy_policy(self):
        """Production deploy requires critical risk approval."""
        policy = ApprovalPolicyEngine.get_policy("production_deploy")
        assert policy["risk_level"] == ApprovalRisk.CRITICAL
        assert policy["required_approvers"] == 2

    def test_send_email_policy(self):
        """Sending email requires medium risk approval."""
        policy = ApprovalPolicyEngine.get_policy("send_email")
        assert policy["risk_level"] == ApprovalRisk.MEDIUM
        assert policy["required_approvers"] == 1

    def test_unknown_action_default_policy(self):
        """Unknown action gets default policy."""
        policy = ApprovalPolicyEngine.get_policy("unknown_action")
        assert policy["risk_level"] == ApprovalRisk.MEDIUM
        assert policy["required_approvers"] == 1

    def test_policy_timeout(self):
        """Policies specify approval timeout."""
        db_policy = ApprovalPolicyEngine.get_policy("database_write")
        deploy_policy = ApprovalPolicyEngine.get_policy("production_deploy")

        assert db_policy["timeout_minutes"] == 60
        assert deploy_policy["timeout_minutes"] == 120


class TestApprovalService:
    """Tests for approval service logic."""

    @pytest.mark.asyncio
    async def test_create_approval_request(self):
        """Create an approval request."""
        service = ApprovalService()
        approval = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="database_write",
            description="Write to production database",
        )

        assert approval["approval_id"] is not None
        assert approval["workflow_id"] == "wf_1"
        assert approval["agent_id"] == "agent_1"
        assert approval["status"] == ApprovalStatus.PENDING.value
        assert approval["risk_level"] == ApprovalRisk.HIGH.value

    @pytest.mark.asyncio
    async def test_get_approval(self):
        """Retrieve an approval request."""
        service = ApprovalService()
        created = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="send_email",
        )

        retrieved = await service.get_approval(created["approval_id"])
        assert retrieved is not None
        assert retrieved["approval_id"] == created["approval_id"]

    @pytest.mark.asyncio
    async def test_approve_request(self):
        """Approve an approval request."""
        service = ApprovalService()
        approval = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="send_email",
        )

        approved = await service.approve(
            approval_id=approval["approval_id"],
            approved_by="user_123",
            comments="Looks good",
        )

        assert approved["status"] == ApprovalStatus.APPROVED.value
        assert approved["approved_by"] == "user_123"
        assert approved["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_reject_request(self):
        """Reject an approval request."""
        service = ApprovalService()
        approval = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="production_deploy",
        )

        rejected = await service.reject(
            approval_id=approval["approval_id"],
            rejected_by="user_456",
            reason="Not ready for production yet",
        )

        assert rejected["status"] == ApprovalStatus.REJECTED.value
        assert rejected["rejected_by"] == "user_456"
        assert rejected["rejection_reason"] == "Not ready for production yet"

    @pytest.mark.asyncio
    async def test_cannot_approve_twice(self):
        """Cannot approve an already approved request."""
        service = ApprovalService()
        approval = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="send_email",
        )

        # First approval
        await service.approve(
            approval_id=approval["approval_id"],
            approved_by="user_1",
        )

        # Second approval should fail
        with pytest.raises(ValueError):
            await service.approve(
                approval_id=approval["approval_id"],
                approved_by="user_2",
            )

    @pytest.mark.asyncio
    async def test_cannot_reject_twice(self):
        """Cannot reject an already rejected request."""
        service = ApprovalService()
        approval = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="send_email",
        )

        # First rejection
        await service.reject(
            approval_id=approval["approval_id"],
            rejected_by="user_1",
            reason="Not ready",
        )

        # Second rejection should fail
        with pytest.raises(ValueError):
            await service.reject(
                approval_id=approval["approval_id"],
                rejected_by="user_2",
                reason="Still not ready",
            )

    @pytest.mark.asyncio
    async def test_approval_with_context(self):
        """Approval includes context for decision making."""
        service = ApprovalService()
        context = {
            "tables_affected": ["users", "orders"],
            "estimated_duration": "30 seconds",
            "risk": "high",
        }

        approval = await service.create_approval_request(
            workflow_id="wf_1",
            task_id="t_1",
            agent_id="agent_1",
            action="database_write",
            description="Migrate user data",
            context=context,
        )

        assert approval["context"] == context

    def test_approval_service_singleton(self):
        """ApprovalService is a singleton."""
        service1 = get_approval_service()
        service2 = get_approval_service()
        assert service1 is service2
