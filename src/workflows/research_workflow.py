from temporalio import workflow, activity
from dataclasses import dataclass
from typing import Dict, Any

from src.agents.base import TaskInput, TaskOutput
from src.agents.research_agent import ResearchAgent


@dataclass
class ResearchWorkflowInput:
    """Input to Research Agent workflow."""
    task_id: str
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = None


# Activity: Execute Research Agent
@activity.defn
async def run_research_activity(input_data: ResearchWorkflowInput) -> TaskOutput:
    """Execute Research Agent as a Temporal activity."""
    agent = ResearchAgent()

    task_input = TaskInput(
        task_id=input_data.task_id,
        workflow_id=input_data.workflow_id,
        instruction=input_data.instruction,
        context=input_data.context or {},
    )

    output = await agent.execute_with_contract_validation(task_input)
    return output


# Workflow: Research Workflow
@workflow.defn
class ResearchWorkflow:
    """Temporal workflow for Research Agent execution."""

    @workflow.run
    async def execute(self, input_data: ResearchWorkflowInput) -> TaskOutput:
        """Execute research task."""
        output = await workflow.execute_activity(
            run_research_activity,
            input_data,
            start_to_close_timeout=300,
        )
        return output
