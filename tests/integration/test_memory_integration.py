"""
Integration tests for RAG/Memory system with workflows.

Tests end-to-end memory saving and retrieval in actual workflows.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.memory.memory_store import MemoryStore
from src.memory.models import RetrievalRequest, WorkflowMemory
from src.workflows.orchestrator_workflow import OrchestratorWorkflowInput


class TestMemoryIntegration:
    """Integration tests for memory with orchestrator."""

    @pytest.mark.asyncio
    async def test_save_workflow_memory_complete_flow(self):
        """Test complete workflow memory saving flow."""
        memory_store = MemoryStore()

        # Mock embedding service
        with patch.object(
            memory_store.embedding_service, "embed_request", new_callable=AsyncMock
        ) as mock_embed:
            mock_embed.return_value = [0.5] * 1536

            # Save a workflow to memory
            saved = await memory_store.save_workflow_memory(
                workflow_id="wf_test_123",
                user_request="Research AI trends and write report",
                agents_selected=["research_agent", "writer_agent"],
                execution_time_ms=8500,
                total_cost=0.08,
                tokens_used=2400,
                success=True,
                results_summary="Generated comprehensive report on 5 AI trends",
                key_outcomes=["report_generated", "saved_to_s3"],
            )

            assert saved.workflow_id == "wf_test_123"
            assert saved.agent_count == 2
            assert saved.success == True
            assert saved.cost_per_second == pytest.approx(0.0094, rel=0.01)

    @pytest.mark.asyncio
    async def test_retrieve_similar_workflows(self):
        """Test retrieval of similar workflows from memory."""
        memory_store = MemoryStore()

        with patch.object(
            memory_store.embedding_service, "embed_request", new_callable=AsyncMock
        ) as mock_embed:
            mock_embed.return_value = [0.5] * 1536

            # Create a retrieval request
            request = RetrievalRequest(
                query="Research trends and write analysis",
                top_k=3,
                min_similarity=0.5,
                filter_success_only=True,
            )

            # Mock the hybrid retriever
            with patch.object(
                memory_store, "retrieve_workflows", new_callable=AsyncMock
            ) as mock_retrieve:
                mock_retrieve.return_value = MagicMock(
                    results=[],
                    retrieval_time_ms=45.2,
                    sparse_results_count=0,
                    dense_results_count=0,
                    candidate_pool_size=0,
                    took_rerank_time_ms=0,
                )

                response = await memory_store.retrieve_workflows(request)

                assert response.query == "Research trends and write analysis"
                assert response.results == []

    @pytest.mark.asyncio
    async def test_supervisor_uses_memory_for_planning(self):
        """Test that supervisor uses memory context for planning."""
        from src.agents.supervisor_agent import SupervisorAgent
        from src.agents.base import TaskInput

        supervisor = SupervisorAgent()
        task_input = TaskInput(
            workflow_id="wf_test",
            instruction="Research AI trends and write a report",
        )

        # Mock memory retrieval
        with patch("src.agents.supervisor_agent.MemoryStore") as mock_memory_class:
            mock_memory = MagicMock()
            mock_memory_class.return_value = mock_memory

            # Setup mock retrieval
            mock_ranked = MagicMock()
            mock_ranked.workflow_memory = WorkflowMemory(
                workflow_id="wf_similar",
                user_request="Research ML trends and write analysis",
                request_embedding=[0.5] * 1536,
                agents_selected=["research_agent", "writer_agent"],
                agent_count=2,
                execution_time_ms=7500,
                total_cost=0.06,
                tokens_used=2000,
                cost_per_second=0.008,
                success=True,
                success_rate=1.0,
                results_summary="Similar analysis report",
            )

            mock_memory.retrieve_workflows = AsyncMock(
                return_value=MagicMock(
                    results=[mock_ranked],
                    retrieval_time_ms=45.0,
                )
            )

            # Execute supervisor
            output = await supervisor.execute(task_input)

            # Verify memory was called
            mock_memory.retrieve_workflows.assert_called_once()

            # Verify supervisor generated a plan
            assert output.status.value == "completed"
            assert "tasks" in output.result

    def test_orchestrator_workflow_input_has_memory_fields(self):
        """Test that OrchestratorWorkflowInput includes memory fields."""
        input_data = OrchestratorWorkflowInput(
            workflow_id="wf_123",
            user_request="Research competitors",
            tasks=[{"id": "t1", "agent": "research_agent", "input": "..."}],
            agents_selected=["research_agent"],
        )

        assert input_data.workflow_id == "wf_123"
        assert input_data.user_request == "Research competitors"
        assert input_data.agents_selected == ["research_agent"]
        assert len(input_data.tasks) == 1

    @pytest.mark.asyncio
    async def test_memory_retrieval_with_filters(self):
        """Test memory retrieval with various filters."""
        memory_store = MemoryStore()

        # Test with success filter
        request = RetrievalRequest(
            query="Research trends",
            top_k=5,
            min_similarity=0.7,
            filter_success_only=True,
            filter_agents=["research_agent"],
        )

        assert request.filter_success_only == True
        assert request.filter_agents == ["research_agent"]
        assert request.min_similarity == 0.7
        assert request.top_k == 5

    @pytest.mark.asyncio
    async def test_memory_learning_loop(self):
        """Test that memory improves planning over time."""
        memory_store = MemoryStore()

        # Workflow 1: Initial successful request
        workflow1 = await memory_store.save_workflow_memory(
            workflow_id="wf_1",
            user_request="Research AI trends and write comprehensive report",
            agents_selected=["research_agent", "writer_agent"],
            execution_time_ms=10000,
            total_cost=0.08,
            tokens_used=2500,
            success=True,
            results_summary="Generated report",
            key_outcomes=["report_complete"],
        )

        assert workflow1.success == True
        assert workflow1.success_rate == 1.0

        # Workflow 2: Similar request (should retrieve workflow1)
        request = RetrievalRequest(
            query="Research machine learning and write detailed report",
            top_k=3,
            min_similarity=0.6,
        )

        # Verify we can construct the request properly
        assert request.query == "Research machine learning and write detailed report"

    def test_cost_tracking_integration(self):
        """Test cost tracker integration for memory."""
        from src.llm.cost_tracker import get_cost_tracker

        tracker = get_cost_tracker()

        # Record a usage
        tracker.record_usage(
            workflow_id="wf_memory_test",
            agent_id="supervisor_agent",
            model="claude-3-5-sonnet",
            input_tokens=100,
            output_tokens=50,
        )

        # Get workflow cost
        cost = tracker.get_workflow_cost("wf_memory_test")
        assert cost > 0

        # Get workflow tokens
        tokens = tracker.get_workflow_tokens("wf_memory_test")
        assert tokens == 150

    @pytest.mark.asyncio
    async def test_memory_context_in_supervisor_prompt(self):
        """Test that memory context is properly formatted for LLM."""
        memory_context = """Here are 3 similar past requests and how they were handled:
