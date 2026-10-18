"""
Pydantic models for Approval API.

Request/response models for approval endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ApprovalAction(str, Enum):
    """Standard approval action types."""
    DATABASE_WRITE = "database_write"
    PRODUCTION_DEPLOY = "production_deploy"
    SEND_EMAIL = "send_email"
    DATA_ACCESS = "data_access"
    CODE_EXECUTION = "code_execution"


class ApprovalRisk(str, Enum):
    """Risk levels for approval."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CreateApprovalRequest(BaseModel):
    """Request to create an approval."""
    workflow_id: str
    task_id: str
    agent_id: str
    action: str = Field(..., description="Action requiring approval")
    description: Optional[str] = None
    risk_level: ApprovalRisk
    context: Optional[Dict[str, Any]] = None
    required_approvers: int = 1


class ApprovalResponse(BaseModel):
    """Approval request details."""
    id: str
    workflow_id: str
    task_id: str
    agent_id: str
    action: str
    description: Optional[str]
    risk_level: str
    status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]


class ApproveRequest(BaseModel):
    """Request to approve an approval. The approval ID comes from the URL path."""
    approved_by: str = Field(..., description="User ID approving")
    comments: Optional[str] = None


class RejectRequest(BaseModel):
    """Request to reject an approval. The approval ID comes from the URL path."""
    rejected_by: str = Field(..., description="User ID rejecting")
    reason: str = Field(..., description="Reason for rejection")


class ApprovalStatusResponse(BaseModel):
    """Response with approval status."""
    approval_id: str
    status: str
    approved: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejected_by: Optional[str]
    rejection_reason: Optional[str]
    workflow_can_resume: bool


class ApprovalListResponse(BaseModel):
    """List of pending approvals."""
    total: int
    pending: int
    approved: int
    rejected: int
    requests: list[ApprovalResponse]
