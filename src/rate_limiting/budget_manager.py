"""
Budget Manager: Track and enforce spending limits.

Controls budget per user, agent, workflow, and monthly.
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

from src.infrastructure.redis_client import get_redis_client
from src.infrastructure.database import get_db
from src.rate_limiting.policy_engine import get_policy_engine
from src.llm.cost_tracker import get_cost_tracker

logger = logging.getLogger(__name__)


class BudgetManager:
    """
    Manage spending limits and track budget usage.

    Prevents overspending by enforcing limits.
    """

    def __init__(self):
        """Initialize budget manager."""
        self.redis = get_redis_client()
        self.policy_engine = get_policy_engine()
        self.cost_tracker = get_cost_tracker()

    def check_budget(
        self,
        user_id: str,
        requested_cost: float,
        user_tier: str = "free",
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request would exceed budget.

        Args:
            user_id: User ID
            requested_cost: Estimated cost of upcoming request
            user_tier: User tier (free, pro, enterprise)

        Returns:
            (is_allowed, info_dict)
        """
        try:
            # Get user budget policy
            policy = self.policy_engine.get_user_policy(user_tier)
            monthly_budget = policy.get("monthly_budget")

            # Unlimited budget
            if monthly_budget is None:
                return True, {
                    "allowed": True,
                    "reason": "unlimited_tier",
                    "monthly_budget": None,
                    "used": 0,
                    "remaining": None,
                }

            # Get this month's spending
            current_month = datetime.utcnow().strftime("%Y-%m")
            budget_key = f"budget:{user_id}:{current_month}"
            used_cost = float(self.redis.get(budget_key) or 0)

            remaining = monthly_budget - used_cost
            allowed = remaining >= requested_cost

            info = {
                "allowed": allowed,
                "monthly_budget": monthly_budget,
                "used": round(used_cost, 4),
                "remaining": round(remaining, 4),
                "requested": round(requested_cost, 4),
                "would_exceed": not allowed,
            }

            if allowed:
                logger.debug(f"Budget OK: {user_id} (${used_cost:.4f}/${monthly_budget})")
            else:
                logger.warning(f"Budget exceeded: {user_id} (${used_cost:.4f}/${monthly_budget})")

            return allowed, info

        except Exception as e:
            logger.error(f"Budget check failed: {e}")
            return True, {"allowed": True, "error": str(e)}

    def track_cost(self, user_id: str, workflow_id: str, cost: float) -> bool:
        """
        Track a cost against user's budget.

        Args:
            user_id: User ID
            workflow_id: Workflow ID
            cost: Cost amount

        Returns:
            True if tracked successfully
        """
        try:
            current_month = datetime.utcnow().strftime("%Y-%m")
            budget_key = f"budget:{user_id}:{current_month}"

            # Increment budget usage
            self.redis.incrbyfloat(budget_key, cost)

            # Set expiration (next month)
            next_month = datetime.utcnow() + timedelta(days=32)
            days_until_next_month = (
                next_month.replace(day=1) - datetime.utcnow()
            ).days
            self.redis.expire(budget_key, days_until_next_month * 86400)

            logger.debug(f"Tracked cost: {user_id} +${cost:.4f}")
            return True

        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            return False

    def get_budget_status(self, user_id: str, user_tier: str = "free") -> Dict[str, any]:
        """
        Get budget status for a user.

        Args:
            user_id: User ID
            user_tier: User tier

        Returns:
            Budget status dict
        """
        try:
            policy = self.policy_engine.get_user_policy(user_tier)
            monthly_budget = policy.get("monthly_budget")

            current_month = datetime.utcnow().strftime("%Y-%m")
            budget_key = f"budget:{user_id}:{current_month}"
            used_cost = float(self.redis.get(budget_key) or 0)

            if monthly_budget is None:
                percentage = 0
                remaining = None
            else:
                remaining = monthly_budget - used_cost
                percentage = (used_cost / monthly_budget * 100) if monthly_budget > 0 else 0

            return {
                "user_id": user_id,
                "tier": user_tier,
                "month": current_month,
                "monthly_budget": monthly_budget,
                "used": round(used_cost, 4),
                "remaining": round(remaining, 4) if remaining is not None else None,
                "percentage_used": round(percentage, 2),
                "is_unlimited": monthly_budget is None,
            }

        except Exception as e:
            logger.error(f"Failed to get budget status: {e}")
            return {}

    def get_workflow_cost_estimate(
        self,
        model: str,
        estimated_tokens: int,
    ) -> float:
        """
        Estimate cost of a workflow.

        Args:
            model: Model to be used
            estimated_tokens: Estimated total tokens

        Returns:
            Estimated cost
        """
        try:
            from src.llm.models import get_model_config

            config = get_model_config(model)
            if not config:
                return 0.0

            # Rough estimate: assume 30% input, 70% output
            input_tokens = int(estimated_tokens * 0.3)
            output_tokens = int(estimated_tokens * 0.7)

            input_cost = (input_tokens / 1000) * config.input_cost_per_1k_tokens
            output_cost = (output_tokens / 1000) * config.output_cost_per_1k_tokens

            return input_cost + output_cost

        except Exception as e:
            logger.error(f"Failed to estimate cost: {e}")
            return 0.0


# Global budget manager instance
_budget_manager: Optional[BudgetManager] = None


def get_budget_manager() -> BudgetManager:
    """Get the global budget manager."""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager()
    return _budget_manager
