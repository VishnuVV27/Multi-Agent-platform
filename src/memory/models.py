"""
Memory system data models.

Pydantic models for RAG workflow memory.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class WorkflowMemory(BaseModel):
    """A stored workflow in the memory system."""

    # Identifiers
    id: Optional[str] = None
    workflow_id: str = Field(..., description="Unique workflow ID")

    # User request
    user_request: str = Field(..., description="Original user request")
    request_embedding: Optional[List[float]] = Field(
        None, description="1536-dim embedding of request"
    )

    # Agent execution
    agents_selected: List[str] = Field(
        ..., description="Agent IDs used: ['research_agent', 'writer_agent']"
    )
    agent_count: int = Field(..., description="Number of agents")
    execution_time_ms: int = Field(..., description="Total execution time")

    # Costs
    total_cost: float = Field(..., description="Total workflow cost in USD")
    tokens_used: int = Field(..., description="Total tokens consumed")
    cost_per_second: float = Field(..., description="Cost efficiency metric")

    # Success metrics
    success: bool = Field(..., description="Did workflow complete successfully?")
    success_rate: float = Field(default=1.0, description="Success probability (0-1)")
    error_message: Optional[str] = Field(None, description="Error if failed")

    # Results
    results_summary: str = Field(..., description="Summary of workflow results")
    key_outcomes: List[str] = Field(
        default_factory=list, description="Key outcomes achieved"
    )

    # Timestamps
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_123",
                "user_request": "Research AI trends and write a report",
                "agents_selected": ["research_agent", "writer_agent"],
                "agent_count": 2,
                "execution_time_ms": 12500,
                "total_cost": 0.08,
                "tokens_used": 3600,
                "cost_per_second": 0.0064,
                "success": True,
                "results_summary": "Generated comprehensive report on 5 AI trends",
                "key_outcomes": ["report_generated", "costs_tracked"],
            }
        }


class RankedWorkflow(BaseModel):
    """Ranked workflow from retrieval."""

    workflow_memory: WorkflowMemory
    relevance_score: float = Field(..., description="Relevance (0-1)")
    success_bonus: float = Field(..., description="Success rate bonus")
    cost_bonus: float = Field(..., description="Cost efficiency bonus")
    final_score: float = Field(..., description="Combined ranking score")

    class Config:
        json_schema_extra = {
            "example": {
                "relevance_score": 0.87,
                "success_bonus": 0.3,
                "cost_bonus": 0.15,
                "final_score": 0.92,
            }
        }


class RetrievalRequest(BaseModel):
    """Request for workflow retrieval."""

    query: str = Field(..., description="User query/request")
    top_k: int = Field(default=3, description="Return top K results")
    min_similarity: float = Field(
        default=0.5, description="Minimum similarity threshold"
    )
    filter_success_only: bool = Field(
        default=False, description="Only return successful workflows?"
    )
    filter_agents: Optional[List[str]] = Field(
        None, description="Filter by specific agents"
    )


class RetrievalResponse(BaseModel):
    """Response with ranked similar workflows."""

    query: str
    results: List[RankedWorkflow]
    retrieval_time_ms: float = Field(..., description="Total retrieval time")
    sparse_results_count: int = Field(..., description="BM25 candidates")
    dense_results_count: int = Field(..., description="Vector candidates")
    candidate_pool_size: int = Field(..., description="Merged candidates")
    took_rerank_time_ms: float = Field(..., description="Reranking duration")
