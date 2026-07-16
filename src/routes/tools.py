"""
API routes for tool management and discovery.

Endpoints:
- GET /api/tools - List all tools
- GET /api/tools/{tool_id} - Get tool metadata
- GET /api/tools/metrics - Get gateway metrics
- GET /api/tools/permissions/{agent_id} - Get agent permissions
"""

from fastapi import APIRouter
from typing import Dict, Any

from src.tools.gateway import get_tool_gateway
from src.registry.tool_registry import get_tool_registry

router = APIRouter(prefix="/api/tools", tags=["Tools"])


@router.get("/")
async def list_tools() -> Dict[str, Any]:
    """List all available tools."""
    gateway = get_tool_gateway()
    tools = gateway.list_tools()
    return {
        "count": len(tools),
        "tools": tools,
    }


@router.get("/{tool_id}")
async def get_tool(tool_id: str) -> Dict[str, Any]:
    """Get detailed metadata for a tool."""
    gateway = get_tool_gateway()
    manifest = gateway.get_tool_manifest(tool_id)

    if not manifest:
        return {
            "error": f"Tool '{tool_id}' not found",
            "tool_id": tool_id,
        }

    return {
        "tool_id": tool_id,
        "metadata": manifest,
    }


@router.get("/metrics/summary")
async def get_tool_metrics() -> Dict[str, Any]:
    """Get tool gateway metrics and statistics."""
    gateway = get_tool_gateway()
    metrics = gateway.get_metrics()

    return {
        "summary": metrics,
        "message": "Tool execution metrics",
    }


@router.get("/permissions/{agent_id}")
async def get_agent_permissions(agent_id: str) -> Dict[str, Any]:
    """Get tools allowed for a specific agent."""
    gateway = get_tool_gateway()
    allowed_tools = gateway.list_allowed_tools(agent_id)

    return {
        "agent_id": agent_id,
        "allowed_tools": allowed_tools,
        "tool_count": len(allowed_tools),
    }


@router.get("/by-category/{category}")
async def get_tools_by_category(category: str) -> Dict[str, Any]:
    """Get all tools in a category (information, action, compute)."""
    gateway = get_tool_gateway()
    all_tools = gateway.list_tools()

    tools_in_category = {
        tool_id: tool_meta
        for tool_id, tool_meta in all_tools.items()
        if tool_meta.get("category") == category
    }

    return {
        "category": category,
        "count": len(tools_in_category),
        "tools": tools_in_category,
    }


@router.get("/by-risk/{risk_level}")
async def get_tools_by_risk(risk_level: str) -> Dict[str, Any]:
    """Get all tools by risk level (low, medium, high, critical)."""
    gateway = get_tool_gateway()
    all_tools = gateway.list_tools()

    tools_by_risk = {
        tool_id: tool_meta
        for tool_id, tool_meta in all_tools.items()
        if tool_meta.get("risk_level") == risk_level
    }

    return {
        "risk_level": risk_level,
        "count": len(tools_by_risk),
        "tools": tools_by_risk,
    }
