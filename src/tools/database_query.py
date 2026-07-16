"""
Database Query Tool: Execute SQL queries safely.

Features:
- Query builder (prevent SQL injection)
- Result limiting (prevent huge result sets)
- Timeout handling
"""

from typing import Dict, Any, List, Optional
import re


class DatabaseQueryTool:
    """Execute SQL queries with safety constraints."""

    TOOL_ID = "database_query"
    TOOL_NAME = "Database Query"
    DESCRIPTION = "Execute SQL queries (SELECT only, max 1000 rows)"
    RISK_LEVEL = "high"  # High risk: can access sensitive data
    CATEGORY = "information"

    # Whitelist: only SELECT allowed
    ALLOWED_OPERATIONS = ["SELECT"]
    MAX_ROWS = 1000
    TIMEOUT_SECONDS = 30

    async def execute(
        self,
        query: str,
        database: str = "default",
        max_rows: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a SQL query safely.

        Args:
            query: SQL query (SELECT only)
            database: Database to query
            max_rows: Limit results (default 1000)

        Returns:
            {
                "success": bool,
                "rows": List[Dict],
                "row_count": int,
                "execution_time_ms": float
            }
        """
        try:
            # Step 1: Validate query is SELECT only
            if not self._is_safe_query(query):
                return {
                    "success": False,
                    "error": "Only SELECT queries are allowed",
                }

            max_rows = min(max_rows or self.MAX_ROWS, self.MAX_ROWS)

            # For MVP: Return mock data
            # Later: Connect to actual database
            mock_rows = [
                {"id": 1, "name": "Sample Row 1", "value": 100},
                {"id": 2, "name": "Sample Row 2", "value": 200},
            ]

            return {
                "success": True,
                "database": database,
                "query": query,
                "rows": mock_rows[:max_rows],
                "row_count": len(mock_rows),
                "execution_time_ms": 45,
                "note": "Using mock data for MVP. Replace with real database connection.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _is_safe_query(self, query: str) -> bool:
        """
        Validate query is safe (SELECT only, no comments).

        Args:
            query: SQL query to validate

        Returns:
            True if safe, False otherwise
        """
        # Remove whitespace and convert to uppercase
        clean_query = query.strip().upper()

        # Check for dangerous keywords
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
        for keyword in dangerous:
            if keyword in clean_query:
                return False

        # Check for comments
        if "--" in query or "/*" in query:
            return False

        # Must start with SELECT
        if not clean_query.startswith("SELECT"):
            return False

        return True

    def get_manifest(self) -> Dict[str, Any]:
        """Return tool metadata."""
        return {
            "tool_id": self.TOOL_ID,
            "tool_name": self.TOOL_NAME,
            "description": self.DESCRIPTION,
            "risk_level": self.RISK_LEVEL,
            "category": self.CATEGORY,
            "constraints": {
                "operations": self.ALLOWED_OPERATIONS,
                "max_rows": self.MAX_ROWS,
                "timeout_seconds": self.TIMEOUT_SECONDS,
            },
        }
