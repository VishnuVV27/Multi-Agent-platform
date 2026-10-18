"""
Database Query Tool: Execute SQL queries safely.

Features:
- SELECT-only whitelist with word-boundary keyword checks
- Result limiting (prevent huge result sets)
- Statement timeout enforcement
- Runs against the platform's own Postgres (read-only view of
  workflows, agent_runs, approvals, memories, audit logs)
"""

from typing import Dict, Any, List, Optional
import asyncio
import re
import time


class DatabaseQueryTool:
    """Execute SQL queries with safety constraints."""

    TOOL_ID = "database_query"
    TOOL_NAME = "Database Query"
    DESCRIPTION = (
        "Query the platform database (SELECT only, max 1000 rows). "
        "Tables: workflows, agent_runs, approval_requests, workflow_memories, audit_logs"
    )
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
            database: Database to query (only "default" supported)
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
                    "error": "Only SELECT queries are allowed (no comments, no mutations)",
                }

            max_rows = min(max_rows or self.MAX_ROWS, self.MAX_ROWS)

            start = time.time()
            rows = await asyncio.to_thread(self._execute_sync, query, max_rows)
            execution_time_ms = (time.time() - start) * 1000

            return {
                "success": True,
                "database": database,
                "query": query,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": round(execution_time_ms, 1),
            }

        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e),
            }

    def _execute_sync(self, query: str, max_rows: int) -> List[Dict[str, Any]]:
        """Run the query against Postgres with a statement timeout."""
        from sqlalchemy import text
        from src.infrastructure.database import get_db

        db = get_db()
        try:
            db.execute(
                text(f"SET LOCAL statement_timeout = {self.TIMEOUT_SECONDS * 1000}")
            )
            result = db.execute(text(query)).mappings()
            rows = []
            for i, row in enumerate(result):
                if i >= max_rows:
                    break
                # Stringify non-JSON-serializable values (UUID, datetime, vectors)
                rows.append(
                    {
                        k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v)[:200])
                        for k, v in dict(row).items()
                    }
                )
            return rows
        finally:
            db.close()

    def _is_safe_query(self, query: str) -> bool:
        """
        Validate query is safe (SELECT only, no comments, no stacked statements).

        Args:
            query: SQL query to validate

        Returns:
            True if safe, False otherwise
        """
        clean_query = query.strip().upper()

        # Word-boundary check for mutating keywords (substring check would
        # false-positive on column names like "updated_at")
        dangerous = [
            "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
            "GRANT", "REVOKE", "CREATE", "COPY", "EXECUTE",
        ]
        for keyword in dangerous:
            if re.search(rf"\b{keyword}\b", clean_query):
                return False

        # No comments or stacked statements
        if "--" in query or "/*" in query or ";" in query.rstrip().rstrip(";"):
            return False

        # Must start with SELECT (or WITH ... SELECT)
        if not (clean_query.startswith("SELECT") or clean_query.startswith("WITH")):
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
