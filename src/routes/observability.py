"""
API endpoints for observability, evaluation, and metrics.

Endpoints for Langfuse traces, evaluation metrics, and performance analytics.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from src.observability.evaluation_service import get_evaluation_service
from src.observability.langfuse_client import get_langfuse_client

router = APIRouter(prefix="/api/observability", tags=["observability"])


@router.get("/summary")
async def get_observability_summary():
    """
    Get overall observability summary.

    Returns:
    - Cost metrics
    - Latency metrics
    - Agent success rates
    """
    try:
        summary = get_evaluation_service().get_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")


@router.get("/metrics/costs")
async def get_cost_metrics(days: int = Query(7, ge=1, le=90)):
    """
    Get cost metrics for the platform.

    Query Parameters:
    - days: Look back this many days (default: 7)

    Returns:
    - Total cost
    - Total tokens
    - Cost by model
    - Average cost per request
    """
    try:
        metrics = get_evaluation_service().get_cost_metrics(days=days)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cost metrics: {str(e)}")


@router.get("/metrics/costs/daily")
async def get_daily_cost_metrics(days: int = Query(7, ge=1, le=90)):
    """Get total cost grouped by day for the last N days."""
    try:
        series = get_evaluation_service().get_daily_cost_series(days=days)
        return {"days": days, "series": series}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get daily cost series: {str(e)}")


@router.get("/metrics/success-rate")
async def get_success_rate_metrics(days: int = Query(7, ge=1, le=90)):
    """Get platform-wide success rate across all agents."""
    try:
        return get_evaluation_service().get_overall_success_rate(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get success rate: {str(e)}")


@router.get("/metrics/latency")
async def get_latency_metrics():
    """
    Get latency metrics for all agents.

    Returns:
    - Average latency per agent
    - Min/max latency
    - Sample counts
    """
    try:
        metrics = get_evaluation_service().get_latency_metrics()
        return {"latency_by_agent": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latency metrics: {str(e)}")


@router.get("/metrics/agents/{agent_id}")
async def get_agent_metrics(
    agent_id: str,
    days: int = Query(7, ge=1, le=90)
):
    """
    Get metrics for a specific agent.

    Path Parameters:
    - agent_id: Agent ID

    Query Parameters:
    - days: Look back this many days (default: 7)

    Returns:
    - Success rate
    - Total runs
    - Successful runs
    """
    try:
        metrics = get_evaluation_service().get_agent_success_rate(agent_id=agent_id, days=days)
        if not metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for agent: {agent_id}")
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent metrics: {str(e)}")


@router.get("/prompts/compare")
async def compare_prompts(
    agent_id: str = Query(...),
    version1: str = Query(...),
    version2: str = Query(...)
):
    """
    Compare performance of two prompt versions.

    Query Parameters:
    - agent_id: Agent ID
    - version1: First prompt version
    - version2: Second prompt version

    Returns:
    - Version 1 success rate
    - Version 2 success rate
    - Improvement percentage
    """
    try:
        comparison = get_evaluation_service().compare_prompt_versions(
            agent_id=agent_id,
            version1=version1,
            version2=version2
        )
        return comparison
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare prompts: {str(e)}")


@router.get("/langfuse/status")
async def get_langfuse_status():
    """
    Get Langfuse integration status.

    Returns:
    - Enabled status
    - Connection status
    - API endpoint
    """
    try:
        langfuse = get_langfuse_client()
        return {
            "enabled": langfuse.enabled,
            "host": langfuse.client.host if langfuse.client else None,
            "status": "connected" if langfuse.enabled else "disconnected",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Langfuse status: {str(e)}")


@router.post("/langfuse/flush")
async def flush_langfuse():
    """
    Manually flush pending Langfuse traces.

    Returns:
    - Flush status
    """
    try:
        langfuse = get_langfuse_client()
        langfuse.flush()
        return {"status": "flushed", "message": "Pending traces flushed to Langfuse"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to flush Langfuse: {str(e)}")
