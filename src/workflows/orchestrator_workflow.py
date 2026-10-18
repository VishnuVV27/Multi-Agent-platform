from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Any, List, Optional
import asyncio
import json

from src.agents.base import TaskOutput
from src.workflows.research_workflow import ResearchWorkflow, ResearchWorkflowInput

# These are only used inside @activity.defn functions below, but the imports
# themselves (confluent_kafka's C extension, pydantic-settings reading .env
# via pathlib) trip Temporal's workflow sandbox restrictions if imported
# normally in a file that also defines a @workflow.defn class.
with workflow.unsafe.imports_passed_through():
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
    user_id: str = "default_user"  # For budget tracking
    require_approval: bool = False  # HIG: pause for plan approval before executing
    # Follow-up runs: the parent workflow's final output, injected into root
    # tasks' context so agents revise/extend previous work instead of
    # starting from scratch. Shape: {"previous_results": {...}, "follow_up": True}
    initial_context: Optional[Dict[str, Any]] = None
    # User's optional cap on output tokens per LLM call (the limiter field
    # in the create form) — injected into every task's context
    output_token_limit: Optional[int] = None
    # Enabled skills resolved to per-agent instruction blocks (computed by
    # the API from the skill catalog): {agent_id: instruction_text}
    skill_instructions: Optional[Dict[str, str]] = None


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


# Activity: Track cost against the user's monthly budget
@activity.defn
async def track_budget_cost(cost_data: Dict[str, Any]) -> bool:
    """Record this workflow's cost against the user's monthly budget."""
    try:
        from src.rate_limiting.budget_manager import get_budget_manager

        budget_manager = get_budget_manager()
        budget_manager.track_cost(
            user_id=cost_data.get("user_id", "default_user"),
            workflow_id=cost_data.get("workflow_id"),
            cost=cost_data.get("cost", 0.0),
        )
        return True
    except Exception as e:
        print(f"Failed to track budget cost: {e}")
        # Don't fail the workflow if budget tracking fails
        return False


# Activity: Update the persisted workflow record with final status
@activity.defn
async def update_workflow_status(status_data: Dict[str, Any]) -> bool:
    """Mark the workflow's DB record as completed or failed."""
    try:
        from src.workflow_store import mark_workflow_finished

        return await mark_workflow_finished(
            workflow_id=status_data.get("workflow_id"),
            status=status_data.get("status", "failed"),
            total_cost=status_data.get("total_cost", 0.0),
            total_tokens=status_data.get("total_tokens", 0),
            execution_time_ms=status_data.get("execution_time_ms", 0),
            error_message=status_data.get("error_message"),
            quality_score=status_data.get("quality_score"),
        )
    except Exception as e:
        print(f"Failed to update workflow status: {e}")
        return False


# Activity: Set workflow status without touching final metrics
@activity.defn
async def set_workflow_status_activity(status_data: Dict[str, Any]) -> bool:
    """Update the workflow's in-flight status (e.g. waiting_approval)."""
    try:
        from src.workflow_store import set_workflow_status

        return await set_workflow_status(
            workflow_id=status_data.get("workflow_id"),
            status=status_data.get("status", "running"),
        )
    except Exception as e:
        print(f"Failed to set workflow status: {e}")
        return False


# Activity: Create a plan-approval request (HIG)
@activity.defn
async def create_plan_approval(approval_data: Dict[str, Any]) -> str:
    """Create an approval request for the Supervisor's plan and return its ID."""
    from src.approval.service import get_approval_service

    service = get_approval_service()
    approval = await service.create_approval_request(
        workflow_id=approval_data["workflow_id"],
        task_id="plan",
        agent_id="supervisor_agent",
        action="plan_approval",
        description=(
            f"Execute {len(approval_data.get('tasks', []))}-agent plan for: "
            f"{approval_data.get('user_request', '')[:200]}"
        ),
        context={
            "tasks": approval_data.get("tasks", []),
            "agents_selected": approval_data.get("agents_selected", []),
        },
    )
    return approval["approval_id"]


