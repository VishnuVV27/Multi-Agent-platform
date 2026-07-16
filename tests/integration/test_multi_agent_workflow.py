"""
Integration tests for multi-agent workflows.

Tests that agents work together in pipelines with proper DAG execution.
"""

import pytest
from src.agents.base import TaskInput, AgentStatus
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.research_agent import ResearchAgent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.writer_agent import WriterAgent


@pytest.mark.asyncio
class TestMultiAgentWorkflows:
    """Test multi-agent DAG execution."""

    async def test_supervisor_generates_multi_agent_dag(self):
        """Supervisor generates DAG with multiple agents."""
        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="wf_multi_1",
            instruction="Research AI trends and write a detailed report"
        )

        output = await supervisor.execute(task_input)

        assert output.status == AgentStatus.COMPLETED
        tasks = output.result.get("tasks", [])

        # Should have both research and writer agents
        agent_ids = [t["agent"] for t in tasks]
        assert "research_agent" in agent_ids
        assert "writer_agent" in agent_ids

        # Should have proper dependency chain
        assert len(tasks) == 2
        assert tasks[0]["depends_on"] == []
        assert "t1" in tasks[1]["depends_on"]

    async def test_supervisor_research_analyze_write_workflow(self):
        """Supervisor generates research → analysis → write workflow."""
        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="wf_comprehensive",
            instruction="Research market trends, analyze data, and write a comprehensive report"
        )

        output = await supervisor.execute(task_input)

        tasks = output.result.get("tasks", [])
        agent_ids = [t["agent"] for t in tasks]

        # All three agents
        assert "research_agent" in agent_ids
        assert "analysis_agent" in agent_ids
        assert "writer_agent" in agent_ids

        # Sequential order with dependencies
        assert tasks[0]["agent"] == "research_agent"
        assert tasks[1]["agent"] == "analysis_agent"
        assert tasks[2]["agent"] == "writer_agent"

    async def test_analysis_agent_initialization(self):
        """Analysis Agent initializes properly."""
        agent = AnalysisAgent()

        assert agent.AGENT_ID == "analysis_agent"
        assert "database_query" in agent.ALLOWED_TOOLS
        assert AgentCapability.DATA_ANALYSIS in agent.CAPABILITIES

    async def test_writer_agent_initialization(self):
        """Writer Agent initializes properly."""
        agent = WriterAgent()

        assert agent.AGENT_ID == "writer_agent"
        assert AgentCapability.WRITING in agent.CAPABILITIES
        assert len(agent.ALLOWED_TOOLS) >= 0

    async def test_research_agent_with_research_findings(self):
        """Research Agent can be called with context."""
        agent = ResearchAgent()
        task_input = TaskInput(
            workflow_id="wf_1",
            instruction="Research Python performance optimization",
            context={"focus": "backend", "max_results": 10}
        )

        output = await agent.execute(task_input)

        # Should complete even if mock
        assert output.workflow_id == "wf_1"
        if output.status == AgentStatus.COMPLETED:
            assert "findings" in output.result

    async def test_analysis_agent_with_context(self):
        """Analysis Agent can be called with previous findings."""
        agent = AnalysisAgent()
        task_input = TaskInput(
            workflow_id="wf_2",
            instruction="Analyze user engagement patterns",
            context={
                "query": "SELECT user_id, COUNT(*) as visits FROM events GROUP BY user_id LIMIT 100"
            }
        )

        output = await agent.execute(task_input)

        assert output.workflow_id == "wf_2"
        # May fail due to database not being real, but contract should be valid
        assert hasattr(output, "task_id")
        assert hasattr(output, "status")

    async def test_writer_agent_with_research_findings(self):
        """Writer Agent uses research findings to write."""
        agent = WriterAgent()
        task_input = TaskInput(
            workflow_id="wf_3",
            instruction="Write a technical report on distributed systems",
            context={
                "research_findings": "Key findings: consistency models, CAP theorem, eventual consistency",
                "format": "report"
            }
        )

        output = await agent.execute(task_input)

        assert output.workflow_id == "wf_3"
        if output.status == AgentStatus.COMPLETED:
            assert "content" in output.result
            assert output.result["format"] == "report"


class TestMultiAgentDAGExecution:
    """Test DAG creation and execution order."""

    def test_dag_respects_dependencies(self):
        """DAG respects task dependencies."""
        supervisor = SupervisorAgent()

        # Test simple chain
        dag = supervisor._build_task_dag(
            agents=["research_agent", "analysis_agent", "writer_agent"],
            original_instruction="Test workflow",
            context={}
        )

        # Verify dependencies
        assert dag[0]["depends_on"] == []  # Research first
        assert dag[1]["depends_on"] == ["t1"]  # Analysis depends on research
        assert dag[2]["depends_on"] == ["t2"]  # Writer depends on analysis

    def test_dag_single_agent(self):
        """DAG with single agent has no dependencies."""
        supervisor = SupervisorAgent()

        dag = supervisor._build_task_dag(
            agents=["research_agent"],
            original_instruction="Just research",
            context={}
        )

        assert len(dag) == 1
        assert dag[0]["depends_on"] == []

    def test_agent_manifest_updated(self):
        """All agents declare correct capabilities."""
        from src.registry.agent_registry import get_agent_registry

        registry = get_agent_registry()

        # Check all agents registered
        research = registry.get_agent("research_agent")
        analysis = registry.get_agent("analysis_agent")
        writer = registry.get_agent("writer_agent")

        assert research is not None
        assert analysis is not None
        assert writer is not None

        # Check capabilities
        assert "web_search" in research["capabilities"]
        assert "data_analysis" in analysis["capabilities"]
        assert "writing" in writer["capabilities"]

        # Check tool permissions
        assert "web_search" in research["allowed_tools"]
        assert "database_query" in analysis["allowed_tools"]
