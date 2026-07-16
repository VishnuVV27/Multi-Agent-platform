"""
Cost tracking for LLM usage.

Tracks:
- Token usage per model
- Cost per request
- Cost per workflow
- Cost per agent
"""

from typing import Dict, Any, Optional
from datetime import datetime
from src.llm.models import get_model_config


@dataclass
class UsageMetrics:
    """Metrics for a single LLM call."""
    workflow_id: str
    agent_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    timestamp: datetime


class CostTracker:
    """Track and aggregate LLM costs."""

    def __init__(self):
        """Initialize tracker."""
        self._usage_history: list[UsageMetrics] = []

    def record_usage(
        self,
        workflow_id: str,
        agent_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Dict[str, Any]:
        """
        Record LLM usage and calculate cost.

        Args:
            workflow_id: Workflow this request belongs to
            agent_id: Agent making the request
            model: Model used
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            Usage metrics with calculated cost
        """
        config = get_model_config(model)
        if not config:
            raise ValueError(f"Unknown model: {model}")

        # Calculate cost
        input_cost = (input_tokens / 1000) * config.input_cost_per_1k_tokens
        output_cost = (output_tokens / 1000) * config.output_cost_per_1k_tokens
        total_cost = input_cost + output_cost

        metrics = UsageMetrics(
            workflow_id=workflow_id,
            agent_id=agent_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost=total_cost,
            timestamp=datetime.utcnow(),
        )

        self._usage_history.append(metrics)
        return self._metrics_to_dict(metrics)

    def get_workflow_cost(self, workflow_id: str) -> float:
        """Get total cost for a workflow."""
        return sum(
            m.cost for m in self._usage_history
            if m.workflow_id == workflow_id
        )

    def get_agent_cost(self, agent_id: str) -> float:
        """Get total cost for an agent."""
        return sum(
            m.cost for m in self._usage_history
            if m.agent_id == agent_id
        )

    def get_model_usage(self, model: str) -> Dict[str, Any]:
        """Get usage statistics for a model."""
        model_usage = [m for m in self._usage_history if m.model == model]
        if not model_usage:
            return {}

        total_cost = sum(m.cost for m in model_usage)
        total_tokens = sum(m.total_tokens for m in model_usage)
        request_count = len(model_usage)

        return {
            "model": model,
            "request_count": request_count,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_cost_per_request": total_cost / request_count if request_count > 0 else 0,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get overall cost summary."""
        if not self._usage_history:
            return {"total_cost": 0, "total_tokens": 0, "request_count": 0}

        total_cost = sum(m.cost for m in self._usage_history)
        total_tokens = sum(m.total_tokens for m in self._usage_history)
        request_count = len(self._usage_history)

        # Group by model
        model_costs = {}
        for m in self._usage_history:
            if m.model not in model_costs:
                model_costs[m.model] = 0
            model_costs[m.model] += m.cost

        return {
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
            "request_count": request_count,
            "avg_cost_per_request": round(total_cost / request_count, 4),
            "cost_by_model": {k: round(v, 4) for k, v in model_costs.items()},
        }

    @staticmethod
    def _metrics_to_dict(metrics: UsageMetrics) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "workflow_id": metrics.workflow_id,
            "agent_id": metrics.agent_id,
            "model": metrics.model,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "total_tokens": metrics.total_tokens,
            "cost": round(metrics.cost, 6),
            "timestamp": metrics.timestamp.isoformat(),
        }


# Global cost tracker
_cost_tracker = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


from dataclasses import dataclass
