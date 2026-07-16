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

    def get_cost_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get cost metrics for the platform.

        Args:
            days: Look back this many days

        Returns:
            Cost metrics
        """
        try:
            from src.llm.cost_tracker import get_cost_tracker

            cost_tracker = get_cost_tracker()
            summary = cost_tracker.get_summary()

            return {
                "period_days": days,
                "total_cost": summary.get("total_cost", 0.0),
                "total_tokens": summary.get("total_tokens", 0),
                "request_count": summary.get("request_count", 0),
                "avg_cost_per_request": summary.get("avg_cost_per_request", 0.0),
                "cost_by_model": summary.get("cost_by_model", {}),
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
