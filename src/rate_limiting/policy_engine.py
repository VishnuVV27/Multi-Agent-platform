"""
Policy Engine: Load and manage rate limiting & budget policies.

Policies defined in YAML for easy management.
"""

import logging
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Load and manage rate limiting policies."""

    def __init__(self, policy_file: Optional[str] = None):
        """
        Initialize policy engine.

        Args:
            policy_file: Path to YAML policy file
        """
        self.policy_file = policy_file or "config/rate_limit_policies.yaml"
        self.policies = self._load_policies()

    def _load_policies(self) -> Dict[str, Any]:
        """
        Load policies from YAML file.

        Returns:
            Policy configuration dict
        """
        try:
            if Path(self.policy_file).exists():
                with open(self.policy_file, "r") as f:
                    policies = yaml.safe_load(f)
                    logger.info(f"Loaded policies from {self.policy_file}")
                    return policies or {}
            else:
                logger.warning(f"Policy file not found: {self.policy_file}")
                return self._get_default_policies()
        except Exception as e:
            logger.error(f"Failed to load policies: {e}")
            return self._get_default_policies()

    def get_user_policy(self, user_tier: str = "free") -> Dict[str, Any]:
        """
        Get rate limit policy for a user tier.

        Args:
            user_tier: User tier (free, pro, enterprise)

        Returns:
            Policy dict with rate limits and budgets
        """
        policies = self.policies.get("users", {})
        return policies.get(user_tier, policies.get("free", {}))

    def get_agent_policy(self, agent_id: str) -> Dict[str, Any]:
        """
        Get policy for a specific agent.

        Args:
            agent_id: Agent ID

        Returns:
            Agent-specific policy
        """
        policies = self.policies.get("agents", {})
        return policies.get(agent_id, {})

    def get_provider_quota(self, provider: str) -> Dict[str, Any]:
        """
        Get provider-specific quotas.

        Args:
            provider: Provider name (openai, anthropic, etc)

        Returns:
            Provider quotas (RPM, TPM, etc)
        """
        quotas = self.policies.get("provider_quotas", {})
        return quotas.get(provider, {})

    def get_workflow_max_cost(self) -> float:
        """Get maximum cost per workflow."""
        return self.policies.get("workflows", {}).get("max_cost", 5.0)

    @staticmethod
    def _get_default_policies() -> Dict[str, Any]:
        """Get default policies if file not found."""
        return {
            "users": {
                "free": {
                    "requests_per_minute": 20,
                    "requests_per_hour": 500,
                    "monthly_budget": 10.0,
                    "max_tokens_per_day": 100000,
                },
                "pro": {
                    "requests_per_minute": 100,
                    "requests_per_hour": 2000,
                    "monthly_budget": 100.0,
                    "max_tokens_per_day": 1000000,
                },
                "enterprise": {
                    "requests_per_minute": 500,
                    "requests_per_hour": 10000,
                    "monthly_budget": None,  # Unlimited
                    "max_tokens_per_day": None,  # Unlimited
                },
            },
            "agents": {
                "research_agent": {"max_tokens_per_workflow": 50000},
                "analysis_agent": {"max_tokens_per_workflow": 30000},
                "writer_agent": {"max_tokens_per_workflow": 40000},
            },
            "provider_quotas": {
                "openai": {"rpm": 3500, "tpm": 80000},
                "anthropic": {"rpm": 5000, "tpm": 100000},
            },
            "workflows": {
                "max_cost": 5.0,
                "max_duration_minutes": 30,
            },
        }


# Global policy engine instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
