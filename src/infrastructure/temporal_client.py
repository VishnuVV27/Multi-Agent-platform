from temporalio.client import Client
from temporalio.worker import Worker
from typing import Optional
import asyncio

from src.config import settings

temporal_client: Optional[Client] = None


async def init_temporal_client():
    """Initialize Temporal client."""
    global temporal_client
    try:
        temporal_client = await Client.connect(
            f"{settings.TEMPORAL_HOST}:{settings.TEMPORAL_PORT}",
            namespace=settings.TEMPORAL_NAMESPACE,
        )
        print("✅ Temporal connected")
    except Exception as e:
        print(f"❌ Temporal connection failed: {e}")
        raise


def get_temporal_client() -> Client:
    """Get Temporal client instance."""
    if temporal_client is None:
        raise RuntimeError("Temporal not initialized. Call init_temporal_client() first.")
    return temporal_client


async def start_worker(worker_cls):
    """Start a Temporal worker."""
    client = get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[],  # Will be populated with workflow classes
        activities=[],  # Will be populated with activity functions
    )
    await worker.run()


async def execute_workflow(workflow_class, input_data: dict, workflow_id: str):
    """Execute a Temporal workflow."""
    client = get_temporal_client()
    result = await client.execute_workflow(
        workflow_class.run,
        input_data,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    return result
