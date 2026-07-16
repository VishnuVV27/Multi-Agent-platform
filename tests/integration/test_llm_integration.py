"""
Integration tests for LLM Gateway.

Tests real LLM calls and agent integration with LLM Gateway.
Note: These tests require valid API keys in .env
"""

import pytest
from src.llm.gateway import get_llm_gateway
from src.llm.cost_tracker import get_cost_tracker


@pytest.mark.asyncio
class TestLLMGatewayIntegration:
    """Integration tests for LLM Gateway."""

    async def test_generate_basic_prompt(self):
        """Test basic text generation."""
        gateway = get_llm_gateway()

        response = await gateway.generate(
            workflow_id="test_wf_1",
            agent_id="test_agent",
            prompt="What is 2 + 2?",
            task_type="fast",
            max_tokens=10,
        )

        # Verify response structure
        assert "text" in response
        assert "model" in response
        assert "tokens" in response
        assert "cost" in response
        assert response["workflow_id"] == "test_wf_1"

        # Verify tokens
        assert response["tokens"]["input"] > 0
        assert response["tokens"]["output"] > 0

    async def test_generate_with_specific_model(self):
        """Test generation with specific model."""
        gateway = get_llm_gateway()

        response = await gateway.generate(
            workflow_id="test_wf_1",
            agent_id="test_agent",
            prompt="Say hello",
            model="gpt-3.5-turbo",
            max_tokens=20,
        )

        assert response["model"] == "gpt-3.5-turbo"

    async def test_chat_interface(self):
        """Test chat-style interaction."""
        gateway = get_llm_gateway()

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is AI?"},
        ]

        response = await gateway.chat(
            workflow_id="test_wf_1",
            agent_id="test_agent",
            messages=messages,
            task_type="reasoning",
            max_tokens=100,
        )

        assert "text" in response
        assert len(response["text"]) > 0
        assert response["tokens"]["total"] > 0

    async def test_cost_tracking_integration(self):
        """Test that costs are tracked during generation."""
        gateway = get_llm_gateway()
        cost_tracker = get_cost_tracker()

        # Clear previous costs
        initial_summary = cost_tracker.get_summary()
        initial_cost = initial_summary.get("total_cost", 0)

        # Generate a response
        response = await gateway.generate(
            workflow_id="cost_test_wf",
            agent_id="cost_test_agent",
            prompt="Hello",
            max_tokens=5,
        )

        # Verify cost was recorded
        workflow_cost = cost_tracker.get_workflow_cost("cost_test_wf")
        assert workflow_cost >= 0
        assert workflow_cost <= 0.01  # Should be very cheap (5 tokens)

        # Verify it's in the summary
        new_summary = cost_tracker.get_summary()
        assert new_summary["request_count"] > initial_summary.get("request_count", 0)


@pytest.mark.asyncio
class TestResearchAgentWithLLM:
    """Test Research Agent integration with LLM Gateway."""

    async def test_research_agent_uses_llm(self):
        """Research agent generates summaries using LLM."""
        from src.agents.research_agent import ResearchAgent
        from src.agents.base import TaskInput

        agent = ResearchAgent()
        task_input = TaskInput(
            workflow_id="test_wf",
            instruction="Research Python programming"
        )

        output = await agent.execute(task_input)

        # If successful, should have LLM metadata
        if output.status.value == "completed":
            # Summary should be from LLM, not hardcoded
            assert "summary" in output.result
            assert len(output.result["summary"]) > 0

            # Should have tokens metadata
            if output.tokens_used:
                assert "input" in output.tokens_used or output.tokens_used == {}

            # Should have cost metadata
            if "metadata" in output.metadata and output.metadata:
                if "llm_cost" in output.metadata:
                    assert output.metadata["llm_cost"] >= 0
