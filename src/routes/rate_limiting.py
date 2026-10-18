"""
API endpoints for rate limiting and budget control.

Monitor quotas, spending, and limits.
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional

from src.rate_limiting.rate_limiter import get_rate_limiter
from src.rate_limiting.budget_manager import get_budget_manager
from src.rate_limiting.policy_engine import get_policy_engine

router = APIRouter(prefix="/api/rate-limiting", tags=["rate-limiting"])


@router.get("/check/{user_id}")
async def check_rate_limits(user_id: str):
    """
    Check rate limit status for a user.

    Path Parameters:
    - user_id: User ID

    Returns:
    - Rate limit status
    - Requests remaining per minute/hour
    """
    try:
        remaining = get_rate_limiter().get_remaining_quota(user_id)
        return {
            "user_id": user_id,
            "remaining": remaining,
            "status": "ok" if all(v > 0 for v in remaining.values()) else "warning",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check limits: {str(e)}")


@router.get("/budget/{user_id}")
async def get_budget_status(
    user_id: str,
    tier: str = Query("free", pattern="^(free|pro|enterprise)$")
):
    """
    Get budget status for a user.

    Path Parameters:
    - user_id: User ID

    Query Parameters:
    - tier: User tier (free, pro, enterprise)

    Returns:
    - Monthly budget
    - Amount spent
    - Amount remaining
    - Percentage used
    """
    try:
        status = get_budget_manager().get_budget_status(user_id, tier)
        if not status:
            raise HTTPException(status_code=404, detail="User not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget: {str(e)}")


@router.post("/reset/{user_id}")
async def reset_rate_limit(user_id: str):
    """
    Reset rate limit for a user (admin only).

    Path Parameters:
    - user_id: User ID

    Returns:
    - Reset status
    """
    try:
        success = get_rate_limiter().reset_limit(user_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset limit")
        return {
            "user_id": user_id,
            "status": "reset",
            "message": "Rate limit reset successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")


@router.get("/policies/users/{tier}")
async def get_user_policy(tier: str = Path(pattern="^(free|pro|enterprise)$")):
    """
    Get rate limit policy for a user tier.

    Path Parameters:
    - tier: User tier

    Returns:
    - Rate limits per tier
    - Budget limits
    - Token limits
    """
    try:
        policy = get_policy_engine().get_user_policy(tier)
        return {
            "tier": tier,
            "policy": policy
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get policy: {str(e)}")


@router.get("/policies/agents/{agent_id}")
async def get_agent_policy(agent_id: str):
    """
    Get rate limit policy for an agent.

    Path Parameters:
    - agent_id: Agent ID

    Returns:
    - Agent-specific limits
    """
    try:
        policy = get_policy_engine().get_agent_policy(agent_id)
        return {
            "agent_id": agent_id,
            "policy": policy
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent policy: {str(e)}")


@router.get("/estimate-cost")
async def estimate_workflow_cost(
    model: str = Query(...),
    estimated_tokens: int = Query(...)
):
    """
    Estimate cost of a workflow before execution.

    Query Parameters:
    - model: Model to be used
    - estimated_tokens: Estimated total tokens

    Returns:
    - Estimated cost in USD
    """
    try:
        cost = get_budget_manager().get_workflow_cost_estimate(model, estimated_tokens)
        return {
            "model": model,
            "estimated_tokens": estimated_tokens,
            "estimated_cost": round(cost, 4),
            "currency": "USD"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to estimate: {str(e)}")


@router.get("/summary")
async def get_rate_limit_summary():
    """
    Get rate limiting and budget system summary.

    Returns:
    - System status
    - Configured tiers
    - Providers being monitored
    """
    try:
        policy_engine = get_policy_engine()
        return {
            "status": "active",
            "users_configured": list(policy_engine.policies.get("users", {}).keys()),
            "agents_monitored": list(policy_engine.policies.get("agents", {}).keys()),
            "providers": list(policy_engine.policies.get("provider_quotas", {}).keys()),
            "message": "Rate limiting and budget control system active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")
