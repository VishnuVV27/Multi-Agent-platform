"""
ORM Model for agent executions.

Stores execution history for evaluation and metrics tracking.
"""

from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AgentRun(Base):
    """
    SQLAlchemy ORM model for agent executions.

    Tracks every time an agent runs, including:
    - Execution metrics (time, cost, tokens)
    - Success/failure status
    - Input/output
    """

    __tablename__ = "agent_runs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(200), nullable=True)

    # Execution
    task_input = Column(Text, nullable=False)
    task_output = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed

    # Metrics
    duration_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)

    # Success tracking
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<AgentRun {self.agent_id}:{self.workflow_id}>"
