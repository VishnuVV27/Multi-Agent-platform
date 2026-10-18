"""
Approval Request Models (ORM).

Database models for approval workflow tracking and audit.
"""

from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM
from datetime import datetime
import uuid
import enum

from src.models.base import Base


class ApprovalStatus(str, enum.Enum):
    """Approval request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalRisk(str, enum.Enum):
    """Risk level for approval routing."""
    LOW = "low"  # Auto-approved or no approval needed
    MEDIUM = "medium"  # Single approver
    HIGH = "high"  # Team approval
    CRITICAL = "critical"  # Executive approval


class ApprovalRequest(Base):
    """Approval request in the database."""

    __tablename__ = "approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String(100), nullable=False, index=True)
    task_id = Column(String(100), nullable=False)
    agent_id = Column(String(100), nullable=False, index=True)

    # What needs approval
    action = Column(String(100), nullable=False)  # e.g., "database_write", "production_deploy"
    description = Column(String(500), nullable=True)
    risk_level = Column(ENUM(ApprovalRisk), nullable=False)

    # Request details
    context = Column(JSON, nullable=True)  # Full context for approval
    required_approvers = Column(Integer, default=1)  # How many approvals needed

    # Status
    status = Column(ENUM(ApprovalStatus), default=ApprovalStatus.PENDING, index=True)
    approved_by = Column(String(100), nullable=True)  # User ID of approver
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(500), nullable=True)

    # Temporal coordination
    temporal_workflow_id = Column(String(100), nullable=True)  # Workflow waiting on this

    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ApprovalRequest {self.id} {self.action} {self.status}>"

    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False


class ApprovalPolicy(Base):
    """Policy rules for approval routing."""

    __tablename__ = "approval_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(String(100), nullable=False, unique=True, index=True)

    # Routing
    risk_level = Column(ENUM(ApprovalRisk), nullable=False)
    required_approvers = Column(Integer, default=1)
    approver_group = Column(String(100), nullable=True)  # Team that approves

    # TTL
    approval_timeout_minutes = Column(Integer, default=60)
    auto_approve = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ApprovalPolicy {self.action} {self.risk_level}>"
