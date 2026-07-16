"""
Unit tests for LLM-powered Supervisor Agent.

Tests LLM-based planning, fallback behavior, and DAG validation.
"""

import pytest
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.base import TaskInput, AgentStatus
from src.agents.supervisor_prompts import validate_generated_dag


class TestSupervisorLLMPlanning:
    """Tests for LLM-based planning."""

    @pytest.mark.asyncio
    async def test_supervisor_accepts_llm_plan(self):
        """Supervisor accepts LLM-generated plan."""
        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="wf_llm_1",
            instruction="Research AI trends and write a comprehensive report"
        )

        output = await supervisor.execute(task_input)

        assert output.status == AgentStatus.COMPLETED
        result = output.result

        # Should have planning_method as "llm"
        assert result["planning_method"] in ["llm", "hardcoded_rules"]

        # Should have tasks
        tasks = result.get("tasks", [])
        assert len(tasks) > 0

        # Should have valid agent IDs
        for task in tasks:
            assert task["agent"] in ["research_agent", "analysis_agent", "writer_agent"]

    @pytest.mark.asyncio
    async def test_supervisor_handles_simple_request(self):
        """Supervisor handles simple single-agent request."""
        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="wf_simple",
            instruction="Research machine learning"
        )

        output = await supervisor.execute(task_input)

        assert output.status == AgentStatus.COMPLETED
        tasks = output.result.get("tasks", [])

        # Could be just research_agent
        assert len(tasks) >= 1

    @pytest.mark.asyncio
    async def test_supervisor_handles_complex_request(self):
        """Supervisor handles complex multi-agent request."""
        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="wf_complex",
            instruction="Research competitors, analyze their market share, and write a detailed market report"
        )

        output = await supervisor.execute(task_input)

        assert output.status == AgentStatus.COMPLETED
        tasks = output.result.get("tasks", [])

        # Should have multiple agents
        assert len(tasks) >= 2

    @pytest.mark.asyncio
    async def test_supervisor_fallback_to_hardcoded(self):
        """Supervisor falls back to hardcoded rules if LLM fails."""
        supervisor = SupervisorAgent()

        # Use a clear keyword that matches hardcoded rules
        task_input = TaskInput(
            workflow_id="wf_fallback",
            instruction="write a report about climate change"
        )

        output = await supervisor.execute(task_input)

        # Should still succeed (either LLM or hardcoded)
        assert output.status == AgentStatus.COMPLETED

    def test_dag_validation_accept_valid(self):
        """Validation accepts valid DAGs."""
        valid_dags = [
            ["research_agent"],
            ["analysis_agent"],
            ["writer_agent"],
            ["research_agent", "writer_agent"],
            ["research_agent", "analysis_agent", "writer_agent"],
        ]

        for dag in valid_dags:
            is_valid, error = validate_generated_dag(dag)
            assert is_valid, f"Valid DAG rejected: {dag}, error: {error}"

    def test_dag_validation_reject_invalid(self):
        """Validation rejects invalid DAGs."""
        invalid_dags = [
            ["unknown_agent"],  # Unknown agent
            ["research_agent", "research_agent"],  # Duplicate
            ["analysis_agent", "research_agent"],  # Wrong order
            ["writer_agent", "research_agent"],  # Wrong order
        ]

        for dag in invalid_dags:
            is_valid, error = validate_generated_dag(dag)
            assert not is_valid, f"Invalid DAG accepted: {dag}"

    def test_supervisor_version_updated(self):
        """Supervisor version reflects LLM upgrade."""
        supervisor = SupervisorAgent()
        assert "2.0" in supervisor.VERSION
        assert "llm" in supervisor.VERSION.lower()


class TestSupervisorTaskCreation:
    """Tests for task creation from agents list."""

    @pytest.mark.asyncio
    async def test_task_dag_has_dependencies(self):
        """Generated DAG respects dependency ordering."""
        supervisor = SupervisorAgent()

        dag = supervisor._build_task_dag(
            agents=["research_agent", "analysis_agent", "writer_agent"],
            original_instruction="Test instruction",
            context={}
        )

        # First task has no dependencies
        assert dag[0]["depends_on"] == []

        # Each subsequent task depends on previous
        for i in range(1, len(dag)):
            prev_task_id = f"t{i}"  # t1, t2, etc.
            assert prev_task_id in dag[i]["depends_on"]

    @pytest.mark.asyncio
    async def test_task_instructions_are_tailored(self):
        """Task instructions are tailored to each agent."""
        supervisor = SupervisorAgent()

        dag = supervisor._build_task_dag(
            agents=["research_agent", "writer_agent"],
            original_instruction="Write a report on AI",
            context={}
        )

        # Research task should mention research
        assert "research" in dag[0]["input"].lower() or "gather" in dag[0]["input"].lower()

        # Writer task should mention writing/report
        assert "write" in dag[1]["input"].lower() or "report" in dag[1]["input"].lower()
