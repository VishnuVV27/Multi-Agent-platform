"""
LLM Model definitions and routing configurations.

Defines:
- Available models and providers
- Model capabilities and costs
- Routing rules (which model for which task)
- Fallback chains
"""

from enum import Enum
from typing import Dict, Any, List
from dataclasses import dataclass


class Provider(str, Enum):
    """LLM Provider."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class ModelCapability(str, Enum):
    """Model capability levels."""
    BASIC = "basic"  # Simple tasks, cheap
    REASONING = "reasoning"  # Complex reasoning, moderate cost
    ADVANCED = "advanced"  # Advanced reasoning, expensive
    VISION = "vision"  # Image understanding


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    name: str  # Model ID (e.g., gpt-4, claude-3-opus)
    provider: Provider
    capability: ModelCapability
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    max_input_tokens: int
    max_output_tokens: int
    fallback_model: str | None = None


# Available models
MODELS: Dict[str, ModelConfig] = {
    # OpenAI models
    "gpt-4.1-nano": ModelConfig(
        name="gpt-4.1-nano",
        provider=Provider.OPENAI,
        capability=ModelCapability.BASIC,
        input_cost_per_1k_tokens=0.0001,
        output_cost_per_1k_tokens=0.0004,
        max_input_tokens=1047576,
        max_output_tokens=32768,
        fallback_model="gpt-3.5-turbo",
    ),
    "gpt-4": ModelConfig(
        name="gpt-4",
        provider=Provider.OPENAI,
        capability=ModelCapability.ADVANCED,
        input_cost_per_1k_tokens=0.03,
        output_cost_per_1k_tokens=0.06,
        max_input_tokens=8192,
        max_output_tokens=2048,
        fallback_model="gpt-3.5-turbo",
    ),
    "gpt-4-turbo": ModelConfig(
        name="gpt-4-turbo-preview",
        provider=Provider.OPENAI,
        capability=ModelCapability.ADVANCED,
        input_cost_per_1k_tokens=0.01,
        output_cost_per_1k_tokens=0.03,
        max_input_tokens=128000,
        max_output_tokens=4096,
        fallback_model="gpt-3.5-turbo",
    ),
    "gpt-3.5-turbo": ModelConfig(
        name="gpt-3.5-turbo",
        provider=Provider.OPENAI,
        capability=ModelCapability.REASONING,
        input_cost_per_1k_tokens=0.0015,
        output_cost_per_1k_tokens=0.002,
        max_input_tokens=4096,
        max_output_tokens=2048,
    ),
    # Anthropic models
    "claude-3-opus": ModelConfig(
        name="claude-3-opus-20240229",
        provider=Provider.ANTHROPIC,
        capability=ModelCapability.ADVANCED,
        input_cost_per_1k_tokens=0.015,
        output_cost_per_1k_tokens=0.075,
        max_input_tokens=200000,
        max_output_tokens=4096,
        fallback_model="claude-3-sonnet",
    ),
    "claude-3-sonnet": ModelConfig(
        name="claude-3-sonnet-20240229",
        provider=Provider.ANTHROPIC,
        capability=ModelCapability.REASONING,
        input_cost_per_1k_tokens=0.003,
        output_cost_per_1k_tokens=0.015,
        max_input_tokens=200000,
        max_output_tokens=4096,
    ),
    "claude-3-haiku": ModelConfig(
        name="claude-3-haiku-20240307",
        provider=Provider.ANTHROPIC,
        capability=ModelCapability.BASIC,
        input_cost_per_1k_tokens=0.00025,
        output_cost_per_1k_tokens=0.00125,
        max_input_tokens=200000,
        max_output_tokens=4096,
    ),
}

# Default models for different task types — all routed to gpt-4.1-nano
# (cheapest/fastest current tier) per user request. Swap individual entries
# back to a heavier model (e.g. "gpt-4-turbo") if quality suffers for
# reasoning-heavy agents like the supervisor or writer.
MODEL_ROUTING: Dict[str, str] = {
    "reasoning": "gpt-4.1-nano",
    "coding": "gpt-4.1-nano",
    "fast": "gpt-4.1-nano",
    "default": "gpt-4.1-nano",
}

# Model routing by capability level
CAPABILITY_MODELS: Dict[ModelCapability, List[str]] = {
    ModelCapability.BASIC: ["gpt-3.5-turbo", "claude-3-haiku"],
    ModelCapability.REASONING: ["gpt-3.5-turbo", "gpt-4-turbo", "claude-3-sonnet"],
    ModelCapability.ADVANCED: ["gpt-4", "gpt-4-turbo", "claude-3-opus"],
    ModelCapability.VISION: ["gpt-4-vision"],
}


def get_model_config(model_id: str) -> ModelConfig | None:
    """Get configuration for a model."""
    return MODELS.get(model_id)


def get_model_for_capability(capability: ModelCapability) -> str:
    """Get the best available model for a capability."""
    models = CAPABILITY_MODELS.get(capability, [])
    return models[0] if models else "gpt-3.5-turbo"


def get_model_for_task(task_type: str) -> str:
    """Get model for a specific task type."""
    return MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])
