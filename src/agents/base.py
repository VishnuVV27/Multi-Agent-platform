from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
import uuid


class AgentStatus(str, Enum):
    """Agent execution status."""
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(str, Enum):
    """Agent capabilities for discovery and matching."""
    WEB_SEARCH = "web_search"
    DOCUMENT_ANALYSIS = "document_analysis"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    WRITING = "writing"
    PLANNING = "planning"


class TaskInput(BaseModel):
    """Standard input contract for agent tasks."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)  # e.g., max_tokens, deadline
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskOutput(BaseModel):
    """Standard output contract for agent results."""
    task_id: str
    workflow_id: str
    status: AgentStatus
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[Dict[str, int]] = None  # {input_tokens, output_tokens}


class AgentEvent(BaseModel):
    """Standard event published by agents to Kafka."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str  # agent.started, agent.completed, agent.failed, agent.progress
    workflow_id: str
    agent_id: str
    task_id: str
    status: AgentStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all agents. Every agent must subclass this and implement execute().

    This enforces the Agent Contract:
    - Consistent input/output shapes (TaskInput/TaskOutput)
    - Capability declaration for registry discovery
    - Allowed tools specification for permission enforcement
    - Standardized error handling
    """

    # Must be set by subclass
    AGENT_ID: str
    AGENT_NAME: str
    DESCRIPTION: str
    CAPABILITIES: List[AgentCapability] = []
    ALLOWED_TOOLS: List[str] = []
    VERSION: str = "1.0.0"

    def __init__(self):
        """Initialize agent with dependency injection."""
        self.agent_id = self.AGENT_ID
        self.agent_name = self.AGENT_NAME
        self.capabilities = self.CAPABILITIES
        self.allowed_tools = self.ALLOWED_TOOLS

    @abstractmethod
    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute the agent's task. Must be implemented by subclass.

        Args:
            task_input: Standard task input with instruction and context

        Returns:
            TaskOutput: Standard task output with result or error

        This is the only method subclasses must implement.
        All other infrastructure (tool access, LLM calls, etc.) goes through gateways.
        """
        pass

    async def execute_with_contract_validation(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute task with input validation and error handling.
        Wraps the actual execute() method to ensure contract compliance.
        """
        try:
            # Validate input
            validated_input = TaskInput(**task_input.dict())

            # Execute agent logic
            output = await self.execute(validated_input)

            # Validate output
            validated_output = TaskOutput(**output.dict())

            return validated_output

        except Exception as e:
            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.FAILED,
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "retryable": self._is_retryable_error(e),
                },
            )

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """Determine if an error is retryable."""
        retryable_errors = ("TimeoutError", "ConnectionError", "TemporaryError")
        return type(error).__name__ in retryable_errors

    def get_manifest(self) -> Dict[str, Any]:
        """Return agent metadata for registry."""
        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "description": self.DESCRIPTION,
            "version": self.VERSION,
            "capabilities": [cap.value for cap in self.CAPABILITIES],
            "allowed_tools": self.ALLOWED_TOOLS,
        }


# Registry of all agents (populated as agents are defined)
AGENT_REGISTRY: Dict[str, BaseAgent] = {}


def register_agent(agent_class: type) -> type:
    """Decorator to register an agent in the global registry."""
    if not issubclass(agent_class, BaseAgent):
        raise TypeError(f"{agent_class} must be a subclass of BaseAgent")

    agent = agent_class()
    AGENT_REGISTRY[agent.AGENT_ID] = agent
    return agent_class


def get_agent(agent_id: str) -> Optional[BaseAgent]:
    """Get an agent from the registry."""
    return AGENT_REGISTRY.get(agent_id)


def list_agents() -> Dict[str, Dict[str, Any]]:
    """List all registered agents with their manifests."""
    return {
        agent_id: agent.get_manifest()
        for agent_id, agent in AGENT_REGISTRY.items()
    }
