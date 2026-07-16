"""
Memory Store: PostgreSQL storage for workflow memories using pgvector.

Handles CRUD operations, full-text search (BM25), and vector search.
"""

import logging
from datetime import datetime
from typing import List, Optional
import asyncio
from sqlalchemy import text, func

from src.infrastructure.database import get_db
from src.models.memory import WorkflowMemoryORM
from src.memory.models import WorkflowMemory, RetrievalRequest, RetrievalResponse
from src.memory.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class MemoryStore:
    """PostgreSQL-backed storage for workflow memories."""

    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def save_workflow_memory(
        self,
        workflow_id: str,
        user_request: str,
        agents_selected: List[str],
        execution_time_ms: int,
        total_cost: float,
        tokens_used: int,
        success: bool,
        results_summary: str,
        error_message: Optional[str] = None,
        key_outcomes: Optional[List[str]] = None,
    ) -> WorkflowMemory:
        """
        Save a completed workflow to memory.

        Steps:
        1. Generate embedding from user request
        2. Calculate cost efficiency
        3. Store in PostgreSQL with embedding

        Args:
            workflow_id: Unique workflow ID
            user_request: Original user request
            agents_selected: List of agent IDs used
            execution_time_ms: Total execution time
            total_cost: Total cost in USD
            tokens_used: Total tokens consumed
            success: Did workflow succeed?
            results_summary: Summary of results
            error_message: Error if failed
            key_outcomes: List of key outcomes

        Returns:
            Stored WorkflowMemory
        """
        try:
            # Generate embedding
            logger.debug(f"Generating embedding for workflow {workflow_id}")
            request_embedding = await self.embedding_service.embed_request(
                user_request
            )

            # Calculate cost efficiency
            cost_per_second = (
                total_cost / (execution_time_ms / 1000)
                if execution_time_ms > 0
                else 0.0
            )

            # Save to database in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            memory_orm = await loop.run_in_executor(
                None,
                self._save_to_db,
                workflow_id,
                user_request,
                request_embedding,
                agents_selected,
                execution_time_ms,
                total_cost,
                tokens_used,
                cost_per_second,
                success,
                error_message,
                results_summary,
                key_outcomes,
            )

            logger.info(f"Saved workflow memory: {workflow_id}")

            # Convert ORM to Pydantic
            return self._orm_to_model(memory_orm)

        except Exception as e:
            logger.error(f"Failed to save workflow memory: {e}")
            raise

    @staticmethod
    def _save_to_db(
        workflow_id: str,
        user_request: str,
        request_embedding: List[float],
        agents_selected: List[str],
        execution_time_ms: int,
        total_cost: float,
        tokens_used: int,
        cost_per_second: float,
        success: bool,
        error_message: Optional[str],
        results_summary: str,
        key_outcomes: Optional[List[str]],
    ) -> WorkflowMemoryORM:
        """Synchronous database save operation."""
        db = get_db()
        try:
            memory_orm = WorkflowMemoryORM(
                workflow_id=workflow_id,
                user_request=user_request,
                request_embedding=request_embedding,
                agents_selected=agents_selected,
                agent_count=len(agents_selected),
                execution_time_ms=execution_time_ms,
                total_cost=total_cost,
                tokens_used=tokens_used,
                cost_per_second=cost_per_second,
                success=success,
                success_rate=1.0 if success else 0.0,
                error_message=error_message,
                results_summary=results_summary,
                key_outcomes=key_outcomes or [],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            db.add(memory_orm)
            db.commit()
            db.refresh(memory_orm)
            return memory_orm
        finally:
            db.close()

    async def retrieve_workflows(
        self,
        request: RetrievalRequest,
    ) -> RetrievalResponse:
        """
        Retrieve top-K similar workflows using hybrid search.

        Steps:
        1. Generate query embedding
        2. BM25 search (keyword matching)
        3. Dense search (vector similarity)
        4. Merge candidates
        5. Rerank by relevance + success + cost
        6. Return top-K

        Args:
            request: Retrieval request with query and filters

        Returns:
            RetrievalResponse with ranked workflows
        """
        import time
        from src.memory.hybrid_retriever import HybridRetriever

        start_time = time.time()

        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.embed_request(request.query)

            # Retrieve using hybrid search
            retriever = HybridRetriever(self.embedding_service)
            ranked_results = await retriever.retrieve(
                query=request.query,
                query_embedding=query_embedding,
                top_k=request.top_k,
                min_similarity=request.min_similarity,
                filter_success_only=request.filter_success_only,
                filter_agents=request.filter_agents,
            )

            retrieval_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Retrieved {len(ranked_results)} workflows in {retrieval_time_ms:.1f}ms"
            )

            return RetrievalResponse(
                query=request.query,
                results=ranked_results,
                retrieval_time_ms=retrieval_time_ms,
                sparse_results_count=0,  # Populated by retriever
                dense_results_count=0,  # Populated by retriever
                candidate_pool_size=0,  # Populated by retriever
                took_rerank_time_ms=0,  # Populated by retriever
            )

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            raise

    async def get_workflow_memory(self, workflow_id: str) -> Optional[WorkflowMemory]:
        """
        Get a specific workflow memory by ID.

        Args:
            workflow_id: Workflow ID to retrieve

        Returns:
            WorkflowMemory or None
        """
        try:
            loop = asyncio.get_event_loop()
            memory_orm = await loop.run_in_executor(
                None, self._get_from_db, workflow_id
            )
            if not memory_orm:
                return None
            return self._orm_to_model(memory_orm)
        except Exception as e:
            logger.error(f"Failed to get workflow memory: {e}")
            return None

    @staticmethod
    def _get_from_db(workflow_id: str) -> Optional[WorkflowMemoryORM]:
        """Synchronous database get operation."""
        db = get_db()
        try:
            return db.query(WorkflowMemoryORM).filter_by(
                workflow_id=workflow_id
            ).first()
        finally:
            db.close()

    async def get_memory_statistics(self) -> dict:
        """
        Get statistics about stored memories.

        Returns dict with:
        - total_workflows: Total stored workflows
        - success_count: Successful workflows
        - failure_count: Failed workflows
        - avg_cost: Average cost per workflow
        - avg_tokens: Average tokens used
        - avg_execution_time_ms: Average execution time
        """
        try:
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, self._get_stats_from_db)
            return stats
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    @staticmethod
    def _get_stats_from_db() -> dict:
        """Synchronous database stats operation."""
        db = get_db()
        try:
            total = db.query(func.count(WorkflowMemoryORM.id)).scalar() or 0
            success_count = (
                db.query(func.count(WorkflowMemoryORM.id))
                .filter(WorkflowMemoryORM.success == True)
                .scalar()
                or 0
            )
            failure_count = total - success_count

            avg_cost = (
                db.query(func.avg(WorkflowMemoryORM.total_cost)).scalar() or 0.0
            )
            avg_tokens = (
                db.query(func.avg(WorkflowMemoryORM.tokens_used)).scalar() or 0
            )
            avg_time = (
                db.query(func.avg(WorkflowMemoryORM.execution_time_ms)).scalar() or 0
            )

            return {
                "total_workflows": total,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_count / total if total > 0 else 0.0,
                "avg_cost": float(avg_cost),
                "avg_tokens": int(avg_tokens),
                "avg_execution_time_ms": int(avg_time),
            }
        finally:
            db.close()

    async def delete_old_memories(self, days_old: int = 90) -> int:
        """
        Delete workflow memories older than specified days.

        Useful for pruning old low-value memories and keeping DB size manageable.

        Args:
            days_old: Delete memories older than this many days

        Returns:
            Number of memories deleted
        """
        try:
            loop = asyncio.get_event_loop()
            deleted = await loop.run_in_executor(None, self._delete_old_from_db, days_old)
            logger.info(f"Deleted {deleted} memories older than {days_old} days")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete old memories: {e}")
            return 0

    @staticmethod
    def _delete_old_from_db(days_old: int) -> int:
        """Synchronous database delete operation."""
        from datetime import timedelta

        db = get_db()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            deleted_count = (
                db.query(WorkflowMemoryORM)
                .filter(WorkflowMemoryORM.created_at < cutoff_date)
                .delete()
            )
            db.commit()
            return deleted_count
        finally:
            db.close()

    @staticmethod
    def _orm_to_model(orm_obj: WorkflowMemoryORM) -> WorkflowMemory:
        """Convert ORM object to Pydantic model."""
        return WorkflowMemory(
            id=str(orm_obj.id),
            workflow_id=orm_obj.workflow_id,
            user_request=orm_obj.user_request,
            request_embedding=orm_obj.request_embedding,
            agents_selected=orm_obj.agents_selected,
            agent_count=orm_obj.agent_count,
            execution_time_ms=orm_obj.execution_time_ms,
            total_cost=orm_obj.total_cost,
            tokens_used=orm_obj.tokens_used,
            cost_per_second=orm_obj.cost_per_second,
            success=orm_obj.success,
            success_rate=orm_obj.success_rate,
            error_message=orm_obj.error_message,
            results_summary=orm_obj.results_summary,
            key_outcomes=orm_obj.key_outcomes,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )
