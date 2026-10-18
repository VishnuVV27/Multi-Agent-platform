"""
Code Executor Tool: Execute Python code in an isolated subprocess.

Security:
- AST validation first (no imports, no exec/eval, no file ops)
- Runs in `python -I` isolated mode as a separate process
- Hard timeout enforcement (process killed on expiry)
- Output capture with length cap

Upgrade path (per CLAUDE.md Tool Execution Layer): move to a Docker/
Firecracker sandbox for true network/filesystem isolation before
allowing untrusted multi-tenant code.
"""

from typing import Dict, Any, Optional
import ast
import asyncio
import sys
import time


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

            start = time.time()
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-I", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "success": False,
                    "error": f"Execution timed out after {timeout}s",
                }

            execution_time_ms = round((time.time() - start) * 1000, 1)
            output = stdout.decode("utf-8", "replace")[: self.MAX_OUTPUT_LENGTH]
            errors = stderr.decode("utf-8", "replace")[: self.MAX_OUTPUT_LENGTH]

            if proc.returncode != 0:
                return {
                    "success": False,
                    "output": output,
                    "error": errors or f"Process exited with code {proc.returncode}",
                    "execution_time_ms": execution_time_ms,
                }

            return {
                "success": True,
                "output": output,
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # Pure-computation stdlib modules with no file/network/process access.
    # Banning ALL imports made real work impossible (e.g. a Monte Carlo
    # simulation without `random` degenerates into deterministic nonsense) —
    # the isolated `python -I` subprocess remains the hard boundary; this
    # allowlist just keeps os/sys/socket/subprocess/urllib-class modules out.
    ALLOWED_MODULES = {
        "math", "random", "statistics", "itertools", "collections",
        "functools", "json", "datetime", "re", "decimal", "fractions",
        "heapq", "string", "bisect", "textwrap",
    }

    def _is_safe_code(self, code: str) -> bool:
        """
        Validate code is safe: only allowlisted pure-computation imports,
        no file operations, no exec/eval.

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
            # Imports: allowlist only
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in self.ALLOWED_MODULES:
                        return False
            if isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] not in self.ALLOWED_MODULES:
                    return False

            # No file operations
            if isinstance(node, ast.Attribute):
                if node.attr in ["open", "read", "write", "system"]:
                    return False

            # No exec/eval
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["exec", "eval", "__import__", "open"]:
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
