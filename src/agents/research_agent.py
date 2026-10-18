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
from src.llm.gateway import get_llm_gateway
from src.observability.progress import report_progress, make_llm_stream_reporter
from src.prompts.registry import get_prompt_registry


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
            await report_progress(
                task_input.workflow_id, self.AGENT_ID,
                "Searching the web…", detail=search_query[:120],
            )
            tool_gateway = get_tool_gateway()
            search_result = await tool_gateway.execute_tool(
                agent_id=self.AGENT_ID,
                tool_name="web_search",
                tool_input={
                    "query": search_query,
                    "max_results": 5,
                }
            )

            # Step 3: Process and aggregate results. If live search failed
            # (network down, rate limit), continue with model knowledge
            # rather than failing the whole workflow — but say so.
            findings = self._process_search_results(search_result.get("results", []))
            search_ok = bool(search_result.get("success", False) and findings)

            await report_progress(
                task_input.workflow_id, self.AGENT_ID,
                f"Found {len(findings)} live sources" if search_ok else "Live search unavailable — using model knowledge",
                detail="; ".join(f.get("title", "")[:60] for f in findings[:3]),
            )

            # Step 4: Synthesize research notes using LLM (prompt text and
            # version come from the Prompt Registry, not code)
            llm_gateway = get_llm_gateway()
            registry = get_prompt_registry()
            if search_ok:
                sources_block = chr(10).join(
                    f"[{f['position']}] {f['title']} ({f['url']})\n    {f['snippet']}"
                    for f in findings
                )
                summary_prompt, prompt_version = registry.render(
                    "research_synthesis",
                    search_query=search_query,
                    sources_block=sources_block,
                )
            else:
                summary_prompt, prompt_version = registry.render(
                    "research_synthesis_offline",
                    search_query=search_query,
                )
            summary_prompt += self.skill_addendum(task_input)

            llm_response = await llm_gateway.generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=summary_prompt,
                task_type="fast",
                max_tokens=self.capped_max_tokens(task_input, 700),
                on_chunk=make_llm_stream_reporter(
                    task_input.workflow_id, self.AGENT_ID, "Synthesizing research notes…",
                ),
            )
            summary = llm_response.get("text", "")
            llm_cost = llm_response.get("cost", 0)
            llm_tokens = llm_response.get("tokens", {})

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "query": search_query,
                    "findings": findings,
                    "summary": summary,
                    "result_count": len(findings),
                    "live_search": search_ok,
                },
                tokens_used=llm_tokens,
                metadata={
                    "llm_cost": llm_cost,
                    "model": llm_response.get("model"),
                    "prompt_version": prompt_version,
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

