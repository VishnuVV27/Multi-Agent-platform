from sqlalchemy import Column, String, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.infrastructure.database import Base


class AuditLog(Base):
    """Audit trail for all sensitive operations."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # tool_executed, approval_requested, etc.
    resource = Column(String(100), nullable=False)  # tool_name, workflow_id, etc.
    status = Column(String(50), nullable=False)  # success, failed, permission_denied
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.agent_id}>"
