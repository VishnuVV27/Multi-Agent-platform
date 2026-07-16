"""
Writer Workflow: Temporal workflow for Writer Agent execution.
"""

from temporalio import workflow, activity
from dataclasses import dataclass
from typing import Dict, Any, Optional

from src.agents.base import TaskInput, TaskOutput
from src.agents.writer_agent import WriterAgent


@dataclass
class WriterWorkflowInput:
    """Input to Writer Agent workflow."""
    task_id: str
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = None


# Activity: Execute Writer Agent
@activity.defn
async def run_writer_activity(input_data: WriterWorkflowInput) -> TaskOutput:
    """Execute Writer Agent as a Temporal activity."""
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
            start_to_close_timeout=300,
        )
        return output
