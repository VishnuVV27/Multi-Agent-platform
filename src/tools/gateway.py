from typing import Dict, Any, Optional
from datetime import datetime

from src.tools.web_search import WebSearchTool
from src.infrastructure.database import get_sync_session
from src.models.audit_log import AuditLog


# Tool registry
TOOL_REGISTRY: Dict[str, Any] = {
    "web_search": WebSearchTool(),
}


class ToolExecutionException(Exception):
    """Exception during tool execution."""
    pass


class PermissionDeniedException(Exception):
    """Tool execution permission denied."""
    pass


class ToolGateway:
    """
    Tool Execution Gateway: The security boundary for tool execution.

    Responsibilities:
    1. Permission enforcement (which agents can call which tools)
    2. Input validation (query format, constraints)
    3. Execution isolation (run tool safely)
    4. Audit logging (track all tool calls)
    """

    # Agent -> allowed tools mapping (MVP: hardcoded, later in DB)
    AGENT_PERMISSIONS = {
        "research_agent": ["web_search"],
        "analysis_agent": ["web_search"],
        "writer_agent": [],
        "supervisor_agent": [],
    }

    async def execute_tool(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool with permission checks and audit logging.

        Args:
            agent_id: Agent requesting tool execution
            tool_name: Name of tool to execute
            tool_input: Arguments for the tool

        Returns:
            Tool execution result

        Raises:
            PermissionDeniedException: If agent not allowed to use tool
            ToolExecutionException: If tool execution fails
        """
        # Step 1: Check permission
        if not self._check_permission(agent_id, tool_name):
            raise PermissionDeniedException(
                f"Agent '{agent_id}' is not allowed to use tool '{tool_name}'"
            )

        # Step 2: Validate input
        try:
            validated_input = self._validate_input(tool_name, tool_input)
        except Exception as e:
            raise ToolExecutionException(f"Invalid input for tool '{tool_name}': {str(e)}")

        # Step 3: Execute tool
        try:
            tool = TOOL_REGISTRY.get(tool_name)
            if not tool:
                raise ToolExecutionException(f"Tool '{tool_name}' not found")

            result = await tool.execute(**validated_input)

        except Exception as e:
            raise ToolExecutionException(f"Tool execution failed: {str(e)}")

        # Step 4: Audit log
        await self._audit_log(agent_id, tool_name, tool_input, result)

        return result

    def _check_permission(self, agent_id: str, tool_name: str) -> bool:
        """
        Check if agent is allowed to use tool.

        Args:
            agent_id: Agent ID
            tool_name: Tool name

        Returns:
            True if allowed, False otherwise
        """
        allowed_tools = self.AGENT_PERMISSIONS.get(agent_id, [])
        return tool_name in allowed_tools

    def _validate_input(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input for the tool.

        Args:
            tool_name: Tool name
            tool_input: Input to validate

        Returns:
            Validated input

        Raises:
            ValueError: If input is invalid
        """
        if tool_name == "web_search":
            # Validate web_search input
            if "query" not in tool_input:
                raise ValueError("Missing required field: query")

            query = tool_input.get("query", "").strip()
            if not query or len(query) > 500:
                raise ValueError("Query must be 1-500 characters")

            max_results = tool_input.get("max_results", 5)
            if not isinstance(max_results, int) or max_results < 1 or max_results > 10:
                raise ValueError("max_results must be 1-10")

            return {
                "query": query,
                "max_results": max_results,
            }

        return tool_input

    async def _audit_log(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        result: Dict[str, Any],
    ):
        """
        Log tool execution for audit trail.

        Args:
            agent_id: Agent that called the tool
            tool_name: Tool name
            tool_input: Input provided
            result: Execution result
        """
        # TODO: Store in database when models are ready
        # For now, just print
        print(f"[AUDIT] {agent_id} executed {tool_name}")

    def get_tool_manifest(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific tool."""
        tool = TOOL_REGISTRY.get(tool_name)
        return tool.get_manifest() if tool else None

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """List all available tools."""
        return {
            tool_name: tool.get_manifest()
            for tool_name, tool in TOOL_REGISTRY.items()
        }

    def list_allowed_tools(self, agent_id: str) -> list:
        """List tools allowed for an agent."""
        return self.AGENT_PERMISSIONS.get(agent_id, [])


# Global gateway instance
_tool_gateway = None


def get_tool_gateway() -> ToolGateway:
    """Get the global ToolGateway instance."""
    global _tool_gateway
    if _tool_gateway is None:
        _tool_gateway = ToolGateway()
    return _tool_gateway
