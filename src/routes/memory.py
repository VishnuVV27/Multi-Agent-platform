"""
API endpoints for workflow memory management.

Endpoints for retrieving similar workflows, storing memories, and analytics.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from src.memory.memory_store import get_memory_store
from src.memory.models import RetrievalRequest, RetrievalResponse, WorkflowMemory

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_similar_workflows(request: RetrievalRequest):
    """
    Retrieve top-K similar workflows from memory.

    Uses hybrid search:
    1. BM25 full-text search (keywords)
    2. Dense vector search (semantics)
    3. Reranking by relevance + success + cost

    Query Parameters:
    - top_k: Number of results to return (default: 3)
    - min_similarity: Minimum similarity threshold (default: 0.5)
    - filter_success_only: Only successful workflows (default: false)
    - filter_agents: Filter by specific agents (optional)

    Example:
    POST /api/memory/retrieve
    {
        "query": "Research AI trends and write a report",
        "top_k": 3,
        "min_similarity": 0.5,
        "filter_success_only": false
    }
    """
    try:
        response = await get_memory_store().retrieve_workflows(request)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.get("/workflows/{workflow_id}", response_model=Optional[WorkflowMemory])
async def get_workflow_memory(workflow_id: str):
    """
    Get a specific workflow memory by ID.

    Args:
        workflow_id: Workflow ID to retrieve

    Returns:
        WorkflowMemory if found, null otherwise

    Example:
    GET /api/memory/workflows/wf_123
    """
    try:
        memory = await get_memory_store().get_workflow_memory(workflow_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return memory

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow: {str(e)}")


@router.get("/statistics")
async def get_memory_statistics():
    """
    Get statistics about stored workflow memories.

    Returns statistics including:
    - total_workflows: Total stored workflows
    - success_count: Successful workflows
    - failure_count: Failed workflows
    - success_rate: Overall success rate
    - avg_cost: Average cost per workflow
    - avg_tokens: Average tokens used
    - avg_execution_time_ms: Average execution time

    Example:
    GET /api/memory/statistics
    """
    try:
        stats = await get_memory_store().get_memory_statistics()
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.delete("/old")
async def delete_old_memories(days: int = Query(90, ge=1, le=365)):
    """
    Delete workflow memories older than specified days.

    Useful for pruning old low-value memories and managing database size.

    Query Parameters:
    - days: Delete memories older than this many days (default: 90, min: 1, max: 365)

    Returns:
    - deleted_count: Number of memories deleted

    Example:
    DELETE /api/memory/old?days=90
    """
    try:
        deleted_count = await get_memory_store().delete_old_memories(days=days)
        return {
            "deleted_count": deleted_count,
            "days_threshold": days,
            "message": f"Deleted {deleted_count} memories older than {days} days",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.post("/search")
async def search_memories(
    query: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(5, ge=1, le=50),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0),
):
    """
    Quick search endpoint for memory retrieval.

    Simplified version of /retrieve for common use cases.

    Query Parameters:
    - query: Search query (required)
    - top_k: Number of results (default: 5)
    - min_similarity: Similarity threshold (default: 0.5)

    Returns:
    - results: List of ranked workflows
    - took_ms: Total retrieval time

    Example:
    GET /api/memory/search?query=research%20and%20analysis&top_k=3
    """
    try:
        request = RetrievalRequest(
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        response = await get_memory_store().retrieve_workflows(request)

        return {
            "query": query,
            "results": [
                {
                    "workflow_id": r.workflow_memory.workflow_id,
                    "user_request": r.workflow_memory.user_request,
                    "agents": r.workflow_memory.agents_selected,
                    "cost": r.workflow_memory.total_cost,
                    "success": r.workflow_memory.success,
                    "relevance_score": r.relevance_score,
                    "final_score": r.final_score,
                }
                for r in response.results
            ],
            "took_ms": response.retrieval_time_ms,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
