"""
Temporal Worker: Registers workflows and activities with Temporal.

Run this in a separate process/container alongside the FastAPI app.
The worker receives tasks from Temporal and executes them.

Usage:
    python -m src.workers.temporal_worker
"""

import asyncio
from temporalio.worker import Worker
from temporalio.client import Client

from src.config import settings
from src.infrastructure.redis_client import init_redis
from src.infrastructure.kafka_client import init_kafka
from src.workflows.supervisor_workflow import SupervisorWorkflow, run_supervisor_activity
from src.workflows.research_workflow import ResearchWorkflow, run_research_activity
from src.workflows.analysis_workflow import AnalysisWorkflow, run_analysis_activity
from src.workflows.coding_workflow import CodingWorkflow, run_coding_activity
from src.workflows.critic_workflow import CriticWorkflow, run_critic_activity
from src.workflows.writer_workflow import WriterWorkflow, run_writer_activity
from src.workflows.approval_workflow import ApprovalWorkflow, create_approval_activity
from src.workflows.orchestrator_workflow import (
    OrchestratorWorkflow,
    publish_kafka_event,
    save_workflow_memory,
    track_budget_cost,
    update_workflow_status,
    set_workflow_status_activity,
    create_plan_approval,
    record_agent_run,
)


async def run_worker():
    """Run the Temporal worker."""
    try:
        # Activities in this worker (track_budget_cost, save_workflow_memory,
        # memory context lookup) use get_redis_client(), which raises unless
        # init_redis() has already run in this process — the FastAPI process
        # doing it doesn't help, workers run in a separate process.
        await init_redis()

        # Same story for Kafka: publish_kafka_event runs in this process, so
        # the producer must be initialized here or every agent lifecycle
        # event silently fails with "Kafka not initialized". Non-fatal if
        # Kafka is down — events are observability, not control flow.
        try:
            await init_kafka()
        except Exception as e:
            print(f"⚠️ Kafka unavailable, events will not publish: {e}")

        # Connect to Temporal
        client = await Client.connect(
            f"{settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}",
            namespace=settings.TEMPORAL_NAMESPACE,
        )

        # Create worker with workflows and activities
        worker = Worker(
            client,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            workflows=[
                SupervisorWorkflow,
                ResearchWorkflow,
                AnalysisWorkflow,
                CodingWorkflow,
                CriticWorkflow,
                WriterWorkflow,
                OrchestratorWorkflow,
                ApprovalWorkflow,
            ],
            activities=[
                run_supervisor_activity,
                run_research_activity,
                run_analysis_activity,
                run_coding_activity,
                run_critic_activity,
                run_writer_activity,
                create_approval_activity,
                publish_kafka_event,
                save_workflow_memory,
                track_budget_cost,
                update_workflow_status,
                set_workflow_status_activity,
                create_plan_approval,
                record_agent_run,
            ],
        )

        print(f"🚀 Temporal worker started on task queue: {settings.TEMPORAL_TASK_QUEUE}")
        print(f"   Workflows: Supervisor, Research, Analysis, Coding, Critic, Writer, Orchestrator, Approval")
        print(f"   Temporal: {settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}")

        await worker.run()

    except Exception as e:
        print(f"❌ Worker failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_worker())
