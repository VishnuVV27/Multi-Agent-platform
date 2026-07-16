"""
Workflow Tracer: Trace workflow execution through all stages.

Integrates with Langfuse to create a trace for each workflow
including all agent executions and LLM calls.
"""

import logging
from typing import Optional, Dict, Any, List

from src.observability.langfuse_client import get_langfuse_client

logger = logging.getLogger(__name__)


class WorkflowTracer:
    """Trace workflow execution for observability."""

    def __init__(self):
        """Initialize workflow tracer."""
        self.langfuse = get_langfuse_client()

    def start_workflow_trace(
        self,
        workflow_id: str,
        user_request: str,
        agents: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Start a workflow trace.

        Args:
            workflow_id: Workflow ID
            user_request: Original user request
            agents: Agents that will execute
            metadata: Additional metadata

        Returns:
            True if trace started, False otherwise
        """
        try:
            trace_metadata = {
                "user_request": user_request,
                "agents": agents,
                "agent_count": len(agents),
            }

            if metadata:
                trace_metadata.update(metadata)

            self.langfuse.client.trace(
                id=workflow_id,
                name="workflow:execution",
                metadata=trace_metadata,
            )

            logger.debug(f"Started workflow trace: {workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start workflow trace: {e}")
            return False

    def end_workflow_trace(
        self,
        workflow_id: str,
        duration_ms: int,
        cost: float,
        tokens: int,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        End a workflow trace.

        Args:
            workflow_id: Workflow ID
            duration_ms: Total execution time
            cost: Total cost
            tokens: Total tokens used
            success: Did workflow succeed?
            metadata: Additional metadata

        Returns:
            True if trace ended, False otherwise
        """
        try:
            trace_metadata = {
                "success": success,
                "duration_ms": duration_ms,
                "cost": cost,
                "tokens": tokens,
            }

            if metadata:
                trace_metadata.update(metadata)

            self.langfuse.client.trace(
                id=workflow_id,
                metadata=trace_metadata,
            )

            logger.debug(f"Ended workflow trace: {workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to end workflow trace: {e}")
            return False

    def trace_agent(
        self,
        workflow_id: str,
        agent_id: str,
        agent_name: str,
        task_input: str,
        task_output: str,
        duration_ms: int,
        cost: float,
        tokens: int,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Trace an agent execution within a workflow.

        Args:
            workflow_id: Parent workflow ID
            agent_id: Agent ID
            agent_name: Agent human name
            task_input: Task instruction
            task_output: Agent result
            duration_ms: Execution time
            cost: Cost of execution
            tokens: Tokens used
            success: Did agent succeed?
            metadata: Additional metadata

        Returns:
            True if trace succeeded, False otherwise
        """
        try:
            span_metadata = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "success": success,
                "duration_ms": duration_ms,
                "cost": cost,
                "tokens": tokens,
            }

            if metadata:
                span_metadata.update(metadata)

            self.langfuse.client.span(
                trace_id=workflow_id,
                name=f"agent:{agent_id}",
                input={"task": task_input},
                output={"result": task_output},
                metadata=span_metadata,
            )

            logger.debug(f"Traced agent: {agent_id} in workflow {workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to trace agent: {e}")
            return False

    def trace_tool_call(
        self,
        workflow_id: str,
        agent_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        duration_ms: int,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Trace a tool call within an agent.

        Args:
            workflow_id: Parent workflow ID
            agent_id: Agent ID
            tool_name: Tool name
            tool_input: Tool input parameters
            tool_output: Tool result
            duration_ms: Execution time
            success: Did tool succeed?
            metadata: Additional metadata

        Returns:
            True if trace succeeded, False otherwise
        """
        try:
            span_metadata = {
                "tool_name": tool_name,
                "success": success,
                "duration_ms": duration_ms,
            }

            if metadata:
                span_metadata.update(metadata)

            self.langfuse.client.span(
                trace_id=workflow_id,
                name=f"tool:{tool_name}",
                input=tool_input,
                output={"result": tool_output},
                metadata=span_metadata,
            )

            logger.debug(f"Traced tool: {tool_name} in agent {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to trace tool call: {e}")
            return False

    def flush(self) -> None:
        """Flush all pending traces."""
        if self.langfuse:
            self.langfuse.flush()