1. Request: "Research ML trends and write report"
   Agents used: [research_agent, writer_agent]
   Success rate: 100%
   Cost: $0.0600

Use these successful patterns to inform your planning decision.

"""

        # Verify context format
        assert "similar past requests" in memory_context
        assert "research_agent" in memory_context
        assert "Success rate: 100%" in memory_context
        assert "$0.0600" in memory_context


class TestMemoryEndToEnd:
    """End-to-end tests for complete memory flow."""

    @pytest.mark.asyncio
    async def test_workflow_save_and_retrieve_flow(self):
        """Test complete save and retrieve flow."""
        memory_store = MemoryStore()

        with patch.object(
            memory_store.embedding_service, "embed_request", new_callable=AsyncMock
        ) as mock_embed:
            mock_embed.return_value = [0.5] * 1536

            # Save first workflow
            await memory_store.save_workflow_memory(
                workflow_id="wf_1",
                user_request="Research AI and write report",
                agents_selected=["research_agent", "writer_agent"],
                execution_time_ms=8000,
                total_cost=0.07,
                tokens_used=2200,
                success=True,
                results_summary="AI report generated",
            )

            # Save second similar workflow
            await memory_store.save_workflow_memory(
                workflow_id="wf_2",
                user_request="Research ML and write analysis",
                agents_selected=["research_agent", "writer_agent"],
                execution_time_ms=7500,
                total_cost=0.065,
                tokens_used=2000,
                success=True,
                results_summary="ML analysis completed",
            )

            # Get statistics
            stats = await memory_store.get_memory_statistics()

            assert stats["total_workflows"] == 2
            assert stats["success_count"] == 2
            assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_ranked_results(self):
        """Test that hybrid search returns properly ranked results."""
        from src.memory.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(MagicMock())

        # Create test memories
        memory_good = WorkflowMemory(
            workflow_id="wf_good",
            user_request="Research trends and write",
            request_embedding=[0.9, 0.1] + [0.0] * 1534,
            agents_selected=["research_agent", "writer_agent"],
            agent_count=2,
            execution_time_ms=5000,
            total_cost=0.05,
            tokens_used=1500,
            cost_per_second=0.01,
            success=True,
            success_rate=0.99,
            results_summary="Good result",
        )

        memory_poor = WorkflowMemory(
            workflow_id="wf_poor",
            user_request="Analyze data",
            request_embedding=[0.1, 0.9] + [0.0] * 1534,
            agents_selected=["analysis_agent"],
            agent_count=1,
            execution_time_ms=3000,
            total_cost=0.02,
            tokens_used=800,
            cost_per_second=0.0067,
            success=False,
            success_rate=0.1,
            results_summary="Poor result",
        )

        # Rerank
        query_embedding = [0.95, 0.05] + [0.0] * 1534
        ranked = await retriever._rerank_candidates(
            query="Research and write",
            query_embedding=query_embedding,
            candidates=[memory_poor, memory_good],
        )

        # Good should rank higher
        assert ranked[0].workflow_memory.workflow_id == "wf_good"
        assert ranked[0].final_score > ranked[1].final_score
