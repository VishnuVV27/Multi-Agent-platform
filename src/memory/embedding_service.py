"""
Embedding Service: Generate and cache embeddings via LiteLLM.

Uses OpenAI's text-embedding-3-small (1536 dimensions) with Redis caching.
Anthropic does not offer a public embeddings API, so this cannot use Claude.
"""

import json
import hashlib
import logging
from typing import List, Optional, Dict

from src.infrastructure.redis_client import get_redis_client
from src.llm.gateway import get_llm_gateway

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages embeddings for workflow memory via LiteLLM (OpenAI)."""

    EMBEDDING_CACHE_TTL = 86400 * 7  # 7 days
    EMBEDDING_DIM = 1536

    def __init__(self):
        self.redis_client = get_redis_client()
        self.llm_gateway = get_llm_gateway()

    async def embed_request(self, request: str) -> List[float]:
        """
        Embed a user request to 1536-dimensional vector.

        Strategy:
        1. Check Redis cache
        2. If miss, call the embeddings API
        3. Cache result for 7 days

        Args:
            request: User request text

        Returns:
            1536-dimensional embedding vector
        """
        # Create cache key from request hash
        cache_key = self._get_cache_key(request)

        # Try Redis cache first
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"Embedding cache HIT for: {request[:50]}...")
                embedding = json.loads(cached)
                return embedding
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")

        # Cache miss: call the embeddings API
        try:
            logger.debug(f"Embedding cache MISS, calling embeddings API: {request[:50]}...")
            embedding = await self._call_embedding_api(request)

            # Cache the result
            try:
                self.redis_client.setex(
                    cache_key,
                    self.EMBEDDING_CACHE_TTL,
                    json.dumps(embedding),
                )
            except Exception as e:
                logger.warning(f"Redis cache write failed: {e}")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def embed_batch(self, requests: List[str]) -> List[List[float]]:
        """
        Batch embed multiple requests efficiently.

        For each request, check cache first. Only call API for cache misses,
        then combine results.

        Args:
            requests: List of request strings

        Returns:
            List of embedding vectors
        """
        # Track each request's embedding by its original index, deduping repeated
        # texts within the batch so they only hit the cache/API once.
        result: List[Optional[List[float]]] = [None] * len(requests)
        indices_by_text: Dict[str, List[int]] = {}
        for i, request in enumerate(requests):
            indices_by_text.setdefault(request, []).append(i)

        cache_misses = []

        # Check cache once per unique request text
        for request, indices in indices_by_text.items():
            cache_key = self._get_cache_key(request)
            try:
                cached = self.redis_client.get(cache_key)
            except Exception as e:
                logger.warning(f"Redis read failed: {e}")
                cached = None

            if cached:
                embedding = json.loads(cached)
                for i in indices:
                    result[i] = embedding
            else:
                cache_misses.append(request)

        logger.info(
            f"Batch embedding: {len(indices_by_text) - len(cache_misses)} hits, "
            f"{len(cache_misses)} misses ({len(requests)} total requests)"
        )

        # Call API for cache misses (each unique missing text once)
        if cache_misses:
            try:
                api_results = await self._call_embedding_api_batch(cache_misses)

                for request, embedding in zip(cache_misses, api_results):
                    for i in indices_by_text[request]:
                        result[i] = embedding

                    cache_key = self._get_cache_key(request)
                    try:
                        self.redis_client.setex(
                            cache_key,
                            self.EMBEDDING_CACHE_TTL,
                            json.dumps(embedding),
                        )
                    except Exception as e:
                        logger.warning(f"Redis cache write failed: {e}")

            except Exception as e:
                logger.error(f"Batch embedding API call failed: {e}")
                raise

        return result

    async def embed_summary(self, summary: str) -> List[float]:
        """
        Embed a workflow results summary.

        Same as embed_request but for results to enable
        similarity search on outcomes.

        Args:
            summary: Workflow results summary

        Returns:
            1536-dimensional embedding
        """
        return await self.embed_request(summary)

    async def _call_embedding_api(self, text: str) -> List[float]:
        """
        Call the embedding API via LiteLLM (OpenAI text-embedding-3-small —
        Anthropic has no public embeddings endpoint).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = await self.llm_gateway.embed(text=text)

            # LiteLLM returns: {"data": [{"embedding": [...]}], "model": "..."}
            if "data" in response and len(response["data"]) > 0:
                embedding = response["data"][0].get("embedding")
                if embedding:
                    return embedding

            raise ValueError(f"Invalid embedding response: {response}")

        except Exception as e:
            logger.error(f"Embedding API call failed: {e}")
            raise

    async def _call_embedding_api_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Call embedding API for multiple texts.

        Uses LiteLLM batch processing if available,
        otherwise loops with concurrency.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings
        """
        embeddings = []

        # For now, embed sequentially (can optimize with concurrent.futures later)
        for text in texts:
            try:
                embedding = await self._call_embedding_api(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to embed text '{text[:50]}...': {e}")
                raise

        return embeddings

    @staticmethod
    def _get_cache_key(text: str) -> str:
        """
        Generate cache key for embedding.

        Uses SHA256 hash of text for consistency.

        Args:
            text: Text to hash

        Returns:
            Cache key: f"embedding:{hash}"
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"embedding:{text_hash}"

    async def warmup_cache(self, requests: List[str]) -> int:
        """
        Pre-warm embedding cache with batch of requests.

        Useful for initialization or migration.

        Args:
            requests: List of requests to pre-embed

        Returns:
            Number of embeddings generated/cached
        """
        try:
            await self.embed_batch(requests)
            logger.info(f"Warmed embedding cache with {len(requests)} requests")
            return len(requests)
        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")
            return 0
