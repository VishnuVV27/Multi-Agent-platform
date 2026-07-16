"""
Unit tests for Agent Contract compliance.

Verifies that all agents follow the standardized contract:
- Input/Output validation
- Status handling
- Error handling
- Capability declaration
"""

import pytest
from pydantic import ValidationError

from src.agents.base import (
    BaseAgent, TaskInput, TaskOutput, AgentStatus, AgentCapability
)
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.research_agent import ResearchAgent
from src.registry.agent_registry import get_agent_registry


class TestTaskInputContract:
    """Tests for TaskInput contract validation."""

    def test_task_input_required_fields(self):
        """TaskInput must have required fields."""
        # Valid input
        task_input = TaskInput(
            workflow_id="wf_123",
            instruction="Test instruction"
        )
        assert task_input.workflow_id == "wf_123"
        assert task_input.instruction == "Test instruction"
        assert task_input.task_id is not None  # Auto-generated

    def test_task_input_with_context(self):
        """TaskInput can include context."""
        task_input = TaskInput(
            workflow_id="wf_123",
            instruction="Test",
            context={"key": "value"}
        )
        assert task_input.context == {"key": "value"}

    def test_task_input_with_constraints(self):
        """TaskInput can include constraints."""
        task_input = TaskInput(
            workflow_id="wf_123",
            instruction="Test",
            constraints={"max_tokens": 1000, "timeout": 300}
        )
        assert task_input.constraints["max_tokens"] == 1000


class TestTaskOutputContract:
    """Tests for TaskOutput contract validation."""

    def test_task_output_completed(self):
        """TaskOutput for completed tasks."""
        output = TaskOutput(
            task_id="t_123",
            workflow_id="wf_123",
            status=AgentStatus.COMPLETED,
            result={"data": "test"}
        )
        assert output.status == AgentStatus.COMPLETED
        assert output.result["data"] == "test"
        assert output.error is None

    def test_task_output_failed(self):
        """TaskOutput for failed tasks."""
        output = TaskOutput(
            task_id="t_123",
            workflow_id="wf_123",
            status=AgentStatus.FAILED,
            error={"type": "ValueError", "message": "Test error", "retryable": True}
        )
        assert output.status == AgentStatus.FAILED
        assert output.error["type"] == "ValueError"
        assert output.error["retryable"] is True

    def test_task_output_with_metadata(self):
        """TaskOutput can include metadata."""
        output = TaskOutput(
            task_id="t_123",
            workflow_id="wf_123",
            status=AgentStatus.COMPLETED,
            result={},
            execution_time_ms=1500,
            tokens_used={"input_tokens": 100, "output_tokens": 50}
        )
        assert output.execution_time_ms == 1500
        assert output.tokens_used["input_tokens"] == 100


class TestAgentManifest:
    """Tests for agent metadata (manifest)."""

    def test_supervisor_agent_manifest(self, supervisor_agent):
        """Supervisor Agent has valid manifest."""
        manifest = supervisor_agent.get_manifest()
        assert manifest["agent_id"] == "supervisor_agent"
        assert manifest["agent_name"] == "Supervisor Agent"
        assert "planning_method" in manifest
        assert len(manifest["capabilities"]) > 0

    def test_research_agent_manifest(self, research_agent):
        """Research Agent has valid manifest."""
        manifest = research_agent.get_manifest()
        assert manifest["agent_id"] == "research_agent"
        assert "web_search" in manifest["allowed_tools"]
        assert len(manifest["capabilities"]) > 0

    def test_manifest_has_required_fields(self, supervisor_agent):
        """All agent manifests have required fields."""
        manifest = supervisor_agent.get_manifest()
        required_fields = [
            "agent_id", "agent_name", "description", "version",
            "capabilities", "allowed_tools"
        ]
        for field in required_fields:
            assert field in manifest, f"Missing field: {field}"


class TestAgentRegistryValidation:
    """Tests for agent registry validation."""

    def test_agent_registry_loads_agents(self):
        """Agent registry discovers all registered agents."""
        registry = get_agent_registry()
        agents = registry.list_agents()
        assert "supervisor_agent" in agents
        assert "research_agent" in agents

    def test_agent_registry_get_agent(self):
        """Can retrieve agent metadata from registry."""
        registry = get_agent_registry()
        supervisor = registry.get_agent("supervisor_agent")
        assert supervisor is not None
        assert supervisor["agent_name"] == "Supervisor Agent"

    def test_agent_registry_get_agent_instance(self):
        """Can retrieve agent instance from registry."""
        registry = get_agent_registry()
        supervisor = registry.get_agent_instance("supervisor_agent")
        assert isinstance(supervisor, SupervisorAgent)

    def test_agent_registry_list_by_capability(self):
        """Can find agents by capability."""
        registry = get_agent_registry()
        research_capable = registry.list_agents_by_capability("web_search")
        # Research agent should have web_search capability
        assert len(research_capable) > 0

    def test_agent_registry_validate_agent_contract(self):
        """Registry can validate agent contract compliance."""
        registry = get_agent_registry()
        supervisor = SupervisorAgent()
        is_valid, errors = registry.validate_agent_contract(supervisor)
        assert is_valid, f"Agent contract validation failed: {errors}"

    def test_agent_registry_heartbeat(self):
        """Registry tracks agent heartbeats."""
        registry = get_agent_registry()
        success = registry.heartbeat("supervisor_agent")
        assert success is True
        agent = registry.get_agent("supervisor_agent")
        assert agent["status"] == "healthy"


class TestAgentCapabilitiesContract:
    """Tests for agent capability declaration."""

    def test_supervisor_has_planning_capability(self, supervisor_agent):
        """Supervisor agent declares planning capability."""
        assert AgentCapability.PLANNING in supervisor_agent.CAPABILITIES

    def test_research_has_web_search_capability(self, research_agent):
        """Research agent declares web_search capability."""
        assert AgentCapability.WEB_SEARCH in research_agent.CAPABILITIES

    def test_capability_enum_values(self):
        """Capabilities use standard enum."""
        assert AgentCapability.WEB_SEARCH.value == "web_search"
        assert AgentCapability.PLANNING.value == "planning"


class TestAgentToolsContract:
    """Tests for agent tool permissions."""

    def test_research_agent_allowed_tools(self, research_agent):
        """Research agent declares allowed tools."""
        assert "web_search" in research_agent.ALLOWED_TOOLS

    def test_supervisor_no_tools(self, supervisor_agent):
        """Supervisor agent doesn't need tools."""
        assert len(supervisor_agent.ALLOWED_TOOLS) == 0


class TestAgentVersioning:
    """Tests for agent versioning."""

    def test_agent_version_format(self, supervisor_agent):
        """Agent version follows semantic versioning."""
        assert isinstance(supervisor_agent.VERSION, str)
        assert supervisor_agent.VERSION  # Not empty
        # Basic format check: major.minor.patch or with suffix
        assert "." in supervisor_agent.VERSION

    def test_manifest_includes_version(self, supervisor_agent):
        """Manifest includes agent version."""
        manifest = supervisor_agent.get_manifest()
        assert "version" in manifest
        assert manifest["version"] == supervisor_agent.VERSION
