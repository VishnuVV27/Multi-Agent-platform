"""
Unit tests for RAG/Memory system.

Tests embedding generation, hybrid search, reranking, and memory operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.memory.models import WorkflowMemory, RankedWorkflow, RetrievalRequest
from src.memory.embedding_service import EmbeddingService
from src.memory.hybrid_retriever import HybridRetriever


class TestEmbeddingService:
    """Tests for embedding generation and caching."""

    @pytest.mark.asyncio
    async def test_embed_request_generates_vector(self):
        """Embedding service generates correct-size vector."""
        service = EmbeddingService()

        with patch.object(
            service.llm_gateway, "embed", new_callable=AsyncMock
        ) as mock_embed:
            # Mock embedding response
            embedding = [0.1] * 1536
            mock_embed.return_value = {
                "data": [{"embedding": embedding}],
                "model": "text-embedding-3-small",
            }

            result = await service.embed_request("Test request")

            assert len(result) == 1536
            assert all(isinstance(x, float) for x in result)

    def test_cache_key_generation(self):
        """Cache key is deterministic."""
        key1 = EmbeddingService._get_cache_key("Hello world")
        key2 = EmbeddingService._get_cache_key("Hello world")
        key3 = EmbeddingService._get_cache_key("Different text")

        assert key1 == key2, "Same text should produce same key"
        assert key1 != key3, "Different text should produce different key"
        assert key1.startswith("embedding:"), "Key should have prefix"

    @pytest.mark.asyncio
    async def test_batch_embedding_efficiency(self):
        """Batch embedding reduces API calls."""
        service = EmbeddingService()

        with patch.object(
            service, "_call_embedding_api", new_callable=AsyncMock
        ) as mock_api:
            embedding = [0.1] * 1536
            mock_api.return_value = embedding

            texts = ["Request 1", "Request 2", "Request 3"]
            result = await service.embed_batch(texts)

            assert len(result) == 3
            assert all(len(e) == 1536 for e in result)
            # API should be called 3 times (all cache misses)
            assert mock_api.call_count == 3


class TestHybridRetriever:
    """Tests for hybrid search with reranking."""

    def test_cosine_similarity_calculation(self):
        """Cosine similarity computed correctly."""
        embedding1 = [1, 0, 0]
        embedding2 = [1, 0, 0]
        embedding3 = [0, 1, 0]

        memory2 = WorkflowMemory(
            workflow_id="wf2",
            user_request="Request 2",
            request_embedding=embedding2,
            agents_selected=["research_agent"],
            agent_count=1,
            execution_time_ms=1000,
            total_cost=0.01,
            tokens_used=100,
            cost_per_second=0.01,
            success=True,
            success_rate=1.0,
            results_summary="Summary 2",
        )

        memory3 = WorkflowMemory(
            workflow_id="wf3",
            user_request="Request 3",
            request_embedding=embedding3,
            agents_selected=["analysis_agent"],
            agent_count=1,
            execution_time_ms=1000,
            total_cost=0.01,
            tokens_used=100,
            cost_per_second=0.01,
            success=True,
            success_rate=1.0,
            results_summary="Summary 3",
        )

        retriever = HybridRetriever(MagicMock())

        # Perfect match
        sim2 = retriever._cosine_similarity(embedding1, memory2)
        assert sim2 == pytest.approx(1.0), "Identical vectors should have similarity 1.0"

        # Perpendicular
        sim3 = retriever._cosine_similarity(embedding1, memory3)
        assert sim3 == pytest.approx(0.0), "Perpendicular vectors should have similarity 0.0"

    def test_bm25_score_approximation(self):
        """BM25 score approximation works."""
        memory = WorkflowMemory(
            workflow_id="wf1",
            user_request="Research trends and analysis",
            request_embedding=[0.1] * 1536,
            agents_selected=["research_agent", "analysis_agent"],
            agent_count=2,
            execution_time_ms=5000,
            total_cost=0.05,
            tokens_used=1500,
            cost_per_second=0.01,
            success=True,
            success_rate=0.95,
            results_summary="Summary",
        )

        retriever = HybridRetriever(MagicMock())

        # Query with many matching terms
        score_high = retriever._approximate_bm25_score(
            "Research trends analysis", memory
        )

        # Query with few matching terms
        score_low = retriever._approximate_bm25_score("Deploy", memory)

        assert score_high > score_low, "More matching terms should give higher score"
        assert 0 <= score_high <= 1, "Score should be between 0 and 1"
        assert 0 <= score_low <= 1, "Score should be between 0 and 1"

    def test_merge_candidates_removes_duplicates(self):
        """Candidate merging removes duplicates."""
        memory1 = WorkflowMemory(
            workflow_id="wf1",
            user_request="Request 1",
            request_embedding=[0.1] * 1536,
            agents_selected=["research_agent"],
            agent_count=1,
            execution_time_ms=1000,
            total_cost=0.01,
            tokens_used=100,
            cost_per_second=0.01,
            success=True,
            success_rate=1.0,
            results_summary="Summary",
        )

        memory2 = WorkflowMemory(
            workflow_id="wf2",
            user_request="Request 2",
            request_embedding=[0.1] * 1536,
            agents_selected=["writer_agent"],
            agent_count=1,
            execution_time_ms=1000,
            total_cost=0.01,
            tokens_used=100,
            cost_per_second=0.01,
            success=True,
            success_rate=1.0,
            results_summary="Summary",
        )

        retriever = HybridRetriever(MagicMock())

        bm25_results = [memory1, memory2]
        dense_results = [memory2, memory1]  # Different order, includes duplicates

        merged = retriever._merge_candidates(bm25_results, dense_results)

        assert len(merged) == 2, "Merged should have 2 unique items"
        assert merged[0].workflow_id == "wf1", "Order should be preserved"
        assert merged[1].workflow_id == "wf2"

    @pytest.mark.asyncio
    async def test_reranking_by_success_and_cost(self):
        """Reranking correctly weights success and cost."""
        memory_successful_cheap = WorkflowMemory(
            workflow_id="wf1",
            user_request="Research",
            request_embedding=[0.5] * 1536,
            agents_selected=["research_agent"],
            agent_count=1,
            execution_time_ms=2000,
            total_cost=0.01,
            tokens_used=500,
            cost_per_second=0.005,  # Cheap
            success=True,
            success_rate=1.0,  # Successful
            results_summary="Summary",
        )

        memory_failed_expensive = WorkflowMemory(
            workflow_id="wf2",
            user_request="Research",
            request_embedding=[0.4] * 1536,  # Slightly different
            agents_selected=["analysis_agent"],
            agent_count=1,
            execution_time_ms=5000,
            total_cost=0.10,
            tokens_used=2000,
            cost_per_second=0.02,  # Expensive
            success=False,
            success_rate=0.0,  # Failed
            results_summary="Summary",
        )

        retriever = HybridRetriever(MagicMock())

        ranked = await retriever._rerank_candidates(
            query="Research",
            query_embedding=[0.5] * 1536,
            candidates=[memory_failed_expensive, memory_successful_cheap],
        )

        # Successful cheap should rank higher
        assert ranked[0].workflow_memory.workflow_id == "wf1"
        assert ranked[1].workflow_memory.workflow_id == "wf2"
        assert ranked[0].final_score > ranked[1].final_score


class TestWorkflowMemoryModel:
    """Tests for WorkflowMemory data model."""

    def test_workflow_memory_creation(self):
        """WorkflowMemory can be created and serialized."""
        memory = WorkflowMemory(
            workflow_id="wf_123",
            user_request="Test request",
            request_embedding=[0.1, 0.2, 0.3],
            agents_selected=["research_agent", "writer_agent"],
            agent_count=2,
            execution_time_ms=5000,
            total_cost=0.05,
            tokens_used=1500,
            cost_per_second=0.01,
            success=True,
            success_rate=0.95,
            results_summary="Test summary",
            key_outcomes=["report_generated"],
        )

        assert memory.workflow_id == "wf_123"
        assert memory.agent_count == 2
        assert memory.success == True
        assert len(memory.request_embedding) == 3

    def test_workflow_memory_json_serialization(self):
        """WorkflowMemory serializes to JSON correctly."""
        memory = WorkflowMemory(
            workflow_id="wf_123",
            user_request="Test",
            request_embedding=[0.1] * 1536,
            agents_selected=["research_agent"],
            agent_count=1,
            execution_time_ms=1000,
            total_cost=0.01,
            tokens_used=100,
            cost_per_second=0.01,
            success=True,
            success_rate=1.0,
            results_summary="Summary",
        )

        json_str = memory.model_dump_json()
        assert "wf_123" in json_str
        assert "research_agent" in json_str


class TestRetrievalRequest:
    """Tests for retrieval request model."""

    def test_retrieval_request_defaults(self):
        """Retrieval request has sensible defaults."""
        request = RetrievalRequest(query="Test query")

        assert request.query == "Test query"
        assert request.top_k == 3
        assert request.min_similarity == 0.5
        assert request.filter_success_only == False

    def test_retrieval_request_custom_params(self):
        """Retrieval request accepts custom parameters."""
        request = RetrievalRequest(
            query="Test",
            top_k=10,
            min_similarity=0.7,
            filter_success_only=True,
            filter_agents=["research_agent"],
        )

        assert request.top_k == 10
        assert request.min_similarity == 0.7
        assert request.filter_success_only == True
        assert request.filter_agents == ["research_agent"]
