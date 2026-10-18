"""
Document Reader Tool: Read and extract text from documents.

Supports: TXT, MD, JSON

Security: reads are confined to the workspace directory (path-traversal
guarded); anything outside it is rejected.
"""

from typing import Dict, Any
from pathlib import Path
import asyncio
import json


class DocumentReaderTool:
    """Read and extract content from documents."""

    TOOL_ID = "document_reader"
    TOOL_NAME = "Document Reader"
    DESCRIPTION = "Read and extract text from documents in the workspace (TXT, MD, JSON)"
    RISK_LEVEL = "low"
    CATEGORY = "information"
    SUPPORTED_FORMATS = ["txt", "md", "json"]
    MAX_BYTES = 1_000_000  # 1 MB cap

    # Documents agents may read live here (created on demand)
    WORKSPACE_DIR = Path(__file__).resolve().parents[2] / "workspace"

    async def execute(self, file_path: str, format: str = "txt") -> Dict[str, Any]:
        """
        Read document content.

        Args:
            file_path: Path to document, relative to the workspace directory
            format: Document format (txt, md, json)

        Returns:
            {
                "success": bool,
                "content": str,
                "format": str,
                "size_bytes": int,
                "lines": int
            }
        """
        try:
            if format not in self.SUPPORTED_FORMATS:
                return {
                    "success": False,
                    "error": f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}",
                }

            resolved = (self.WORKSPACE_DIR / file_path).resolve()
            if not resolved.is_relative_to(self.WORKSPACE_DIR):
                return {
                    "success": False,
                    "error": "Access denied: path escapes the workspace directory",
                    "file_path": file_path,
                }

            if not resolved.is_file():
                return {
                    "success": False,
                    "error": f"File not found in workspace: {file_path}",
                    "file_path": file_path,
                }

            if resolved.stat().st_size > self.MAX_BYTES:
                return {
                    "success": False,
                    "error": f"File exceeds {self.MAX_BYTES} byte limit",
                    "file_path": file_path,
                }

            content = await asyncio.to_thread(
                resolved.read_text, "utf-8", "replace"
            )

            if format == "json":
                # Validate it parses; return pretty-printed for the LLM
                content = json.dumps(json.loads(content), indent=2)

            return {
                "success": True,
                "file_path": file_path,
                "format": format,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "lines": content.count("\n") + 1,
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {e}",
                "file_path": file_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path,
            }

    def get_manifest(self) -> Dict[str, Any]:
        """Return tool metadata."""
        return {
            "tool_id": self.TOOL_ID,
            "tool_name": self.TOOL_NAME,
            "description": self.DESCRIPTION,
            "risk_level": self.RISK_LEVEL,
            "category": self.CATEGORY,
            "input_schema": {
                "file_path": "string (path relative to the workspace directory)",
                "format": f"string (one of: {', '.join(self.SUPPORTED_FORMATS)})",
            },
        }
