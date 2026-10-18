"""
Analysis Agent: Analyzes data and generates insights.

Capabilities:
- Query databases for data
- Analyze trends and patterns
- Generate recommendations
- Uses database_query tool
"""

from typing import Dict, Any, List
import json

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
class AnalysisAgent(BaseAgent):
    """
    Analysis Agent: Analyzes data and generates insights.

    Uses database queries to gather data, then LLM to generate analysis.

    Input: Previous research findings or direct data request
    Output: Structured analysis with insights and recommendations
    """

    AGENT_ID = "analysis_agent"
    AGENT_NAME = "Analysis Agent"
    DESCRIPTION = "Analyzes data and generates insights from databases"
    CAPABILITIES = [
        AgentCapability.DATA_ANALYSIS,
        AgentCapability.WEB_SEARCH,
        AgentCapability.DOCUMENT_ANALYSIS,
    ]
    ALLOWED_TOOLS = ["database_query", "web_search"]
    VERSION = "1.0.0"

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute analysis task.

        Input:
        {
            instruction: "Analyze user engagement metrics",
            context: {
                "query": "SELECT user_id, engagement_score FROM users WHERE active=true",
                "previous_findings": "..."
            }
        }

        Output:
        {
            status: "completed",
            result: {
                "analysis": "...",
                "insights": [...],
                "recommendations": [...]
            }
        }
        """
        try:
            instruction = task_input.instruction
            context = task_input.context or {}
            previous_results = context.get("previous_results") or {}

            # Decide the data source. Priority:
            # 1. Upstream pipeline results (research findings) — the normal
            #    multi-agent case: analyze what the previous agent produced.
            # 2. An explicit SQL query in context, or a request that is
            #    clearly about platform data — use the database tool.
            # 3. Neither — analyze the instruction directly from knowledge.
            data_source = "previous_results" if previous_results else None
            query = context.get("query")
            rows: list = []

            if data_source == "previous_results":
                await report_progress(
                    task_input.workflow_id, self.AGENT_ID,
                    "Analyzing upstream findings…",
                )

            if data_source is None and (query or self._is_platform_data_request(instruction)):
                data_source = "database_query"
                await report_progress(
                    task_input.workflow_id, self.AGENT_ID,
                    "Querying platform database…",
                )
                if not query:
                    query = await self._generate_platform_query(task_input, instruction)

                tool_gateway = get_tool_gateway()
                data_result = await tool_gateway.execute_tool(
                    agent_id=self.AGENT_ID,
                    tool_name="database_query",
                    tool_input={"query": query, "max_rows": 100},
                )
                if data_result.get("success"):
                    rows = data_result.get("rows", [])
                else:
                    # Bad generated SQL shouldn't kill the pipeline — fall
                    # back to knowledge-based analysis and say so.
                    data_source = "knowledge"

            if data_source is None:
                data_source = "knowledge"

            # Build the analysis prompt from the Prompt Registry, using
            # whichever data-source template applies
            registry = get_prompt_registry()
            if data_source == "previous_results":
                upstream_block = json.dumps(previous_results, indent=2, default=str)[:6000]
                analysis_prompt, prompt_version = registry.render(
                    "analysis_upstream",
                    instruction=instruction,
                    upstream_block=upstream_block,
                )
            elif data_source == "database_query":
                analysis_prompt, prompt_version = registry.render(
                    "analysis_database",
                    instruction=instruction,
                    query=query,
                    row_count=len(rows),
                    data_sample=str(rows[:10]),
                )
            else:
                analysis_prompt, prompt_version = registry.render(
                    "analysis_knowledge",
                    instruction=instruction,
                )
            analysis_prompt += self.skill_addendum(task_input)

            llm_gateway = get_llm_gateway()
            analysis_response = await llm_gateway.generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=analysis_prompt,
                task_type="reasoning",
                max_tokens=self.capped_max_tokens(task_input, 700),
                on_chunk=make_llm_stream_reporter(
                    task_input.workflow_id, self.AGENT_ID, "Generating insights…",
                ),
            )
            analysis = analysis_response.get("text", "")

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "analysis": analysis,
                    "data_source": data_source,
                    **({"query": query, "row_count": len(rows), "data_summary": rows[:5]} if data_source == "database_query" else {}),
                },
                tokens_used=analysis_response.get("tokens", {}),
                metadata={
                    "llm_cost": analysis_response.get("cost", 0),
                    "model": analysis_response.get("model"),
                    "data_source": data_source,
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

    @staticmethod
    def _is_platform_data_request(instruction: str) -> bool:
        """Is the user asking about the platform's own operational data?"""
        lowered = instruction.lower()
        return any(
            kw in lowered
            for kw in (
                "workflow", "agent run", "agent_runs", "approval",
                "audit log", "token usage", "cost per", "our database",
                "platform stats", "platform data",
            )
        )

    async def _generate_platform_query(self, task_input: TaskInput, instruction: str) -> str:
        """Generate a SELECT against the platform schema via LLM."""
        query_prompt = f"""Generate one safe SQL SELECT query (Postgres) for this request: {instruction}

Available tables:
- workflows(workflow_id, user_id, prompt, status, agents_selected, total_cost, total_tokens, execution_time_ms, created_at, completed_at)
- agent_runs(workflow_id, agent_id, agent_name, status, duration_ms, tokens_used, cost, success, created_at)
- approval_requests(workflow_id, agent_id, action, risk_level, status, created_at)

Rules: SELECT only, no comments, no semicolons, LIMIT 100 or less.
Return just the SQL query, nothing else."""
        llm_gateway = get_llm_gateway()
        query_response = await llm_gateway.generate(
            workflow_id=task_input.workflow_id,
            agent_id=self.AGENT_ID,
            prompt=query_prompt,
            task_type="fast",
            max_tokens=200,
        )
        query = query_response.get("text", "").strip()
        # Strip markdown fences if the model added them
        if query.startswith("```"):
            query = query.strip("`")
            if query.lower().startswith("sql"):
                query = query[3:]
        return query.strip()
