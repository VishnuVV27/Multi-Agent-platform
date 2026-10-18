"""
ORM Models for workflow memory storage.

Uses PostgreSQL + pgvector for semantic search.
"""

from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ARRAY, Computed, Index
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector

from src.models.base import Base


class WorkflowMemoryORM(Base):
    """
    SQLAlchemy ORM model for workflow memories.

    Stores workflow execution details with embeddings for semantic search.
    Uses PostgreSQL pgvector extension for vector operations.
    """

    __tablename__ = "workflow_memories"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(String(100), unique=True, nullable=False, index=True)

    # User request
    user_request = Column(Text, nullable=False)
    # Full-text search lexemes, kept in sync by Postgres itself (generated
    # column). Powers the sparse half of hybrid retrieval: stemming, stop
    # words, and ts_rank scoring instead of brittle ILIKE substring matching.
    request_tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(user_request, ''))", persisted=True),
        nullable=True,
    )
    # 1536-dimensional embedding (OpenAI text-embedding-3-small via LiteLLM)
    request_embedding = Column(Vector(1536), nullable=False)

    # Agent execution
    agents_selected = Column(ARRAY(String), nullable=False, default=[])
    agent_count = Column(Integer, nullable=False)
    execution_time_ms = Column(Integer, nullable=False)

    # Costs
    total_cost = Column(Float, nullable=False)
    tokens_used = Column(Integer, nullable=False)
    cost_per_second = Column(Float, nullable=False)

    # Success metrics
    success = Column(Boolean, nullable=False)
    success_rate = Column(Float, default=1.0)
    error_message = Column(Text, nullable=True)

    # Results
    results_summary = Column(Text, nullable=False)
    key_outcomes = Column(ARRAY(String), nullable=False, default=[])

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index(
            "workflow_memories_request_tsv_idx",
            "request_tsv",
            postgresql_using="gin",
        ),
    )

    def __repr__(self):
        return f"<WorkflowMemory {self.workflow_id}>"
