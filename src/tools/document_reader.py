"""
Document Reader Tool: Read and extract text from documents.

Supports: TXT, PDF, MD, JSON
"""

from typing import Dict, Any, Optional
import json


class DocumentReaderTool:
    """Read and extract content from documents."""

    TOOL_ID = "document_reader"
    TOOL_NAME = "Document Reader"
    DESCRIPTION = "Read and extract text from documents (TXT, PDF, MD, JSON)"
    RISK_LEVEL = "low"
    CATEGORY = "information"
    SUPPORTED_FORMATS = ["txt", "md", "json"]

    async def execute(self, file_path: str, format: str = "txt") -> Dict[str, Any]:
        """
        Read document content.

        Args:
            file_path: Path to document
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
            # Validate format
            if format not in self.SUPPORTED_FORMATS:
                return {
                    "success": False,
                    "error": f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}",
                }

            # For MVP: Return mock data
            # Later: Implement actual file reading with security checks
            mock_content = f"Sample content from {file_path}"
            lines = mock_content.split("\n")

            return {
                "success": True,
                "file_path": file_path,
                "format": format,
                "content": mock_content,
                "size_bytes": len(mock_content),
                "lines": len(lines),
                "note": "Using mock data for MVP. Replace with real file operations.",
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
                "file_path": "string (path to document)",
                "format": f"string (one of: {', '.join(self.SUPPORTED_FORMATS)})",
            },
        }
