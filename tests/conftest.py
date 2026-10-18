"""
Pytest configuration and fixtures for all tests.
"""

import pytest
import asyncio
from typing import Generator

from src.agents.base import TaskInput, TaskOutput, AgentStatus
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.research_agent import ResearchAgent
from src.infrastructure.database import init_db
from src.infrastructure.redis_client import init_redis


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def _infra():
    """
    Several "unit" tests exercise real DB/Redis-backed services (approval
    service, embedding cache) rather than pure logic, so they need a live
    Postgres + Redis — same ones docker-compose.yml brings up for local dev,
    and the same two services the CI workflow runs as service containers.
    """
    await init_db()
    await init_redis()


@pytest.fixture
def sample_task_input() -> TaskInput:
    """Create a sample task input for testing."""
    return TaskInput(
        task_id="test_task_1",
        workflow_id="test_workflow_1",
        instruction="Test research on AI trends",
        context={"industry": "technology"},
    )


@pytest.fixture
def supervisor_agent() -> SupervisorAgent:
    """Get Supervisor Agent instance."""
    return SupervisorAgent()


@pytest.fixture
def research_agent() -> ResearchAgent:
    """Get Research Agent instance."""
    return ResearchAgent()


@pytest.fixture
def sample_task_output() -> TaskOutput:
    """Create a sample task output for testing."""
    return TaskOutput(
        task_id="test_task_1",
        workflow_id="test_workflow_1",
        status=AgentStatus.COMPLETED,
        result={
            "query": "AI trends",
            "findings": ["Finding 1", "Finding 2"],
        },
    )
