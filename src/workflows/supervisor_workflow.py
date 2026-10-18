from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Any, List

from src.agents.base import TaskInput, TaskOutput


@dataclass
class SupervisorWorkflowInput:
    """Input to the Supervisor workflow."""
    workflow_id: str
    user_prompt: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SupervisorWorkflowOutput:
    """Output from the Supervisor workflow."""
    workflow_id: str
    tasks: List[Dict[str, Any]]
    planning_method: str
    agents_selected: List[str] = field(default_factory=list)


# Activity: Execute Supervisor Agent
@activity.defn
async def run_supervisor_activity(input_data: SupervisorWorkflowInput) -> SupervisorWorkflowOutput:
    """
    Activity that executes the Supervisor Agent.

    Temporal separates workflows (deterministic, retry-able logic) from activities (non-deterministic, external calls).
    Running the agent here as an activity ensures Temporal can retry it if needed.
    """
    # Imported locally: SupervisorAgent pulls in litellm -> httpx -> urllib,
    # which Temporal's workflow sandbox restricts if imported at module level
    # in a file that also defines a @workflow.defn class.
    from src.agents.supervisor_agent import SupervisorAgent

    supervisor = SupervisorAgent()

    # Create task input for Supervisor
    task_input = TaskInput(
        workflow_id=input_data.workflow_id,
        instruction=input_data.user_prompt,
        context=input_data.context or {},
    )

    # Execute Supervisor Agent
    task_output = await supervisor.execute_with_contract_validation(task_input)

    # Check if execution was successful
    if task_output.status.value != "completed":
        raise Exception(f"Supervisor failed: {task_output.error}")

    # Extract tasks from result
    tasks = task_output.result.get("tasks", [])

    return SupervisorWorkflowOutput(
        workflow_id=input_data.workflow_id,
        tasks=tasks,
        planning_method=task_output.result.get("planning_method", "unknown"),
        agents_selected=task_output.result.get("agents_selected", []),
    )


# Workflow: Supervisor Workflow
@workflow.defn
class SupervisorWorkflow:
    """
    Temporal workflow that executes the Supervisor Agent.

    Workflow responsibilities:
    1. Receive user prompt
    2. Execute Supervisor Agent activity
    3. Return task DAG to the orchestrator workflow

    This is deterministic and can be retried/replayed by Temporal.
    """

    @workflow.run
    async def execute(self, input_data: SupervisorWorkflowInput) -> SupervisorWorkflowOutput:
        """
        Main workflow entrypoint.

        Args:
            input_data: Supervisor workflow input with user prompt

        Returns:
            Task DAG ready for execution by orchestrator
        """
        # Execute the Supervisor Agent as an activity
        # This allows Temporal to manage retries and replay
        output = await workflow.execute_activity(
            run_supervisor_activity,
            input_data,
            start_to_close_timeout=timedelta(seconds=300),  # 5 minute timeout
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        return output
