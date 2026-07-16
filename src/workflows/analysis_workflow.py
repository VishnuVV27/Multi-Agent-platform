"""
Analysis Workflow: Temporal workflow for Analysis Agent execution.
"""

from temporalio import workflow, activity
from dataclasses import dataclass
from typing import Dict, Any, Optional

from src.agents.base import TaskInput, TaskOutput
from src.agents.analysis_agent import AnalysisAgent


@dataclass
class AnalysisWorkflowInput:
    """Input to Analysis Agent workflow."""
    task_id: str
    workflow_id: str
    instruction: str
    context: Dict[str, Any] = None


# Activity: Execute Analysis Agent
@activity.defn
async def run_analysis_activity(input_data: AnalysisWorkflowInput) -> TaskOutput:
    """Execute Analysis Agent as a Temporal activity."""
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
            start_to_close_timeout=300,
        )
        return output
