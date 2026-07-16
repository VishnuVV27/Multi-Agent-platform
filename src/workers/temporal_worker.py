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
from src.workflows.supervisor_workflow import SupervisorWorkflow, run_supervisor_activity
from src.workflows.research_workflow import ResearchWorkflow, run_research_activity
from src.workflows.orchestrator_workflow import OrchestratorWorkflow, publish_kafka_event


async def run_worker():
    """Run the Temporal worker."""
    try:
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
                OrchestratorWorkflow,
            ],
            activities=[
                run_supervisor_activity,
                run_research_activity,
                publish_kafka_event,
            ],
        )

        print(f"🚀 Temporal worker started on task queue: {settings.TEMPORAL_TASK_QUEUE}")
        print(f"   Workflows: SupervisorWorkflow, ResearchWorkflow, OrchestratorWorkflow")
        print(f"   Temporal: {settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}")

        await worker.run()

    except Exception as e:
        print(f"❌ Worker failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_worker())
