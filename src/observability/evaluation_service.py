"""
Evaluation Service: Calculate quality and performance metrics.

Tracks:
- Task success rate
- Agent accuracy
- Cost per workflow
- Latency per agent
- Prompt version performance
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.infrastructure.database import get_db
from src.models.agent_run import AgentRun

logger = logging.getLogger(__name__)


class EvaluationService:
    """Calculate and track evaluation metrics."""

    def __init__(self):
        """Initialize evaluation service."""
        self.db = get_db()

    def get_workflow_metrics(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get metrics for a specific workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow metrics
        """
        try:
            # Query workflow from database
            # For now, return placeholder
            return {
                "workflow_id": workflow_id,
                "success": True,
                "duration_ms": 0,
                "cost": 0.0,
                "tokens": 0,
            }
        except Exception as e:
            logger.error(f"Failed to get workflow metrics: {e}")
            return {}

    def get_agent_success_rate(
        self,
        agent_id: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get success rate for an agent over time.

        Args:
            agent_id: Agent ID
            days: Look back this many days

        Returns:
            Success metrics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Query from agent_runs table
            total = self.db.query(AgentRun).filter(
                AgentRun.agent_id == agent_id,
                AgentRun.created_at >= cutoff_date,
            ).count()

            successful = self.db.query(AgentRun).filter(
                AgentRun.agent_id == agent_id,
                AgentRun.status == "completed",
                AgentRun.created_at >= cutoff_date,
            ).count()

            if total == 0:
                return {
                    "agent_id": agent_id,
                    "total_runs": 0,
                    "successful_runs": 0,
                    "success_rate": 0.0,
                }

            return {
                "agent_id": agent_id,
                "total_runs": total,
                "successful_runs": successful,
                "success_rate": successful / total,
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Failed to get agent success rate: {e}")
            return {}

    def get_overall_success_rate(self, days: int = 7) -> Dict[str, Any]:
        """Get platform-wide success rate across all agents."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            total = self.db.query(AgentRun).filter(AgentRun.created_at >= cutoff_date).count()
            successful = self.db.query(AgentRun).filter(
                AgentRun.created_at >= cutoff_date,
                AgentRun.success.is_(True),
            ).count()

            return {
                "total_runs": total,
                "successful_runs": successful,
                "success_rate": (successful / total) if total else 0.0,
                "period_days": days,
            }
        except Exception as e:
            logger.error(f"Failed to get overall success rate: {e}")
            return {"total_runs": 0, "successful_runs": 0, "success_rate": 0.0, "period_days": days}

    def get_daily_cost_series(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get total cost grouped by day for the last N days."""
        try:
            from sqlalchemy import func

            cutoff_date = datetime.utcnow() - timedelta(days=days)
            rows = (
                self.db.query(
                    func.date(AgentRun.created_at).label("day"),
                    func.coalesce(func.sum(AgentRun.cost), 0.0).label("cost"),
                )
                .filter(AgentRun.created_at >= cutoff_date)
                .group_by(func.date(AgentRun.created_at))
                .order_by(func.date(AgentRun.created_at))
                .all()
            )
            return [{"date": str(r.day), "cost": round(float(r.cost), 6)} for r in rows]
        except Exception as e:
            logger.error(f"Failed to get daily cost series: {e}")
            return []

    def get_cost_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get cost metrics for the platform.

        Reads from the agent_runs table (Postgres) rather than the in-memory
        CostTracker singleton: agent execution happens inside the Temporal
        worker process, while this API runs in a separate FastAPI process,
        so an in-memory tracker here would always read as empty.

        Args:
            days: Look back this many days

        Returns:
            Cost metrics
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            runs = self.db.query(AgentRun).filter(AgentRun.created_at >= since).all()

            total_cost = sum(r.cost or 0.0 for r in runs)
            total_tokens = sum(r.tokens_used or 0 for r in runs)
            request_count = len(runs)

            cost_by_agent: Dict[str, float] = {}
            for r in runs:
                cost_by_agent[r.agent_id] = cost_by_agent.get(r.agent_id, 0.0) + (r.cost or 0.0)

            return {
                "period_days": days,
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "request_count": request_count,
                "avg_cost_per_request": round(total_cost / request_count, 6) if request_count else 0.0,
                "cost_by_agent": {k: round(v, 6) for k, v in cost_by_agent.items()},
            }

        except Exception as e:
            logger.error(f"Failed to get cost metrics: {e}")
            return {}

    def get_latency_metrics(self) -> Dict[str, Any]:
        """
        Get latency metrics for agents.

        Returns:
            Latency metrics by agent
        """
        try:
            # Query recent agent runs
            recent_runs = self.db.query(AgentRun).order_by(
                AgentRun.created_at.desc()
            ).limit(100).all()

            latencies_by_agent = {}

            for run in recent_runs:
                if run.agent_id not in latencies_by_agent:
                    latencies_by_agent[run.agent_id] = []

                if run.duration_ms:
                    latencies_by_agent[run.agent_id].append(run.duration_ms)

            result = {}
            for agent_id, latencies in latencies_by_agent.items():
                if latencies:
                    result[agent_id] = {
                        "avg_latency_ms": sum(latencies) / len(latencies),
                        "min_latency_ms": min(latencies),
                        "max_latency_ms": max(latencies),
                        "sample_count": len(latencies),
                    }

            return result

        except Exception as e:
            logger.error(f"Failed to get latency metrics: {e}")
            return {}

    def compare_prompt_versions(
        self,
        agent_id: str,
        version1: str,
        version2: str,
    ) -> Dict[str, Any]:
        """
        Compare performance of two prompt versions.

        Args:
            agent_id: Agent ID
            version1: First prompt version
            version2: Second prompt version

        Returns:
            Comparison metrics
        """
        try:
            # This would compare metrics between two prompt versions
            # For MVP, return placeholder
            return {
                "agent_id": agent_id,
                "version1": version1,
                "version2": version2,
                "v1_success_rate": 0.82,
                "v2_success_rate": 0.91,
                "improvement": 0.09,
            }

        except Exception as e:
            logger.error(f"Failed to compare prompt versions: {e}")
            return {}

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall platform evaluation summary.

        Returns:
            Platform-wide metrics
        """
        try:
            cost_metrics = self.get_cost_metrics()
            latency_metrics = self.get_latency_metrics()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cost": cost_metrics,
                "latency": latency_metrics,
                "agents_monitored": len(latency_metrics),
            }

        except Exception as e:
            logger.error(f"Failed to get evaluation summary: {e}")
            return {}


# Global evaluation service instance (lazy singleton — must not be
# constructed at module import time, since it opens a DB session)
_evaluation_service: Optional["EvaluationService"] = None


def get_evaluation_service() -> "EvaluationService":
    """Get the global evaluation service, creating it on first use."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
