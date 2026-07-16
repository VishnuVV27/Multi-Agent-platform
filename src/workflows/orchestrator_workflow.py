from temporalio import workflow, activity
from dataclasses import dataclass
from typing import Dict, Any, List
import asyncio

from src.agents.base import TaskOutput
from src.workflows.research_workflow import ResearchWorkflow, ResearchWorkflowInput
from src.infrastructure.kafka_client import publish_event
from src.config import settings
import importlib


@dataclass
class OrchestratorWorkflowInput:
    """Input to the Orchestrator workflow."""
    workflow_id: str
    user_request: str  # Original user request (for memory)
    tasks: List[Dict[str, Any]]  # Task DAG from Supervisor
    agents_selected: List[str]  # Agent IDs used (for memory)


@dataclass
class OrchestratorWorkflowOutput:
    """Output from the Orchestrator workflow."""
    workflow_id: str
    tasks_completed: int
    tasks_failed: int
    results: Dict[str, Any]


# Activity: Publish event to Kafka
@activity.defn
async def publish_kafka_event(event_data: Dict[str, Any]) -> bool:
    """Publish an event to Kafka for observability."""
    if not settings.ENABLE_KAFKA_OBSERVABILITY:
        return True

    try:
        topic = event_data.get("event_type")
        if topic:
            full_topic = settings.KAFKA_TOPICS.get(topic, topic)
            await publish_event(full_topic, event_data)
        return True
    except Exception as e:
        print(f"Failed to publish event: {e}")
        return False


# Activity: Save workflow memory
@activity.defn
async def save_workflow_memory(memory_data: Dict[str, Any]) -> bool:
    """Save workflow memory for RAG learning."""
    try:
        from src.memory.memory_store import MemoryStore

        memory_store = MemoryStore()
        await memory_store.save_workflow_memory(
            workflow_id=memory_data.get("workflow_id"),
            user_request=memory_data.get("user_request"),
            agents_selected=memory_data.get("agents_selected", []),
            execution_time_ms=memory_data.get("execution_time_ms", 0),
            total_cost=memory_data.get("total_cost", 0.0),
            tokens_used=memory_data.get("tokens_used", 0),
            success=memory_data.get("success", False),
            results_summary=memory_data.get("results_summary", ""),
            error_message=memory_data.get("error_message"),
            key_outcomes=memory_data.get("key_outcomes", []),
        )
        return True
    except Exception as e:
        print(f"Failed to save workflow memory: {e}")
        # Don't fail the workflow if memory save fails
        return False


# Workflow: Orchestrator
@workflow.defn
class OrchestratorWorkflow:
    """
    Main orchestration workflow that executes the task DAG.

    Workflow:
    1. Receive task DAG from Supervisor
    2. For each task in DAG:
       a. Check dependencies (wait for previous tasks)
       b. Execute appropriate agent workflow
       c. Publish event to Kafka
    3. Aggregate results
    4. Return final output
    """

    @workflow.run
    async def execute(self, input_data: OrchestratorWorkflowInput) -> OrchestratorWorkflowOutput:
        """Execute the task DAG."""
        import time

        workflow_id = input_data.workflow_id
        user_request = input_data.user_request
        agents_selected = input_data.agents_selected
        tasks = input_data.tasks
        task_results = {}
        tasks_completed = 0
        tasks_failed = 0
        execution_start_time = time.time()

        for task in tasks:
            task_id = task.get("id")
            agent_id = task.get("agent")
            task_instruction = task.get("input")
            depends_on = task.get("depends_on", [])

            try:
                # Step 1: Wait for dependencies to complete
                if depends_on:
                    for dep_task_id in depends_on:
                        if dep_task_id not in task_results:
                            raise Exception(f"Dependency {dep_task_id} not found")

                # Step 2: Publish agent.started event
                await workflow.execute_activity(
                    publish_kafka_event,
                    {
                        "event_type": "agent_started",
                        "workflow_id": workflow_id,
                        "agent_id": agent_id,
                        "task_id": task_id,
                        "status": "started",
                    }
                )

                # Step 3: Execute appropriate agent workflow
                task_result = await self._execute_agent_workflow(
                    agent_id,
                    task_id,
                    workflow_id,
                    task_instruction,
                )

                task_results[task_id] = task_result
                tasks_completed += 1

                # Step 4: Publish agent.completed event
                await workflow.execute_activity(
                    publish_kafka_event,
                    {
                        "event_type": "agent_completed",
                        "workflow_id": workflow_id,
                        "agent_id": agent_id,
                        "task_id": task_id,
                        "status": "completed",
                    }
                )

            except Exception as e:
                tasks_failed += 1

                # Publish agent.failed event
                await workflow.execute_activity(
                    publish_kafka_event,
                    {
                        "event_type": "agent_failed",
                        "workflow_id": workflow_id,
                        "agent_id": agent_id,
                        "task_id": task_id,
                        "status": "failed",
                        "error": str(e),
                    }
                )

                raise

        # Calculate execution metrics
        execution_time_ms = int((time.time() - execution_start_time) * 1000)

        # Get workflow cost from cost tracker
        try:
            from src.llm.cost_tracker import get_cost_tracker

            cost_tracker = get_cost_tracker()
            total_cost = cost_tracker.get_workflow_cost(workflow_id)
            total_tokens = cost_tracker.get_workflow_tokens(workflow_id)
        except Exception as e:
            print(f"Failed to get cost metrics: {e}")
            total_cost = 0.0
            total_tokens = 0

        # Generate results summary
        results_summary = f"Executed {tasks_completed} agents successfully"
        if tasks_failed > 0:
            results_summary += f" ({tasks_failed} failed)"

        # Save workflow memory for RAG learning
        workflow_success = tasks_failed == 0
        await workflow.execute_activity(
            save_workflow_memory,
            {
                "workflow_id": workflow_id,
                "user_request": user_request,
                "agents_selected": agents_selected,
                "execution_time_ms": execution_time_ms,
                "total_cost": total_cost,
                "tokens_used": total_tokens,
                "success": workflow_success,
                "results_summary": results_summary,
                "error_message": None if workflow_success else "Some tasks failed",
                "key_outcomes": [
                    f"{tasks_completed} tasks completed",
                    f"Cost: ${total_cost:.4f}",
                    f"Tokens: {total_tokens}",
                ],
            },
        )

        # Return aggregated results
        return OrchestratorWorkflowOutput(
            workflow_id=workflow_id,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            results=task_results,
        )

    async def _execute_agent_workflow(
        self,
        agent_id: str,
        task_id: str,
        workflow_id: str,
        instruction: str,
    ) -> TaskOutput:
        """
        Execute the appropriate agent workflow based on agent_id.

        Supports: research_agent, analysis_agent, writer_agent
        """
        if agent_id == "research_agent":
            return await workflow.execute_child_workflow(
                ResearchWorkflow.execute,
                ResearchWorkflowInput(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    instruction=instruction,
                )
            )

        elif agent_id == "analysis_agent":
            # Import analysis workflow dynamically
            from src.workflows.analysis_workflow import AnalysisWorkflow, AnalysisWorkflowInput
            return await workflow.execute_child_workflow(
                AnalysisWorkflow.execute,
                AnalysisWorkflowInput(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    instruction=instruction,
                )
            )

        elif agent_id == "writer_agent":
            # Import writer workflow dynamically
            from src.workflows.writer_workflow import WriterWorkflow, WriterWorkflowInput
            return await workflow.execute_child_workflow(
                WriterWorkflow.execute,
                WriterWorkflowInput(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    instruction=instruction,
                )
            )

        else:
            raise Exception(f"Unknown agent: {agent_id}")
