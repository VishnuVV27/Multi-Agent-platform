"""
Writer Workflow: Temporal workflow for Writer Agent execution.
"""

from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Any, Optional

from src.agents.base import TaskInput, TaskOutput


@dataclass
class WriterWorkflowInput:
    """Input to Writer Agent workflow."""
    task_id: str
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = field(default_factory=dict)


# Activity: Execute Writer Agent
@activity.defn
async def run_writer_activity(input_data: WriterWorkflowInput) -> TaskOutput:
    """Execute Writer Agent as a Temporal activity."""
    # Imported locally: see research_workflow.py for why (litellm/httpx import
    # chain trips Temporal's workflow sandbox if imported at module level).
    from src.agents.writer_agent import WriterAgent

    agent = WriterAgent()

    task_input = TaskInput(
        task_id=input_data.task_id,
        workflow_id=input_data.workflow_id,
        instruction=input_data.instruction,
        context=input_data.context or {},
    )

    output = await agent.execute_with_contract_validation(task_input)
    return output


# Workflow: Writer
@workflow.defn
class WriterWorkflow:
    """Temporal workflow for Writer Agent execution."""

    @workflow.run
    async def execute(self, input_data: WriterWorkflowInput) -> TaskOutput:
        """Execute writing task."""
        output = await workflow.execute_activity(
            run_writer_activity,
            input_data,
            start_to_close_timeout=timedelta(seconds=300),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return output
