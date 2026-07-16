from typing import Dict, Any, List

from src.agents.base import (
    BaseAgent,
    TaskInput,
    TaskOutput,
    AgentStatus,
    AgentCapability,
    register_agent,
)
from src.tools.gateway import get_tool_gateway


@register_agent
class ResearchAgent(BaseAgent):
    """
    Research Agent: Gathers information on a topic using web search.

    Capabilities:
    - Web search for information
    - Result aggregation and summarization

    Uses Tool Gateway to execute web_search tool (permission-controlled).
    """

    AGENT_ID = "research_agent"
    AGENT_NAME = "Research Agent"
    DESCRIPTION = "Researches topics by searching the web and aggregating results"
    CAPABILITIES = [AgentCapability.WEB_SEARCH, AgentCapability.DOCUMENT_ANALYSIS]
    ALLOWED_TOOLS = ["web_search"]
    VERSION = "1.0.0"

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute research task.

        Input:
        {
            instruction: "Research competitors in SaaS market",
            context: {...}
        }

        Output:
        {
            result: {
                query: "...",
                findings: [...],
                summary: "..."
            }
        }
        """
        try:
            instruction = task_input.instruction
            context = task_input.context or {}

            # Step 1: Extract search query from instruction
            search_query = self._extract_search_query(instruction, context)

            # Step 2: Execute web search through Tool Gateway
            tool_gateway = get_tool_gateway()
            search_result = await tool_gateway.execute_tool(
                agent_id=self.AGENT_ID,
                tool_name="web_search",
                tool_input={
                    "query": search_query,
                    "max_results": 5,
                }
            )

            if not search_result.get("success"):
                raise Exception(f"Web search failed: {search_result.get('error')}")

            # Step 3: Process and aggregate results
            findings = self._process_search_results(search_result.get("results", []))

            # Step 4: Generate summary
            summary = self._generate_summary(search_query, findings)

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "query": search_query,
                    "findings": findings,
                    "summary": summary,
                    "result_count": len(findings),
                },
            )

        except Exception as e:
            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.FAILED,
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "retryable": True,
                },
            )

    def _extract_search_query(self, instruction: str, context: Dict[str, Any]) -> str:
        """
        Extract search query from instruction.

        For MVP: Just use the instruction as-is (after cleaning).
        Later: Use LLM to extract or refine the query.
        """
        # Remove common prefixes
        query = instruction.replace("Research the following:", "").strip()
        query = query.replace("Research", "").strip()

        return query or instruction

    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process raw search results.

        Args:
            results: List of search results from tool

        Returns:
            Processed findings
        """
        processed = []
        for i, result in enumerate(results):
            processed.append({
                "position": i + 1,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
            })
        return processed

    def _generate_summary(self, query: str, findings: List[Dict[str, Any]]) -> str:
        """
        Generate a summary of findings.

        For MVP: Simple concatenation.
        Later: Use LLM to generate coherent summary.
        """
        if not findings:
            return f"No findings found for: {query}"

        summary_parts = [
            f"Research Summary for '{query}':",
            f"Found {len(findings)} results:",
        ]

        for finding in findings:
            summary_parts.append(
                f"  {finding['position']}. {finding['title']} - {finding['snippet'][:100]}..."
            )

        return "\n".join(summary_parts)
