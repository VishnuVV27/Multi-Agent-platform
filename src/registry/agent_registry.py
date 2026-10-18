"""
Agent Registry: Service discovery for agents.

Maintains metadata about all agents:
- What agents exist
- What they can do (capabilities)
- What tools they can use
- Which version is active
- Their status

For MVP: In-memory dictionary.
Later: Postgres + Redis cache.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from src.agents.base import BaseAgent, AGENT_REGISTRY as _AGENT_CLASS_REGISTRY


class AgentRegistry:
    """Central registry for agent discovery and lifecycle management."""

    def __init__(self):
        """Initialize registry."""
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._load_registered_agents()

    def _load_registered_agents(self):
        """Load all registered agents from the global AGENT_REGISTRY."""
        for agent_id, agent_instance in _AGENT_CLASS_REGISTRY.items():
            self._agents[agent_id] = {
                "agent_id": agent_id,
                "agent_name": agent_instance.AGENT_NAME,
                "description": agent_instance.DESCRIPTION,
                "version": agent_instance.VERSION,
                "status": "healthy",
                "capabilities": [cap.value for cap in agent_instance.CAPABILITIES],
                "allowed_tools": agent_instance.ALLOWED_TOOLS,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            }

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent metadata by ID."""
        return self._agents.get(agent_id)

    def get_agent_instance(self, agent_id: str) -> Optional[BaseAgent]:
        """Get the actual agent instance."""
        return _AGENT_CLASS_REGISTRY.get(agent_id)

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all agents."""
        return self._agents.copy()

    def list_agents_by_capability(self, capability: str) -> Dict[str, Dict[str, Any]]:
        """List all agents with a specific capability."""
        return {
            agent_id: agent_meta
            for agent_id, agent_meta in self._agents.items()
            if capability in agent_meta.get("capabilities", [])
        }

    def find_agent_for_task(self, required_capabilities: List[str]) -> Optional[str]:
        """
        Find the best agent for a task given required capabilities.

        For MVP: Simple first-match.
        Later: Scoring algorithm based on capability match + performance.

        Args:
            required_capabilities: List of capability names needed

        Returns:
            Agent ID that can fulfill the requirements, or None
        """
        for agent_id, agent_meta in self._agents.items():
            agent_capabilities = set(agent_meta.get("capabilities", []))
            required_set = set(required_capabilities)

            # Check if agent has all required capabilities
            if required_set.issubset(agent_capabilities):
                return agent_id

        return None

    def heartbeat(self, agent_id: str) -> bool:
        """Record a heartbeat for an agent."""
        if agent_id in self._agents:
            self._agents[agent_id]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            self._agents[agent_id]["status"] = "healthy"
            return True
        return False

    def set_agent_status(self, agent_id: str, status: str) -> bool:
        """Set agent status (healthy, unavailable, deprecated)."""
        if agent_id in self._agents:
            self._agents[agent_id]["status"] = status
            return True
        return False

    def validate_agent_contract(self, agent: BaseAgent) -> tuple[bool, List[str]]:
        """
        Validate that an agent follows the Agent Contract.

        Args:
            agent: Agent instance to validate

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check required attributes
        if not hasattr(agent, "AGENT_ID") or not agent.AGENT_ID:
            errors.append("AGENT_ID is required and cannot be empty")

        if not hasattr(agent, "AGENT_NAME") or not agent.AGENT_NAME:
            errors.append("AGENT_NAME is required and cannot be empty")

        if not hasattr(agent, "DESCRIPTION") or not agent.DESCRIPTION:
            errors.append("DESCRIPTION is required and cannot be empty")

        if not hasattr(agent, "CAPABILITIES"):
            errors.append("CAPABILITIES is required")

        if not hasattr(agent, "ALLOWED_TOOLS"):
            errors.append("ALLOWED_TOOLS is required")

        if not hasattr(agent, "VERSION") or not agent.VERSION:
            errors.append("VERSION is required and cannot be empty")

        # Check that execute method is implemented
        if not hasattr(agent, "execute"):
            errors.append("execute() method is required")

        return len(errors) == 0, errors


# Global registry instance
_agent_registry = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
