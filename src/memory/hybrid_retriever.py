"""
Hybrid Retriever: BM25 + Dense Search + Reranking.

Two-stage retrieval for optimal workflow matching:
1. Candidate generation (BM25 + dense)
2. Reranking (hybrid scoring)
"""

import logging
import time
import asyncio
from typing import List, Optional
from sqlalchemy import text, func

from src.infrastructure.database import get_db
from src.models.memory import WorkflowMemoryORM
from src.memory.models import WorkflowMemory, RankedWorkflow
from src.memory.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid search with BM25 + dense retrieval + reranking."""

    # Weights for final scoring
    WEIGHT_RELEVANCE = 0.5
    WEIGHT_SUCCESS = 0.3
    WEIGHT_COST = 0.2

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def retrieve(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 3,
        min_similarity: float = 0.5,
        filter_success_only: bool = False,
        filter_agents: Optional[List[str]] = None,
    ) -> List[RankedWorkflow]:
        """
        Retrieve top-K similar workflows using hybrid search.

        Process:
        1. BM25 search (keyword matching) → top-20
        2. Dense search (vector similarity) → top-20
        3. Merge candidates + remove duplicates → top-50
        4. Rerank by: relevance + success + cost
        5. Return top-K

        Args:
            query: User query string
            query_embedding: Pre-computed query embedding
            top_k: Return top K results (default: 3)
            min_similarity: Minimum similarity threshold (0-1)
            filter_success_only: Only return successful workflows
            filter_agents: Filter by specific agent combinations

        Returns:
            List of RankedWorkflow objects, ranked by score
        """
        start_time = time.time()

        try:
            db = get_db()

            # Stage 1: Candidate Generation (run in executor)
            loop = asyncio.get_event_loop()

            # BM25 Search (keyword matching)
            bm25_candidates = await loop.run_in_executor(
                None,
                self._bm25_search_sync,
                query,
                20,
                filter_success_only,
            )
            logger.debug(f"BM25 search returned {len(bm25_candidates)} candidates")

            # Dense Search (vector similarity)
            dense_candidates = await loop.run_in_executor(
                None,
                self._dense_search_sync,
                query_embedding,
                20,
                min_similarity,
                filter_success_only,
            )
            logger.debug(f"Dense search returned {len(dense_candidates)} candidates")

            # Merge candidates (remove duplicates)
            candidate_pool = self._merge_candidates(bm25_candidates, dense_candidates)
            logger.debug(f"Merged to {len(candidate_pool)} unique candidates")

            # Filter by agents if specified
            if filter_agents:
                candidate_pool = [
                    c
                    for c in candidate_pool
                    if any(agent in c.agents_selected for agent in filter_agents)
                ]
                logger.debug(
                    f"After agent filter: {len(candidate_pool)} candidates"
                )

            # Stage 2: Reranking
            rerank_start = time.time()
            ranked_results = await self._rerank_candidates(
                query, query_embedding, candidate_pool
            )
            rerank_time_ms = (time.time() - rerank_start) * 1000

            logger.debug(f"Reranking took {rerank_time_ms:.1f}ms")

            # Return top-K
            results = ranked_results[:top_k]

            total_time_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Hybrid retrieval: {len(results)} results in {total_time_ms:.1f}ms"
            )

            return results

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []

    def _bm25_search_sync(
        self,
        query: str,
        limit: int = 20,
        filter_success_only: bool = False,
    ) -> List[WorkflowMemory]:
        """
        BM25 full-text search using PostgreSQL full-text search.

        Keyword matching for precise results.

        Args:
            query: Search query
            limit: Max results to return
            filter_success_only: Only successful workflows

        Returns:
            List of WorkflowMemory objects
        """
        db = get_db()
        try:
            # For now, use simple keyword matching
            # Future: implement proper BM25 with tsvector/tsquery
            sql_query = """
            SELECT * FROM workflow_memories
            WHERE user_request ILIKE :query_pattern
            """

            if filter_success_only:
                sql_query += " AND success = true"

            sql_query += " LIMIT :limit"

            query_pattern = f"%{query}%"

            result = db.execute(
                text(sql_query), {"query_pattern": query_pattern, "limit": limit}
            ).mappings()

            memories = []
            for row in result:
                memory = self._row_to_memory(row)
                if memory:
                    memories.append(memory)

            logger.debug(f"BM25 found {len(memories)} results for: {query[:50]}")
            return memories

        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []
        finally:
            db.close()

    def _dense_search_sync(
        self,
        query_embedding: List[float],
        limit: int = 20,
        min_similarity: float = 0.5,
        filter_success_only: bool = False,
    ) -> List[WorkflowMemory]:
        """
        Dense vector similarity search using pgvector.

        Semantic matching for related requests.

        Args:
            query_embedding: Query embedding vector
            limit: Max results
            min_similarity: Minimum cosine similarity (0-1)
            filter_success_only: Only successful workflows

        Returns:
            List of WorkflowMemory objects
        """
        db = get_db()
        try:
            # Vector similarity search with cosine distance
            max_distance = 1.0 - min_similarity

            sql_query = """
            SELECT *
            FROM workflow_memories
            WHERE (request_embedding <=> :embedding::vector) < :max_distance
            """

            if filter_success_only:
                sql_query += " AND success = true"

            sql_query += """
            ORDER BY request_embedding <=> :embedding::vector ASC
            LIMIT :limit
            """

            result = db.execute(
                text(sql_query),
                {
                    "embedding": query_embedding,
                    "max_distance": max_distance,
                    "limit": limit,
                },
            ).mappings()

            memories = []
            for row in result:
                memory = self._row_to_memory(row)
                if memory:
                    memories.append(memory)

            logger.debug(f"Dense search found {len(memories)} results")
            return memories

        except Exception as e:
            logger.warning(f"Dense search failed: {e}")
            return []
        finally:
            db.close()

    def _merge_candidates(
        self,
        bm25_results: List[WorkflowMemory],
        dense_results: List[WorkflowMemory],
    ) -> List[WorkflowMemory]:
        """
        Merge BM25 and dense results, removing duplicates.

        Preserves order (BM25 first, then new from dense).

        Args:
            bm25_results: Results from BM25 search
            dense_results: Results from dense search

        Returns:
            Merged list with no duplicates
        """
        seen_ids = set()
        merged = []

        # Add BM25 results first (higher relevance)
        for result in bm25_results:
            if result.workflow_id not in seen_ids:
                merged.append(result)
                seen_ids.add(result.workflow_id)

        # Add new dense results
        for result in dense_results:
            if result.workflow_id not in seen_ids:
                merged.append(result)
                seen_ids.add(result.workflow_id)

        return merged

    async def _rerank_candidates(
        self,
        query: str,
        query_embedding: List[float],
        candidates: List[WorkflowMemory],
    ) -> List[RankedWorkflow]:
        """
        Rerank candidates using hybrid scoring.

        Combines:
        - Relevance: cosine similarity + BM25 score
        - Success: success_rate bonus
        - Cost: cost efficiency bonus

        Args:
            query: Original query string
            query_embedding: Query embedding vector
            candidates: Candidate workflows to rerank

        Returns:
            Ranked workflows sorted by final score (highest first)
        """
        ranked = []

        for candidate in candidates:
            # Relevance Score: blend cosine similarity + BM25
            cosine_sim = self._cosine_similarity(query_embedding, candidate)
            # BM25 score (0-1 approximation based on agents matching)
            bm25_score = self._approximate_bm25_score(query, candidate)

            relevance_score = 0.7 * cosine_sim + 0.3 * bm25_score

            # Success bonus: higher success rate = higher score
            success_bonus = min(candidate.success_rate, 1.0) * self.WEIGHT_SUCCESS

            # Cost efficiency bonus: lower cost = higher bonus
            # Normalize: cost_per_second from 0 to ~0.1, so 1/cost gives 10+
            cost_efficiency = 1.0 / (candidate.cost_per_second + 0.01)
            cost_bonus = min(cost_efficiency / 10.0, 1.0) * self.WEIGHT_COST

            # Final score
            final_score = (
                relevance_score * self.WEIGHT_RELEVANCE
                + success_bonus
                + cost_bonus
            )

            ranked.append(
                RankedWorkflow(
                    workflow_memory=candidate,
                    relevance_score=relevance_score,
                    success_bonus=success_bonus,
                    cost_bonus=cost_bonus,
                    final_score=final_score,
                )
            )

        # Sort by final score (descending)
        ranked.sort(key=lambda x: x.final_score, reverse=True)

        return ranked

    @staticmethod
    def _cosine_similarity(embedding1: List[float], memory: WorkflowMemory) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: Query embedding
            memory: WorkflowMemory with embedding

        Returns:
            Cosine similarity (0-1)
        """
        if not memory.request_embedding:
            return 0.0

        embedding2 = memory.request_embedding

        # Dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))

        # Magnitudes
        mag1 = sum(a * a for a in embedding1) ** 0.5
        mag2 = sum(b * b for b in embedding2) ** 0.5

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    @staticmethod
    def _approximate_bm25_score(query: str, memory: WorkflowMemory) -> float:
        """
        Approximate BM25 score for candidate.

        Simple approximation: check how many query words
        appear in request and agents.

        Args:
            query: Query string
            memory: WorkflowMemory

        Returns:
            BM25 approximation (0-1)
        """
        query_words = set(query.lower().split())
        request_words = set(memory.user_request.lower().split())
        agent_words = set(
            word.lower()
            for agent in memory.agents_selected
            for word in agent.split("_")
        )

        matching_request = len(query_words & request_words)
        matching_agents = len(query_words & agent_words)

        total_matches = matching_request + matching_agents * 2  # Agents weighted higher

        # Normalize: assume max ~10 relevant matches
        return min(total_matches / 10.0, 1.0)

    @staticmethod
    def _row_to_memory(row: dict) -> Optional[WorkflowMemory]:
        """Convert database row to WorkflowMemory."""
        try:
            return WorkflowMemory(
                id=str(row["id"]),
                workflow_id=row["workflow_id"],
                user_request=row["user_request"],
                request_embedding=row.get("request_embedding"),
                agents_selected=row.get("agents_selected", []),
                agent_count=row.get("agent_count", 0),
                execution_time_ms=row.get("execution_time_ms", 0),
                total_cost=row.get("total_cost", 0.0),
                tokens_used=row.get("tokens_used", 0),
                cost_per_second=row.get("cost_per_second", 0.0),
                success=row.get("success", False),
                success_rate=row.get("success_rate", 0.0),
                error_message=row.get("error_message"),
                results_summary=row.get("results_summary", ""),
                key_outcomes=row.get("key_outcomes", []),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
        except Exception as e:
            logger.error(f"Failed to convert row to WorkflowMemory: {e}")
            return None
