"""
Integration tests for Agent Contract.

Tests that agents properly implement the contract through full execution.
"""

import pytest
import asyncio

from src.agents.base import TaskInput, TaskOutput, AgentStatus
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.research_agent import ResearchAgent


@pytest.mark.asyncio
class TestSupervisorAgentContract:
    """Test Supervisor Agent contract compliance."""

    async def test_supervisor_executes_with_valid_input(self):
        """Supervisor accepts TaskInput and returns TaskOutput."""
        agent = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research AI trends and analyze them"
        )

        output = await agent.execute(task_input)

        # Verify output contract
        assert isinstance(output, TaskOutput)
        assert output.task_id == task_input.task_id
        assert output.workflow_id == task_input.workflow_id
        assert output.status in [AgentStatus.COMPLETED, AgentStatus.FAILED]

    async def test_supervisor_returns_task_dag(self):
        """Supervisor returns valid task DAG."""
        agent = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research competitors"
        )

        output = await agent.execute(task_input)

        assert output.status == AgentStatus.COMPLETED
        assert "tasks" in output.result
        assert len(output.result["tasks"]) > 0

        # Verify task structure
        for task in output.result["tasks"]:
            assert "id" in task
            assert "agent" in task
            assert "input" in task
            assert "depends_on" in task

    async def test_supervisor_contract_validation_wrapper(self):
        """Supervisor's contract validation wrapper works."""
        agent = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Test"
        )

        # Use the validation wrapper
        output = await agent.execute_with_contract_validation(task_input)

        # Should still be valid output
        assert isinstance(output, TaskOutput)
        assert output.status in [AgentStatus.COMPLETED, AgentStatus.FAILED]

    async def test_supervisor_handles_errors(self):
        """Supervisor handles errors gracefully."""
        agent = SupervisorAgent()
        # Empty instruction
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction=""
        )

        output = await agent.execute(task_input)

        # Should handle gracefully
        assert isinstance(output, TaskOutput)
        assert output.workflow_id == task_input.workflow_id


@pytest.mark.asyncio
class TestResearchAgentContract:
    """Test Research Agent contract compliance."""

    async def test_research_executes_with_valid_input(self):
        """Research agent accepts TaskInput and returns TaskOutput."""
        agent = ResearchAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research AI trends"
        )

        output = await agent.execute(task_input)

        # Verify output contract
        assert isinstance(output, TaskOutput)
        assert output.task_id == task_input.task_id
        assert output.workflow_id == task_input.workflow_id
        assert output.status in [AgentStatus.COMPLETED, AgentStatus.FAILED]

    async def test_research_returns_structured_results(self):
        """Research agent returns structured results."""
        agent = ResearchAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research machine learning"
        )

        output = await agent.execute(task_input)

        if output.status == AgentStatus.COMPLETED:
            assert "query" in output.result
            assert "findings" in output.result
            assert "summary" in output.result
            assert isinstance(output.result["findings"], list)

    async def test_research_contract_validation_wrapper(self):
        """Research agent's validation wrapper works."""
        agent = ResearchAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Test research"
        )

        output = await agent.execute_with_contract_validation(task_input)

        assert isinstance(output, TaskOutput)
        assert output.status in [AgentStatus.COMPLETED, AgentStatus.FAILED]

    async def test_research_includes_metadata(self):
        """Research agent can include execution metadata."""
        agent = ResearchAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research trends"
        )

        output = await agent.execute(task_input)

        # Metadata is optional but structure should be valid
        if output.execution_time_ms:
            assert isinstance(output.execution_time_ms, int)
        if output.tokens_used:
            assert isinstance(output.tokens_used, dict)


@pytest.mark.asyncio
class TestAgentContractChaining:
    """Test agents working together with contract compliance."""

    async def test_supervisor_output_as_orchestrator_input(self):
        """Supervisor's output can feed into Orchestrator's input."""
        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research and analyze competitors"
        )

        # Supervisor generates DAG
        supervisor_output = await supervisor.execute(task_input)
        assert supervisor_output.status == AgentStatus.COMPLETED

        # Extract tasks from supervisor output
        tasks = supervisor_output.result.get("tasks", [])
        assert len(tasks) > 0

        # Verify tasks are valid for orchestrator
        for task in tasks:
            assert "id" in task
            assert "agent" in task
            assert "input" in task
            # Task input should be a string (instruction)
            assert isinstance(task["input"], str)

    async def test_research_output_structure_for_chaining(self):
        """Research agent output can be chained to next agent."""
        research = ResearchAgent()
        task_input = TaskInput(
            workflow_id="test_wf_1",
            instruction="Research AI trends"
        )

        output = await research.execute(task_input)

        if output.status == AgentStatus.COMPLETED:
            # Output should be serializable and pass-able to next agent
            result = output.result
            assert isinstance(result, dict)
            # Next agent would receive this as context
            assert "findings" in result or "summary" in result


class TestContractConsistency:
    """Test consistency across agent implementations."""

    def test_all_agents_have_required_attributes(self):
        """All agents declare required attributes."""
        from src.registry.agent_registry import get_agent_registry

        registry = get_agent_registry()
        agents = registry.list_agents()

        for agent_id, agent_meta in agents.items():
            assert agent_meta["agent_id"]
            assert agent_meta["agent_name"]
            assert agent_meta["description"]
            assert agent_meta["version"]
            assert isinstance(agent_meta["capabilities"], list)
            assert isinstance(agent_meta["allowed_tools"], list)

    def test_agent_ids_are_unique(self):
        """All agent IDs are unique."""
        from src.registry.agent_registry import get_agent_registry

        registry = get_agent_registry()
        agents = registry.list_agents()
        agent_ids = [a["agent_id"] for a in agents.values()]

        assert len(agent_ids) == len(set(agent_ids))
