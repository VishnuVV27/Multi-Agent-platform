"""
Unit tests for Enhanced Tool Gateway.

Tests RBAC, metrics, multiple tools, and permission enforcement.
"""

import pytest
from src.tools.gateway import (
    get_tool_gateway, ToolGateway, AgentRole, PermissionDeniedException
)


class TestToolGatewayRBAC:
    """Tests for Role-Based Access Control."""

    def test_researcher_role_permissions(self):
        """Researcher can use search and documents only."""
        gateway = get_tool_gateway()
        allowed = gateway.list_allowed_tools("research_agent")
        assert "web_search" in allowed
        assert "document_reader" in allowed
        assert "database_query" not in allowed
        assert "code_executor" not in allowed

    def test_analyst_role_permissions(self):
        """Analyst can use search, documents, and database."""
        gateway = get_tool_gateway()
        allowed = gateway.list_allowed_tools("analysis_agent")
        assert "web_search" in allowed
        assert "document_reader" in allowed
        assert "database_query" in allowed
        assert "code_executor" not in allowed

    def test_supervisor_no_tools(self):
        """Supervisor has no tool access."""
        gateway = get_tool_gateway()
        allowed = gateway.list_allowed_tools("supervisor_agent")
        assert len(allowed) == 0

    def test_permission_check_allowed(self):
        """Check permission for allowed tool."""
        gateway = ToolGateway()
        # Research agent should be able to use web_search
        allowed = gateway._check_permission("research_agent", "web_search")
        assert allowed is True

    def test_permission_check_denied(self):
        """Check permission for denied tool."""
        gateway = ToolGateway()
        # Research agent should NOT be able to use database_query
        allowed = gateway._check_permission("research_agent", "database_query")
        assert allowed is False

    def test_permission_check_unknown_agent(self):
        """Unknown agent has no permissions."""
        gateway = ToolGateway()
        allowed = gateway._check_permission("unknown_agent", "web_search")
        assert allowed is False


class TestToolRegistration:
    """Tests for tool registration and discovery."""

    def test_all_tools_registered(self):
        """All expected tools are registered."""
        gateway = get_tool_gateway()
        tools = gateway.list_tools()
        assert "web_search" in tools
        assert "document_reader" in tools
        assert "database_query" in tools
        assert "code_executor" in tools

    def test_get_tool_manifest(self):
        """Can get tool metadata."""
        gateway = get_tool_gateway()
        manifest = gateway.get_tool_manifest("web_search")
        assert manifest is not None
        assert manifest["tool_id"] == "web_search"
        assert "input_schema" in manifest

    def test_tool_has_risk_level(self):
        """Tools declare their risk level."""
        gateway = get_tool_gateway()

        # Low risk
        web_search = gateway.get_tool_manifest("web_search")
        assert web_search["risk_level"] == "low"

        # High risk
        db_query = gateway.get_tool_manifest("database_query")
        assert db_query["risk_level"] == "high"

        code_exec = gateway.get_tool_manifest("code_executor")
        assert code_exec["risk_level"] == "high"


class TestToolMetrics:
    """Tests for tool execution metrics."""

    def test_metrics_initialized(self):
        """Gateway tracks metrics."""
        gateway = ToolGateway()
        metrics = gateway.get_metrics()
        assert "total_calls" in metrics
        assert "successful_calls" in metrics
        assert "failed_calls" in metrics
        assert "permission_denied" in metrics

    def test_record_metric_success(self):
        """Record successful execution metric."""
        gateway = ToolGateway()
        gateway._record_metric("research_agent", "web_search", True)

        metrics = gateway.get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["successful_calls"] == 1
        assert metrics["by_tool"]["web_search"]["success"] == 1

    def test_record_metric_failure(self):
        """Record failed execution metric."""
        gateway = ToolGateway()
        gateway._record_metric("research_agent", "web_search", False)

        metrics = gateway.get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["failed_calls"] == 1
        assert metrics["by_tool"]["web_search"]["failed"] == 1

    def test_record_metric_permission_denied(self):
        """Record permission denied metric."""
        gateway = ToolGateway()
        gateway._record_metric("supervisor_agent", "web_search", False, permission_denied=True)

        metrics = gateway.get_metrics()
        assert metrics["permission_denied"] == 1

    def test_metrics_by_agent(self):
        """Metrics tracked per agent."""
        gateway = ToolGateway()
        gateway._record_metric("research_agent", "web_search", True)
        gateway._record_metric("analysis_agent", "database_query", True)

        metrics = gateway.get_metrics()
        assert metrics["by_agent"]["research_agent"]["calls"] == 1
        assert metrics["by_agent"]["analysis_agent"]["calls"] == 1

    def test_metrics_by_tool(self):
        """Metrics tracked per tool."""
        gateway = ToolGateway()
        gateway._record_metric("research_agent", "web_search", True)
        gateway._record_metric("research_agent", "web_search", False)

        metrics = gateway.get_metrics()
        assert metrics["by_tool"]["web_search"]["calls"] == 2
        assert metrics["by_tool"]["web_search"]["success"] == 1
        assert metrics["by_tool"]["web_search"]["failed"] == 1


class TestPermissionEnforcement:
    """Tests for permission enforcement in execute_tool."""

    @pytest.mark.asyncio
    async def test_permission_denied_raises_exception(self):
        """Permission denied raises PermissionDeniedException."""
        gateway = ToolGateway()

        with pytest.raises(PermissionDeniedException):
            await gateway.execute_tool(
                agent_id="supervisor_agent",
                tool_name="web_search",
                tool_input={"query": "test"}
            )

    @pytest.mark.asyncio
    async def test_invalid_input_raises_exception(self):
        """Invalid input raises ToolExecutionException."""
        from src.tools.gateway import ToolExecutionException

        gateway = ToolGateway()

        with pytest.raises(ToolExecutionException):
            await gateway.execute_tool(
                agent_id="research_agent",
                tool_name="web_search",
                tool_input={"query": "", "invalid_param": "value"}  # Empty query
            )


class TestToolConstraints:
    """Tests for tool constraints and safety."""

    def test_database_tool_constraints(self):
        """Database tool declares constraints."""
        gateway = get_tool_gateway()
        manifest = gateway.get_tool_manifest("database_query")

        assert "constraints" in manifest
        assert manifest["constraints"]["operations"] == ["SELECT"]
        assert manifest["constraints"]["max_rows"] == 1000

    def test_code_executor_constraints(self):
        """Code executor declares constraints."""
        gateway = get_tool_gateway()
        manifest = gateway.get_tool_manifest("code_executor")

        assert "constraints" in manifest
        assert manifest["constraints"]["timeout_seconds"] == 10
        assert "blocked_operations" in manifest["constraints"]
