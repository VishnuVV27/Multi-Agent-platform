"""
Live agent progress: the plumbing behind Mission Control's live monitors.

Agents report phases ("Searching the web…") and streaming LLM previews while
they work. Delivery is two-channel:

- Redis:  hash `progress:{workflow_id}`  → snapshot for late-joining clients
          channel `progress_channel:{workflow_id}` → real-time pub/sub that
          the SSE endpoint forwards to the browser
- Kafka:  `agent.progress` topic → the observability contract (durable,
          replayable, for any consumer — dashboards never talk to agents)

Everything here is best-effort: a progress failure must never fail a task.
"""

import json
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PROGRESS_TTL_SECONDS = 3600


def _publish_sync(
    workflow_id: str,
    agent_id: str,
    phase: str,
    detail: str = "",
    preview: str = "",
) -> None:
    """Write the progress event to Redis (snapshot + pub/sub). Never raises."""
    try:
        from src.infrastructure.redis_client import get_redis_client

        payload = {
            "agent_id": agent_id,
            "phase": phase,
            "detail": detail,
            "preview": preview,
            "ts": time.time(),
        }
        data = json.dumps(payload)
        r = get_redis_client()
        r.hset(f"progress:{workflow_id}", agent_id, data)
        r.expire(f"progress:{workflow_id}", PROGRESS_TTL_SECONDS)
        r.publish(f"progress_channel:{workflow_id}", data)
    except Exception as e:
        logger.debug(f"Progress publish skipped: {e}")


async def report_progress(
    workflow_id: str,
    agent_id: str,
    phase: str,
    detail: str = "",
    preview: str = "",
) -> None:
    """
    Report a progress phase from inside an agent.

    Redis for real-time UI delivery, Kafka for the observability stream.
    """
    _publish_sync(workflow_id, agent_id, phase, detail, preview)

    try:
        from src.infrastructure.kafka_client import publish_event
        from src.config import settings

        await publish_event(
            settings.KAFKA_TOPICS["agent_progress"],
            {
                "event_type": "agent_progress",
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "phase": phase,
                "detail": detail,
            },
        )
    except Exception as e:
        logger.debug(f"Kafka progress publish skipped: {e}")


def make_llm_stream_reporter(
    workflow_id: str,
    agent_id: str,
    phase: str,
    interval_seconds: float = 0.4,
    preview_chars: int = 400,
) -> Callable[[str], None]:
    """
    Build a throttled on_chunk callback for LLMGateway.generate(stream).

    Publishes the tail of the accumulated generation to Redis at most every
    `interval_seconds` — Mission Control renders it as text appearing on the
    agent's holographic monitor. (Redis only: per-chunk Kafka events would
    flood the topic for no observability gain.)
    """
    state = {"last": 0.0}

    def on_chunk(full_text: str) -> None:
        now = time.time()
        if now - state["last"] < interval_seconds:
            return
        state["last"] = now
        _publish_sync(
            workflow_id, agent_id, phase,
            preview=full_text[-preview_chars:],
        )

    return on_chunk
