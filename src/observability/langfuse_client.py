"""
Langfuse Client: Trace LLM calls with cost, latency, and token metrics.

Integrates with Langfuse Cloud for LLM observability.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import time

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None

from src.config import settings

logger = logging.getLogger(__name__)


class LangfuseClient:
    """
    Langfuse integration for LLM tracing.

    Traces every LLM call with:
    - Model name and provider
    - Prompt version
    - Input/output tokens
    - Cost
    - Latency
    - Workflow/agent context
    """

    def __init__(self, public_key: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Initialize Langfuse client.

        Args:
            public_key: Langfuse public key (from settings if not provided)
            secret_key: Langfuse secret key (from settings if not provided)
        """
        self.public_key = public_key or settings.LANGFUSE_PUBLIC_KEY
        self.secret_key = secret_key or settings.LANGFUSE_SECRET_KEY
        self.enabled = bool(self.public_key and self.secret_key)

        if self.enabled and Langfuse:
            try:
                self.client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
                self.enabled = False
        else:
            logger.warning("Langfuse disabled: missing API keys or langfuse package")
            self.client = None

    def trace_llm_call(
        self,
        workflow_id: str,
        agent_id: str,
        model: str,
        prompt: str,
        output: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: int,
        prompt_version: str = "1.0",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Trace an LLM call to Langfuse.

        Args:
            workflow_id: Workflow ID
            agent_id: Agent making the call
            model: Model used (e.g., "claude-3.5-sonnet")
            prompt: User prompt
            output: Model output
            input_tokens: Input token count
            output_tokens: Output token count
            cost: Cost in USD
            latency_ms: Latency in milliseconds
            prompt_version: Version of prompt used
            metadata: Additional metadata

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            trace_id = f"{workflow_id}-{agent_id}-{int(time.time() * 1000)}"

            self.client.trace(
                id=trace_id,
                name=f"{agent_id}:llm_call",
                metadata={
                    "workflow_id": workflow_id,
                    "agent_id": agent_id,
                    "model": model,
                    "prompt_version": prompt_version,
                    **(metadata or {}),
                },
            )

            # Log the LLM generation
            self.client.generation(
                trace_id=trace_id,
                name=f"llm_generation:{model}",
                input=[{"role": "user", "content": prompt}],
                output={"text": output},
                model=model,
                usage={
                    "input": input_tokens,
                    "output": output_tokens,
                },
                cost={
                    "input": cost * (input_tokens / (input_tokens + output_tokens)),
                    "output": cost * (output_tokens / (input_tokens + output_tokens)),
                },
                end_time=datetime.utcnow(),
                duration_ms=latency_ms,
            )

            logger.debug(f"Traced LLM call: {trace_id}")
            return trace_id

        except Exception as e:
            logger.error(f"Failed to trace LLM call: {e}")
            return None

    def trace_workflow(
        self,
        workflow_id: str,
        user_request: str,
        agents: List[str],
        duration_ms: int,
        cost: float,
        tokens: int,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Trace a complete workflow execution.

        Args:
            workflow_id: Workflow ID
            user_request: Original user request
            agents: Agents used
            duration_ms: Total duration
            cost: Total cost
            tokens: Total tokens
            success: Did workflow succeed?
            metadata: Additional metadata

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            self.client.trace(
                id=workflow_id,
                name="workflow:execution",
                metadata={
                    "user_request": user_request,
                    "agents": agents,
                    "agent_count": len(agents),
                    "success": success,
                    "tokens": tokens,
                    "cost": cost,
                    "duration_ms": duration_ms,
                    **(metadata or {}),
                },
            )

            logger.debug(f"Traced workflow: {workflow_id}")
            return workflow_id

        except Exception as e:
            logger.error(f"Failed to trace workflow: {e}")
            return None

    def trace_agent_execution(
        self,
        workflow_id: str,
        agent_id: str,
        task_input: str,
        task_output: str,
        duration_ms: int,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Trace an agent execution within a workflow.

        Args:
            workflow_id: Workflow ID
            agent_id: Agent ID
            task_input: Agent task input
            task_output: Agent output
            duration_ms: Execution duration
            success: Did agent succeed?
            metadata: Additional metadata

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            trace_id = f"{workflow_id}-{agent_id}"

            self.client.span(
                trace_id=workflow_id,
                name=f"agent:{agent_id}",
                input={"task": task_input},
                output={"result": task_output},
                metadata={
                    "agent_id": agent_id,
                    "success": success,
                    "duration_ms": duration_ms,
                    **(metadata or {}),
                },
            )

            logger.debug(f"Traced agent execution: {trace_id}")
            return trace_id

        except Exception as e:
            logger.error(f"Failed to trace agent execution: {e}")
            return None

    def flush(self) -> None:
        """Flush pending traces to Langfuse."""
        if self.enabled and self.client:
            try:
                self.client.flush()
                logger.debug("Langfuse traces flushed")
            except Exception as e:
                logger.error(f"Failed to flush Langfuse: {e}")


# Global Langfuse client
_langfuse_client: Optional[LangfuseClient] = None


def get_langfuse_client() -> LangfuseClient:
    """Get the global Langfuse client."""
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = LangfuseClient()
    return _langfuse_client
