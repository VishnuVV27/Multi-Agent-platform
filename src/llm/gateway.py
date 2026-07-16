"""
LLM Gateway: Centralized interface to LLMs using LiteLLM.

Responsibilities:
- Route requests to appropriate model
- Handle provider abstraction (OpenAI, Anthropic, etc.)
- Model fallback on failure
- Token management
- Cost tracking
- Rate limiting integration (placeholder)
"""

from typing import Optional, Dict, Any, List
import litellm
from litellm import completion, acompletion
import asyncio
import time

from src.config import settings
from src.llm.models import get_model_config, get_model_for_task, ModelCapability
from src.llm.cost_tracker import get_cost_tracker


class LLMException(Exception):
    """Exception during LLM call."""
    pass


class LLMGateway:
    """Centralized gateway for all LLM interactions."""

    def __init__(self):
        """Initialize gateway."""
        # Configure LiteLLM
        litellm.drop_params = True
        litellm.set_verbose = settings.LITELLM_LOG

        # Set API keys from environment
        if settings.OPENAI_API_KEY:
            # LiteLLM uses OPENAI_API_KEY env var automatically

            pass

    async def generate(
        self,
        workflow_id: str,
        agent_id: str,
        prompt: str,
        task_type: str = "default",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate text using an LLM.

        Args:
            workflow_id: Workflow ID for tracking
            agent_id: Agent making the request
            prompt: Input prompt
            task_type: Type of task (reasoning, coding, fast, etc.)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            model: Specific model to use (optional, will route if not specified)

        Returns:
            {
                "text": "generated text",
                "model": "model used",
                "tokens": {input, output, total},
                "cost": cost,
                ...
            }
        """
        try:
            # Step 1: Select model if not specified
            if not model:
                model = get_model_for_task(task_type)

            model_config = get_model_config(model)
            if not model_config:
                raise LLMException(f"Unknown model: {model}")

            # Step 2: Prepare request
            max_output_tokens = min(
                max_tokens or 1000,
                model_config.max_output_tokens
            )

            # Step 3: Call LLM through LiteLLM
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_output_tokens,
                temperature=temperature,
                timeout=60,
            )

            # Step 4: Extract response
            generated_text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            # Step 5: Track cost
            cost_tracker = get_cost_tracker()
            cost_data = cost_tracker.record_usage(
                workflow_id=workflow_id,
                agent_id=agent_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            return {
                "text": generated_text,
                "model": model,
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                },
                "cost": cost_data["cost"],
                "workflow_id": workflow_id,
                "agent_id": agent_id,
            }

        except Exception as e:
            # Attempt fallback if available
            model_config = get_model_config(model)
            if model_config and model_config.fallback_model:
                try:
                    return await self.generate(
                        workflow_id=workflow_id,
                        agent_id=agent_id,
                        prompt=prompt,
                        task_type=task_type,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        model=model_config.fallback_model,
                    )
                except Exception as fallback_error:
                    raise LLMException(f"Primary model failed: {e}. Fallback also failed: {fallback_error}")

            raise LLMException(f"LLM request failed: {str(e)}")

    async def chat(
        self,
        workflow_id: str,
        agent_id: str,
        messages: List[Dict[str, str]],
        task_type: str = "default",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Chat-style interaction with LLM (with Langfuse tracing).

        Args:
            workflow_id: Workflow ID
            agent_id: Agent ID
            messages: List of messages [{role, content}, ...]
            task_type: Task type for routing
            max_tokens: Max output tokens
            temperature: Temperature
            model: Specific model (optional)

        Returns:
            Response with generated text and metadata
        """
        try:
            call_start = time.time()

            if not model:
                model = get_model_for_task(task_type)

            model_config = get_model_config(model)
            if not model_config:
                raise LLMException(f"Unknown model: {model}")

            max_output_tokens = min(
                max_tokens or 1000,
                model_config.max_output_tokens
            )

            response = await acompletion(
                model=model,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=temperature,
                timeout=60,
            )

            generated_text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            latency_ms = int((time.time() - call_start) * 1000)

            cost_tracker = get_cost_tracker()
            cost_data = cost_tracker.record_usage(
                workflow_id=workflow_id,
                agent_id=agent_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            # Trace to Langfuse
            if settings.ENABLE_LANGFUSE_TRACING:
                try:
                    from src.observability.langfuse_client import get_langfuse_client
                    langfuse = get_langfuse_client()
                    langfuse.trace_llm_call(
                        workflow_id=workflow_id,
                        agent_id=agent_id,
                        model=model,
                        prompt=messages[-1].get("content", "") if messages else "",
                        output=generated_text,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost_data["cost"],
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    # Don't fail if Langfuse tracing fails
                    pass

            return {
                "text": generated_text,
                "model": model,
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens,
                },
                "cost": cost_data["cost"],
            }

        except Exception as e:
            raise LLMException(f"Chat request failed: {str(e)}")

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary."""
        cost_tracker = get_cost_tracker()
        return cost_tracker.get_summary()

    def get_workflow_cost(self, workflow_id: str) -> float:
        """Get cost for a specific workflow."""
        cost_tracker = get_cost_tracker()
        return cost_tracker.get_workflow_cost(workflow_id)

    async def embed(
        self,
        text: str,
        model: str = "text-embedding-3-small",
    ) -> Dict[str, Any]:
        """
        Generate embeddings using LiteLLM.

        Args:
            text: Text to embed
            model: Embedding model (default: Claude embeddings)

        Returns:
            {"data": [{"embedding": [...]}], "model": "..."}
        """
        try:
            # Use Claude embeddings API via LiteLLM
            response = await litellm.aembedding(
                model="claude",
                input=text,
            )

            return response

        except Exception as e:
            raise LLMException(f"Embedding request failed: {str(e)}")


# Global gateway instance
_llm_gateway = None


def get_llm_gateway() -> LLMGateway:
    """Get the global LLM gateway."""
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway
