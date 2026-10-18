"""
Analysis Workflow: Temporal workflow for Analysis Agent execution.
"""

from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Any, Optional

from src.agents.base import TaskInput, TaskOutput


@dataclass
class AnalysisWorkflowInput:
    """Input to Analysis Agent workflow."""
    task_id: str
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = field(default_factory=dict)


# Activity: Execute Analysis Agent
@activity.defn
async def run_analysis_activity(input_data: AnalysisWorkflowInput) -> TaskOutput:
    """Execute Analysis Agent as a Temporal activity."""
    # Imported locally: see research_workflow.py for why (litellm/httpx import
    # chain trips Temporal's workflow sandbox if imported at module level).
    from src.agents.analysis_agent import AnalysisAgent

    agent = AnalysisAgent()

    task_input = TaskInput(
        task_id=input_data.task_id,
        workflow_id=input_data.workflow_id,
        instruction=input_data.instruction,
        context=input_data.context or {},
    )

    output = await agent.execute_with_contract_validation(task_input)
    return output


# Workflow: Analysis
@workflow.defn
class AnalysisWorkflow:
    """Temporal workflow for Analysis Agent execution."""

    @workflow.run
    async def execute(self, input_data: AnalysisWorkflowInput) -> TaskOutput:
        """Execute analysis task."""
        output = await workflow.execute_activity(
            run_analysis_activity,
            input_data,
            start_to_close_timeout=timedelta(seconds=300),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return output
