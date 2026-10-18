"""
Unit tests for LLM Gateway.

Tests model routing, cost tracking, and gateway functionality.
"""

import pytest
from src.llm.models import (
    get_model_config, get_model_for_capability, get_model_for_task,
    ModelCapability, Provider, MODELS, MODEL_ROUTING
)
from src.llm.cost_tracker import CostTracker, get_cost_tracker
from src.llm.gateway import get_llm_gateway


class TestModelConfiguration:
    """Tests for model configuration."""

    def test_get_model_config(self):
        """Can retrieve model configuration."""
        config = get_model_config("gpt-3.5-turbo")
        assert config is not None
        assert config.name == "gpt-3.5-turbo"
        assert config.provider == Provider.OPENAI
        assert config.max_input_tokens > 0
        assert config.max_output_tokens > 0

    def test_unknown_model_returns_none(self):
        """Unknown model returns None."""
        config = get_model_config("unknown-model")
        assert config is None

    def test_model_has_fallback(self):
        """Models have fallback chain configured."""
        gpt4 = get_model_config("gpt-4")
        assert gpt4.fallback_model is not None
        fallback = get_model_config(gpt4.fallback_model)
        assert fallback is not None


class TestModelRouting:
    """Tests for model routing logic."""

    def test_get_model_for_task_reasoning(self):
        """Reasoning task routes to the configured reasoning model."""
        model = get_model_for_task("reasoning")
        assert model == MODEL_ROUTING["reasoning"]
        assert get_model_config(model) is not None

    def test_get_model_for_task_coding(self):
        """Coding task routes to the configured coding model."""
        model = get_model_for_task("coding")
        assert model == MODEL_ROUTING["coding"]
        assert get_model_config(model) is not None

    def test_get_model_for_task_fast(self):
        """Fast task routes to the configured fast model."""
        model = get_model_for_task("fast")
        assert model == MODEL_ROUTING["fast"]
        assert get_model_config(model) is not None

    def test_get_model_for_task_default(self):
        """Unknown task type falls back to the default model."""
        model = get_model_for_task("unknown_task")
        assert model == MODEL_ROUTING["default"]

    def test_get_model_for_capability(self):
        """Get model for specific capability."""
        model = get_model_for_capability(ModelCapability.ADVANCED)
        assert model in ["gpt-4", "gpt-4-turbo", "claude-3-opus"]

    def test_model_capability_chain(self):
        """Models have proper capability levels."""
        basic = get_model_for_capability(ModelCapability.BASIC)
        reasoning = get_model_for_capability(ModelCapability.REASONING)
        advanced = get_model_for_capability(ModelCapability.ADVANCED)

        # All should return valid models
        assert basic is not None
        assert reasoning is not None
        assert advanced is not None


class TestCostTracker:
    """Tests for cost tracking."""

    def test_cost_tracker_records_usage(self):
        """Cost tracker records LLM usage."""
        tracker = CostTracker()
        usage = tracker.record_usage(
            workflow_id="wf_1",
            agent_id="research_agent",
            model="gpt-3.5-turbo",
            input_tokens=100,
            output_tokens=50,
        )

        assert usage["workflow_id"] == "wf_1"
        assert usage["agent_id"] == "research_agent"
        assert usage["model"] == "gpt-3.5-turbo"
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["cost"] > 0

    def test_cost_calculation(self):
        """Cost calculation is correct."""
        tracker = CostTracker()
        # GPT-3.5-turbo: input=$0.0015/1k, output=$0.002/1k
        # 100 input tokens: 100/1000 * 0.0015 = 0.00015
        # 50 output tokens: 50/1000 * 0.002 = 0.0001
        # Total: 0.00025

        usage = tracker.record_usage(
            workflow_id="wf_1",
            agent_id="agent_1",
            model="gpt-3.5-turbo",
            input_tokens=1000,  # 1000 tokens
            output_tokens=1000,  # 1000 tokens
        )

        expected_cost = (1000/1000 * 0.0015) + (1000/1000 * 0.002)
        assert abs(usage["cost"] - expected_cost) < 0.0001

    def test_workflow_cost_aggregation(self):
        """Get total cost for a workflow."""
        tracker = CostTracker()
        tracker.record_usage("wf_1", "agent_1", "gpt-3.5-turbo", 100, 50)
        tracker.record_usage("wf_1", "agent_2", "gpt-3.5-turbo", 200, 100)

        total = tracker.get_workflow_cost("wf_1")
        assert total > 0

    def test_agent_cost_aggregation(self):
        """Get total cost for an agent."""
        tracker = CostTracker()
        tracker.record_usage("wf_1", "agent_1", "gpt-3.5-turbo", 100, 50)
        tracker.record_usage("wf_2", "agent_1", "gpt-3.5-turbo", 200, 100)

        total = tracker.get_agent_cost("agent_1")
        assert total > 0

    def test_model_usage_statistics(self):
        """Get usage statistics for a model."""
        tracker = CostTracker()
        tracker.record_usage("wf_1", "agent_1", "gpt-3.5-turbo", 100, 50)
        tracker.record_usage("wf_1", "agent_1", "gpt-3.5-turbo", 200, 100)

        stats = tracker.get_model_usage("gpt-3.5-turbo")
        assert stats["request_count"] == 2
        assert stats["total_tokens"] == 450  # 100 + 50 + 200 + 100
        assert stats["total_cost"] > 0

    def test_summary(self):
        """Get cost summary."""
        tracker = CostTracker()
        tracker.record_usage("wf_1", "agent_1", "gpt-3.5-turbo", 100, 50)
        tracker.record_usage("wf_2", "agent_2", "gpt-4", 200, 100)

        summary = tracker.get_summary()
        assert summary["request_count"] == 2
        assert summary["total_tokens"] == 450
        assert summary["total_cost"] > 0
        assert "cost_by_model" in summary


class TestLLMGateway:
    """Tests for LLM Gateway (non-async)."""

    def test_gateway_initialization(self):
        """LLM gateway initializes."""
        gateway = get_llm_gateway()
        assert gateway is not None

    def test_gateway_singleton(self):
        """LLM gateway is singleton."""
        gateway1 = get_llm_gateway()
        gateway2 = get_llm_gateway()
        assert gateway1 is gateway2

    def test_cost_summary(self):
        """Gateway provides cost summary."""
        gateway = get_llm_gateway()
        summary = gateway.get_cost_summary()
        assert "total_cost" in summary
        assert "total_tokens" in summary
        assert "request_count" in summary
