from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Any

from src.agents.base import TaskInput, TaskOutput


@dataclass
class CodingWorkflowInput:
    """Input to Coding Agent workflow."""
    task_id: str
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = field(default_factory=dict)


# Activity: Execute Coding Agent
@activity.defn
async def run_coding_activity(input_data: CodingWorkflowInput) -> TaskOutput:
    """Execute Coding Agent as a Temporal activity."""
    # Imported locally (not at module level): CodingAgent pulls in litellm ->
    # httpx -> urllib, which Temporal's workflow sandbox restricts. Since this
    # file also defines a @workflow.defn class, top-level imports here are
    # sandboxed even though only this activity function needs them.
    from src.agents.coding_agent import CodingAgent

    agent = CodingAgent()

    task_input = TaskInput(
        task_id=input_data.task_id,
        workflow_id=input_data.workflow_id,
        instruction=input_data.instruction,
        context=input_data.context or {},
    )

    output = await agent.execute_with_contract_validation(task_input)
    return output


# Workflow: Coding Workflow
@workflow.defn
class CodingWorkflow:
    """Temporal workflow for Coding Agent execution."""

    @workflow.run
    async def execute(self, input_data: CodingWorkflowInput) -> TaskOutput:
        """Execute coding task."""
        output = await workflow.execute_activity(
            run_coding_activity,
            input_data,
            start_to_close_timeout=timedelta(seconds=300),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return output
