"""
Tool Registry: Service discovery and metadata for tools.

Maintains:
- What tools exist
- What they do
- Risk level (permission enforcement)
- Input/output schemas
- Category (information, action, compute)

For MVP: In-memory from TOOL_REGISTRY.
Later: Postgres + Redis cache.
"""

from typing import Dict, Any, Optional, List
from src.tools.gateway import TOOL_REGISTRY


class ToolRegistry:
    """Central registry for tool discovery and metadata."""

    def __init__(self):
        """Initialize registry from TOOL_REGISTRY."""
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._load_tools()

    def _load_tools(self):
        """Load all registered tools."""
        for tool_id, tool_instance in TOOL_REGISTRY.items():
            manifest = tool_instance.get_manifest()
            self._tools[tool_id] = {
                **manifest,
                "registered": True,
            }

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get tool metadata by ID."""
        return self._tools.get(tool_id)

    def get_tool_instance(self, tool_id: str):
        """Get the actual tool instance."""
        return TOOL_REGISTRY.get(tool_id)

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """List all tools."""
        return self._tools.copy()

    def list_tools_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """List tools by category (information, action, compute)."""
        return {
            tool_id: tool_meta
            for tool_id, tool_meta in self._tools.items()
            if tool_meta.get("category") == category
        }

    def list_tools_by_risk_level(self, risk_level: str) -> Dict[str, Dict[str, Any]]:
        """List tools by risk level (low, medium, high, critical)."""
        return {
            tool_id: tool_meta
            for tool_id, tool_meta in self._tools.items()
            if tool_meta.get("risk_level") == risk_level
        }

    def validate_tool_input(self, tool_id: str, input_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate input against tool's schema.

        Args:
            tool_id: Tool ID
            input_data: Input to validate

        Returns:
            (is_valid, error_message)
        """
        tool = self.get_tool(tool_id)
        if not tool:
            return False, f"Tool '{tool_id}' not found"

        # TODO: Implement schema validation using JSONSchema
        # For now: basic check
        return True, ""


# Global registry instance
_tool_registry = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
