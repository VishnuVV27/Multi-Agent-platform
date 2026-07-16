"""
Analysis Agent: Analyzes data and generates insights.

Capabilities:
- Query databases for data
- Analyze trends and patterns
- Generate recommendations
- Uses database_query tool
"""

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

            # Step 1: Extract data query from context or generate one
            query = context.get("query")
            if not query:
                # Generate query using LLM
                query_prompt = f"""
Based on this request: {instruction}

Generate a safe SQL SELECT query to analyze the data. Only SELECT queries.
Maximum 1000 rows.

Return just the SQL query, nothing else.
"""
                llm_gateway = get_llm_gateway()
                query_response = await llm_gateway.generate(
                    workflow_id=task_input.workflow_id,
                    agent_id=self.AGENT_ID,
                    prompt=query_prompt,
                    task_type="fast",
                    max_tokens=200,
                )
                query = query_response.get("text", "").strip()

            # Step 2: Execute database query through Tool Gateway
            tool_gateway = get_tool_gateway()
            data_result = await tool_gateway.execute_tool(
                agent_id=self.AGENT_ID,
                tool_name="database_query",
                tool_input={"query": query, "max_rows": 100}
            )

            if not data_result.get("success"):
                raise Exception(f"Database query failed: {data_result.get('error')}")

            rows = data_result.get("rows", [])

            # Step 3: Analyze data using LLM
            analysis_prompt = f"""
Analyze this data and provide insights:

Query: {query}
Rows: {len(rows)} results

Data sample:
{str(rows[:5])}

Task: {instruction}

Provide:
1. Key findings (2-3 bullet points)
2. Trends observed
3. Recommendations (2-3 items)

Format as clear, actionable insights.
"""

            llm_gateway = get_llm_gateway()
            analysis_response = await llm_gateway.generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=analysis_prompt,
                task_type="reasoning",
                max_tokens=500,
            )
            analysis = analysis_response.get("text", "")

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "query": query,
                    "row_count": len(rows),
                    "analysis": analysis,
                    "data_summary": rows[:5] if rows else [],
                },
                tokens_used=analysis_response.get("tokens", {}),
                metadata={
                    "llm_cost": analysis_response.get("cost", 0),
                    "model": analysis_response.get("model"),
                    "data_source": "database_query",
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
