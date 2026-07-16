"""
Embedding Service: Generate and cache embeddings using Claude API.

Uses LiteLLM for Claude embeddings with Redis caching.
"""

import json
import hashlib
import logging
from typing import List

from src.infrastructure.redis_client import get_redis_client
from src.llm.gateway import get_llm_gateway

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages embeddings for workflow memory using Claude API."""

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
        2. If miss, call Claude embeddings API
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
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"Embedding cache HIT for: {request[:50]}...")
                embedding = json.loads(cached)
                return embedding
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")

        # Cache miss: call Claude API
        try:
            logger.debug(f"Embedding cache MISS, calling Claude API: {request[:50]}...")
            embedding = await self._call_embedding_api(request)

            # Cache the result
            try:
                await self.redis_client.setex(
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
        embeddings = []
        cache_hits = []
        cache_misses = []
        cache_miss_indices = []

        # Check cache for all requests
        for i, request in enumerate(requests):
            cache_key = self._get_cache_key(request)
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    embeddings.append(json.loads(cached))
                    cache_hits.append(request)
                else:
                    cache_misses.append(request)
                    cache_miss_indices.append(i)
            except Exception as e:
                logger.warning(f"Redis read failed: {e}")
                cache_misses.append(request)
                cache_miss_indices.append(i)

        logger.info(
            f"Batch embedding: {len(cache_hits)} hits, {len(cache_misses)} misses"
        )

        # Call API for cache misses
        if cache_misses:
            try:
                api_results = await self._call_embedding_api_batch(cache_misses)

                # Cache results
                for request, embedding in zip(cache_misses, api_results):
                    cache_key = self._get_cache_key(request)
                    try:
                        await self.redis_client.setex(
                            cache_key,
                            self.EMBEDDING_CACHE_TTL,
                            json.dumps(embedding),
                        )
                    except Exception as e:
                        logger.warning(f"Redis cache write failed: {e}")

            except Exception as e:
                logger.error(f"Batch embedding API call failed: {e}")
                raise

        # Combine results in original order
        result = [None] * len(requests)
        embedding_idx = 0

        for i in range(len(requests)):
            if i in cache_miss_indices:
                result[i] = api_results[cache_miss_indices.index(i)]
            else:
                result[i] = cache_hits[len([x for x in cache_miss_indices if x < i])]

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
        Call Claude embedding API via LiteLLM.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = await self.llm_gateway.embed(text=text, model="claude")

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