# Activity: Record a single agent's execution for observability/evaluation
@activity.defn
async def record_agent_run(run_data: Dict[str, Any]) -> bool:
    """Persist an AgentRun row for this agent execution."""
    try:
        from datetime import datetime
        from src.infrastructure.database import get_db
        from src.models.agent_run import AgentRun
        import asyncio as _asyncio
        import uuid as _uuid

        def _insert():
            db = get_db()
            try:
                db.add(AgentRun(
                    id=_uuid.uuid4(),
                    workflow_id=run_data["workflow_id"],
                    agent_id=run_data["agent_id"],
                    agent_name=run_data.get("agent_name"),
                    task_input=run_data.get("task_input", ""),
                    task_output=run_data.get("task_output"),
                    status=run_data.get("status", "completed"),
                    duration_ms=run_data.get("duration_ms"),
                    tokens_used=run_data.get("tokens_used"),
                    cost=run_data.get("cost"),
                    success=run_data.get("success", False),
                    error_message=run_data.get("error_message"),
                    prompt_version=run_data.get("prompt_version"),
                    created_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                ))
                db.commit()
            finally:
                db.close()

        loop = _asyncio.get_event_loop()
        await loop.run_in_executor(None, _insert)
        return True
    except Exception as e:
        print(f"Failed to record agent run: {e}")
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

    def __init__(self) -> None:
        # Set by the approval_signal handler when a human decides on the plan
        self._approval_decision: Optional[Dict[str, Any]] = None

    @workflow.signal
    def approval_signal(self, decision: Dict[str, Any]) -> None:
        """
        Human approval decision from the API.

        decision: {"approved": bool, "approved_by": str, "reason": str}
        """
        self._approval_decision = decision

    @workflow.run
    async def execute(self, input_data: OrchestratorWorkflowInput) -> OrchestratorWorkflowOutput:
        """Execute the task DAG."""
        # workflow.now() (not time.time()) — Temporal's workflow sandbox
        # restricts real wall-clock access since it must be deterministic
        # across replay; workflow.now() is replay-safe.
        workflow_id = input_data.workflow_id
        user_request = input_data.user_request
        agents_selected = input_data.agents_selected
        tasks = input_data.tasks

        # HIG plan-approval gate: pause the whole DAG until a human approves
        # the Supervisor's plan (Temporal keeps the workflow durably parked —
        # this is the "Plan Approval" type from the HIG design).
        if input_data.require_approval:
            await workflow.execute_activity(
                set_workflow_status_activity,
                {"workflow_id": workflow_id, "status": "waiting_approval"},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            approval_id = await workflow.execute_activity(
                create_plan_approval,
                {
                    "workflow_id": workflow_id,
                    "user_request": user_request,
                    "tasks": tasks,
                    "agents_selected": agents_selected,
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            await workflow.execute_activity(
                publish_kafka_event,
                {
                    "event_type": "approval_created",
                    "workflow_id": workflow_id,
                    "approval_id": approval_id,
                    "action": "plan_approval",
                },
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Park until the API signals a decision (1 hour timeout)
            try:
                await workflow.wait_condition(
                    lambda: self._approval_decision is not None,
                    timeout=timedelta(hours=1),
                )
            except asyncio.TimeoutError:
                pass

            decision = self._approval_decision or {}
            if not decision.get("approved", False):
                reason = (
                    decision.get("reason", "rejected by user")
                    if decision
                    else "approval timed out after 1 hour"
                )
                await workflow.execute_activity(
                    update_workflow_status,
                    {
                        "workflow_id": workflow_id,
                        "status": "rejected",
                        "error_message": f"Plan not approved: {reason}",
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                await workflow.execute_activity(
                    publish_kafka_event,
                    {
                        "event_type": "approval_rejected",
                        "workflow_id": workflow_id,
                        "approval_id": approval_id,
                        "reason": reason,
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return OrchestratorWorkflowOutput(
                    workflow_id=workflow_id,
                    tasks_completed=0,
                    tasks_failed=0,
                    results={"rejected": True, "reason": reason},
                )

            # Approved — resume execution
            await workflow.execute_activity(
                set_workflow_status_activity,
                {"workflow_id": workflow_id, "status": "running"},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            await workflow.execute_activity(
                publish_kafka_event,
                {
                    "event_type": "approval_approved",
                    "workflow_id": workflow_id,
                    "approval_id": approval_id,
                    "approved_by": decision.get("approved_by", "unknown"),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
        task_results = {}
        tasks_completed = 0
        tasks_failed = 0
        workflow_error: Optional[str] = None
        # Accumulated directly from each TaskOutput rather than read from the
        # CostTracker singleton: Temporal's workflow sandbox gives workflow
        # code an isolated module namespace, so a `get_cost_tracker()` call
        # here would see an empty instance completely disconnected from the
        # one activities actually record usage into.
        total_cost = 0.0
        total_tokens = 0
        execution_start_time = workflow.now()

        # ---- Parallel DAG scheduler ----
        # Waves: every pending task whose dependencies are all satisfied runs
        # CONCURRENTLY (asyncio.gather is deterministic inside Temporal
        # workflows — the SDK's event loop replays task ordering). Each wave
        # finishes before the next is scheduled. On failure the workflow
        # records the error and skips dependents, but siblings already running
        # in the same wave complete (their cost is real either way).
        pending = {t.get("id"): t for t in tasks}
        any_failed = False

        while pending:
            ready = [
                t for t in pending.values()
                if all(dep in task_results for dep in (t.get("depends_on") or []))
            ]
            if not ready:
                if workflow_error is None:
                    workflow_error = "Unresolvable dependencies in task DAG"
                break

            wave_outcomes = await asyncio.gather(
                *(self._run_task(input_data, t, task_results) for t in ready)
            )

            for task_id, outcome in wave_outcomes:
                pending.pop(task_id, None)
                if outcome["success"]:
                    task_results[task_id] = outcome["task_result"]
                    tasks_completed += 1
                    total_cost += outcome["cost"]
                    total_tokens += outcome["tokens"]
                else:
                    any_failed = True
                    tasks_failed += 1
                    workflow_error = outcome["error"]

            if any_failed:
                # Don't schedule downstream work built on failed tasks, but
                # still run finalization below so cost tracking, memory, and
                # the workflow's status record aren't silently skipped.
                break

        # ---- Quality gate: one revision pass when the critic says revise ----
        # If the plan included a critic and it scored the report below the
        # bar, run the writer once more (draft + critique as context) and
        # re-review. Bounded to a single loop so a harsh judge can't burn
        # budget indefinitely.
        quality_score: Optional[float] = None
        if not any_failed:
            critic_task = next((t for t in tasks if t.get("agent") == "critic_agent"), None)
            writer_task = next((t for t in tasks if t.get("agent") == "writer_agent"), None)
            critic_result = task_results.get(critic_task["id"]) if critic_task else None

            if critic_result and critic_result.result:
                quality_score = critic_result.result.get("overall_score")

                if (
                    critic_result.result.get("verdict") == "revise"
                    and writer_task is not None
                ):
                    # Revision context: the critic's feedback plus everything
                    # the original writer saw (sources), plus the draft itself
                    revision_deps = [
                        dep for dep in (writer_task.get("depends_on") or [])
                        if dep in task_results
                    ] + [writer_task["id"], critic_task["id"]]

                    rev_id, rev_outcome = await self._run_task(
                        input_data,
                        {
                            "id": "t_rev",
                            "agent": "writer_agent",
                            "input": (
                                f"Revise the report about: {user_request}. "
                                "A quality reviewer found problems — you will receive the "
                                "previous draft and the critique. Address every point in "
                                "the critique; keep what the reviewer praised."
                            ),
                            "depends_on": revision_deps,
                        },
                        task_results,
                    )
                    if rev_outcome["success"]:
                        task_results[rev_id] = rev_outcome["task_result"]
                        tasks_completed += 1
                        total_cost += rev_outcome["cost"]
                        total_tokens += rev_outcome["tokens"]

                        # Re-review the revised draft against the same evidence
                        recheck_deps = [
                            dep for dep in (critic_task.get("depends_on") or [])
                            if dep in task_results and dep != writer_task["id"]
                        ] + [rev_id]
                        recheck_id, recheck_outcome = await self._run_task(
                            input_data,
                            {
                                "id": "t_recheck",
                                "agent": "critic_agent",
                                "input": critic_task.get("input"),
                                "depends_on": recheck_deps,
                            },
                            task_results,
                        )
                        if recheck_outcome["success"]:
                            task_results[recheck_id] = recheck_outcome["task_result"]
                            tasks_completed += 1
                            total_cost += recheck_outcome["cost"]
                            total_tokens += recheck_outcome["tokens"]
                            quality_score = (
                                recheck_outcome["task_result"].result or {}
                            ).get("overall_score", quality_score)

        # Calculate execution metrics
        execution_time_ms = int((workflow.now() - execution_start_time).total_seconds() * 1000)
        # total_cost / total_tokens were accumulated above from each TaskOutput
        # as tasks completed — see the note where they're initialized.

        # Generate results summary
        workflow_success = workflow_error is None
        results_summary = f"Executed {tasks_completed} agents successfully"
        if tasks_failed > 0:
            results_summary += f" ({tasks_failed} failed)"

        # Save workflow memory for RAG learning
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
                "error_message": workflow_error,
                "key_outcomes": [
                    f"{tasks_completed} tasks completed",
                    f"Cost: ${total_cost:.4f}",
                    f"Tokens: {total_tokens}",
                ],
            },
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Track cost against the user's monthly budget
        await workflow.execute_activity(
            track_budget_cost,
            {
                "user_id": input_data.user_id,
                "workflow_id": workflow_id,
                "cost": total_cost,
            },
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Update the persisted workflow record (dashboard reads this)
        await workflow.execute_activity(
            update_workflow_status,
            {
                "workflow_id": workflow_id,
                "status": "completed" if workflow_success else "failed",
                "total_cost": total_cost,
                "total_tokens": total_tokens,
                "execution_time_ms": execution_time_ms,
                "error_message": workflow_error,
                "quality_score": quality_score,
            },
            start_to_close_timeout=timedelta(seconds=30),
        )

        if workflow_error:
            # ApplicationError (not a bare Exception) is required here: Temporal
            # treats an unhandled plain Exception raised from workflow code as
            # a workflow TASK failure (a possible bug in the workflow itself)
            # and retries the task indefinitely with backoff, rather than
            # terminally failing the workflow execution. non_retryable=True
            # because per-task retries already happened at the activity/child
            # workflow level above.
            raise ApplicationError(workflow_error, non_retryable=True)

        # Return aggregated results
        return OrchestratorWorkflowOutput(
            workflow_id=workflow_id,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            results=task_results,
        )

    async def _run_task(
        self,
        input_data: OrchestratorWorkflowInput,
        task: Dict[str, Any],
        task_results: Dict[str, TaskOutput],
    ) -> tuple:
        """
        Full lifecycle for one task: started event → agent child workflow →
        completed/failed event → agent_run record.

        Never raises — returns (task_id, outcome) so a failing task in a
        parallel wave doesn't cancel its siblings mid-flight.
        """
        workflow_id = input_data.workflow_id
        task_id = task.get("id")
        agent_id = task.get("agent")
        task_instruction = task.get("input")
        depends_on = task.get("depends_on", [])
        agent_start_time = workflow.now()

        try:
            # Collect dependency results so downstream agents build on
            # upstream work (the whole point of a multi-agent pipeline).
            # Waves only schedule tasks whose deps are already in
            # task_results, so no waiting is needed here.
            previous_results: Dict[str, Any] = {}
            if depends_on:
                for dep_task_id in depends_on:
                    dep_output = task_results.get(dep_task_id)
                    if dep_output is None:
                        raise Exception(f"Dependency {dep_task_id} not found")
                    if dep_output.result:
                        previous_results[dep_task_id] = dep_output.result
            elif input_data.initial_context:
                # Root task of a follow-up run: seed it with the parent
                # workflow's output so this thread continues prior work.
                previous_results.update(
                    input_data.initial_context.get("previous_results", {})
                )

            await workflow.execute_activity(
                publish_kafka_event,
                {
                    "event_type": "agent_started",
                    "workflow_id": workflow_id,
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "status": "started",
                },
                start_to_close_timeout=timedelta(seconds=30),
            )

            task_context: Dict[str, Any] = {}
            if previous_results:
                task_context["previous_results"] = previous_results
            if input_data.output_token_limit:
                task_context["max_output_tokens"] = input_data.output_token_limit
            if input_data.skill_instructions and agent_id in input_data.skill_instructions:
                task_context["skill_instructions"] = input_data.skill_instructions[agent_id]

            task_result = await self._execute_agent_workflow(
                agent_id,
                task_id,
                workflow_id,
                task_instruction,
                task_context,
            )

            # Agents report failure via TaskOutput.status rather than raising
            # (see BaseAgent.execute_with_contract_validation) — a normal
            # return is NOT necessarily a success.
            if task_result.status.value == "failed":
                raise Exception(
                    task_result.error.get("message") if task_result.error else "Agent reported failure"
                )

            agent_duration_ms = int((workflow.now() - agent_start_time).total_seconds() * 1000)
            # Cost/tokens come from the TaskOutput contract, not the
            # CostTracker singleton (workflow sandbox isolation — see the
            # note where totals are initialized in execute()).
            agent_cost = (task_result.metadata or {}).get("llm_cost", 0.0) or 0.0
            agent_tokens = (task_result.tokens_used or {}).get("total", 0) or 0

            await workflow.execute_activity(
                publish_kafka_event,
                {
                    "event_type": "agent_completed",
                    "workflow_id": workflow_id,
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "status": "completed",
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            await workflow.execute_activity(
                record_agent_run,
                {
                    "workflow_id": workflow_id,
                    "agent_id": agent_id,
                    "agent_name": agent_id.replace("_", " ").title(),
                    "task_input": task_instruction,
                    "task_output": json.dumps(task_result.result) if task_result.result else None,
                    "status": "completed",
                    "duration_ms": agent_duration_ms,
                    "cost": agent_cost,
                    "tokens_used": agent_tokens,
                    "success": True,
                    "prompt_version": (task_result.metadata or {}).get("prompt_version"),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )

            return (task_id, {
                "success": True,
                "task_result": task_result,
                "cost": agent_cost,
                "tokens": agent_tokens,
            })

        except Exception as e:
            agent_duration_ms = int((workflow.now() - agent_start_time).total_seconds() * 1000)

            await workflow.execute_activity(
                publish_kafka_event,
                {
                    "event_type": "agent_failed",
                    "workflow_id": workflow_id,
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            await workflow.execute_activity(
                record_agent_run,
                {
                    "workflow_id": workflow_id,
                    "agent_id": agent_id,
                    "agent_name": agent_id.replace("_", " ").title() if agent_id else "Unknown",
                    "task_input": task_instruction,
                    "status": "failed",
                    "duration_ms": agent_duration_ms,
                    "success": False,
                    "error_message": str(e),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )

            return (task_id, {"success": False, "error": str(e)})

    async def _execute_agent_workflow(
        self,
        agent_id: str,
        task_id: str,
        workflow_id: str,
        instruction: str,
        context: Dict[str, Any],
    ) -> TaskOutput:
        """
        Execute the appropriate agent workflow based on agent_id.
        (See _run_task for the full per-task lifecycle wrapper.)

        Supports: research_agent, analysis_agent, coding_agent, writer_agent

        `context` carries upstream task results (previous_results) so each
        agent builds on the pipeline instead of working from the raw prompt.
        """
        # Bounded so a persistent failure (bad API key, broken prompt) fails
        # the task in minutes rather than retrying against Temporal's default
        # (effectively unlimited) retry policy.
        child_retry_policy = RetryPolicy(maximum_attempts=2)

        if agent_id == "research_agent":
            return await workflow.execute_child_workflow(
                ResearchWorkflow.execute,
                ResearchWorkflowInput(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    instruction=instruction,
                    context=context,
                ),
                retry_policy=child_retry_policy,
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
                    context=context,
                ),
                retry_policy=child_retry_policy,
            )

        elif agent_id == "coding_agent":
            # Import coding workflow dynamically
            from src.workflows.coding_workflow import CodingWorkflow, CodingWorkflowInput
            return await workflow.execute_child_workflow(
                CodingWorkflow.execute,
                CodingWorkflowInput(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    instruction=instruction,
                    context=context,
                ),
                retry_policy=child_retry_policy,
            )

        elif agent_id == "critic_agent":
            # Import critic workflow dynamically
            from src.workflows.critic_workflow import CriticWorkflow, CriticWorkflowInput
            return await workflow.execute_child_workflow(
                CriticWorkflow.execute,
                CriticWorkflowInput(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    instruction=instruction,
                    context=context,
                ),
                retry_policy=child_retry_policy,
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
                    context=context,
                ),
                retry_policy=child_retry_policy,
            )

        else:
            raise Exception(f"Unknown agent: {agent_id}")
