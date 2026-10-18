"""
ORM Model for workflow execution records.

Lets the API list/query workflows without hitting Temporal directly for
history (Temporal is still the source of truth for live execution state).
"""

from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base


class WorkflowORM(Base):
    """A single workflow run, from creation through completion/failure."""

    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)

    # Thread lineage: set on follow-up runs that continue a previous
    # workflow's output. Points at the ROOT workflow of the thread so one
    # query fetches the whole conversation.
    parent_workflow_id = Column(String(100), nullable=True, index=True)

    prompt = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="running", index=True)  # running|completed|failed
    agents_selected = Column(ARRAY(String), nullable=False, default=list)

    total_cost = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Final Critic Agent score (0-100) for the deliverable, when the plan
    # included a quality review. Null for runs without a critic.
    quality_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Workflow {self.workflow_id} {self.status}>"
