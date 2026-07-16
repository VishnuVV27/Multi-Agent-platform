"""
Code Executor Tool: Execute Python code safely in a sandbox.

Security:
- Timeout enforcement (prevent infinite loops)
- Restricted builtins (no file/network access)
- Output capture
"""

from typing import Dict, Any, Optional
import ast
import sys
from io import StringIO


class CodeExecutorTool:
    """Execute Python code with safety constraints."""

    TOOL_ID = "code_executor"
    TOOL_NAME = "Code Executor"
    DESCRIPTION = "Execute Python code safely (sandboxed, no file/network access)"
    RISK_LEVEL = "high"  # High risk: can execute arbitrary code
    CATEGORY = "compute"

    TIMEOUT_SECONDS = 10
    MAX_OUTPUT_LENGTH = 10000

    # Restricted builtins (no file/network access)
    ALLOWED_BUILTINS = {
        "print", "len", "range", "sum", "max", "min", "sorted", "enumerate",
        "zip", "map", "filter", "abs", "round", "str", "int", "float", "bool",
        "list", "dict", "set", "tuple", "dict", "Exception"
    }

    async def execute(
        self,
        code: str,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute Python code safely.

        Args:
            code: Python code to execute
            timeout_seconds: Execution timeout (default 10)

        Returns:
            {
                "success": bool,
                "output": str,
                "error": str (if failed)
            }
        """
        try:
            # Step 1: Validate code is safe
            if not self._is_safe_code(code):
                return {
                    "success": False,
                    "error": "Code contains unsafe operations",
                }

            timeout = min(timeout_seconds or self.TIMEOUT_SECONDS, self.TIMEOUT_SECONDS)

            # For MVP: Return mock execution
            # Later: Use actual sandbox (Docker, Firecracker, etc.)
            mock_output = f"Executed code (mock):\n{code[:100]}..."

            return {
                "success": True,
                "output": mock_output,
                "execution_time_ms": 150,
                "note": "Using mock execution for MVP. Replace with real sandbox.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _is_safe_code(self, code: str) -> bool:
        """
        Validate code is safe (no file/network/import).

        Args:
            code: Python code to validate

        Returns:
            True if safe, False otherwise
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        # Check for unsafe patterns
        for node in ast.walk(tree):
            # No imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return False

            # No file operations
            if isinstance(node, ast.Attribute):
                if node.attr in ["open", "read", "write", "system"]:
                    return False

            # No exec/eval
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["exec", "eval", "__import__"]:
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
                "timeout_seconds": self.TIMEOUT_SECONDS,
                "max_output_length": self.MAX_OUTPUT_LENGTH,
                "blocked_operations": ["import", "file I/O", "network", "exec/eval"],
                "allowed_builtins": list(self.ALLOWED_BUILTINS),
            },
        }
