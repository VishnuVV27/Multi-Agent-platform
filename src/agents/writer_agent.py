"""
Writer Agent: Generates written content.

Capabilities:
- Write reports
- Generate documentation
- Create summaries
- Professional writing
- Uses LLM for content generation
"""

from typing import Dict, Any

from src.agents.base import (
    BaseAgent,
    TaskInput,
    TaskOutput,
    AgentStatus,
    AgentCapability,
    register_agent,
)
from src.llm.gateway import get_llm_gateway


@register_agent
class WriterAgent(BaseAgent):
    """
    Writer Agent: Generates written content.

    Takes research/analysis from previous agents and generates polished reports.

    Input: Raw findings, analysis, or instructions for writing
    Output: Structured written content (reports, summaries, etc.)
    """

    AGENT_ID = "writer_agent"
    AGENT_NAME = "Writer Agent"
    DESCRIPTION = "Generates professional written content and reports"
    CAPABILITIES = [AgentCapability.WRITING]
    ALLOWED_TOOLS = ["document_reader"]
    VERSION = "1.0.0"

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute writing task.

        Input:
        {
            instruction: "Write a comprehensive report on market trends",
            context: {
                "research_findings": "...",
                "analysis_insights": "...",
                "format": "report" (report, summary, documentation, article)
            }
        }

        Output:
        {
            status: "completed",
            result: {
                "content": "...",
                "format": "report",
                "sections": [...]
            }
        }
        """
        try:
            instruction = task_input.instruction
            context = task_input.context or {}

            # Extract writing context
            research = context.get("research_findings", "")
            analysis = context.get("analysis_insights", "")
            format_type = context.get("format", "report")

            # Step 1: Build writing prompt with all available context
            writing_prompt = f"""
You are a professional writer. Generate high-quality {format_type} content.

Original Task: {instruction}

Research Findings:
{research if research else "(No research provided)"}

Analysis & Insights:
{analysis if analysis else "(No analysis provided)"}

Requirements:
1. Professional, clear writing
2. Well-structured with clear sections
3. Actionable recommendations where relevant
4. Proper formatting for {format_type}
5. 500-1000 words

Generate the {format_type} now:
"""

            # Step 2: Generate content using LLM
            llm_gateway = get_llm_gateway()
            response = await llm_gateway.generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=writing_prompt,
                task_type="reasoning",
                max_tokens=2000,  # Larger for writing
            )

            content = response.get("text", "")

            # Step 3: Structure the output
            sections = self._extract_sections(content, format_type)

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "content": content,
                    "format": format_type,
                    "sections": sections,
                    "word_count": len(content.split()),
                },
                tokens_used=response.get("tokens", {}),
                metadata={
                    "llm_cost": response.get("cost", 0),
                    "model": response.get("model"),
                    "format": format_type,
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

    def _extract_sections(self, content: str, format_type: str) -> list:
        """Extract sections from generated content."""
        sections = []

        # Simple section extraction (split by common headers)
        lines = content.split("\n")
        current_section = None

        for line in lines:
            # Check for section headers
            if line.strip().startswith("#"):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "title": line.strip("#").strip(),
                    "content": []
                }
            elif current_section and line.strip():
                current_section["content"].append(line.strip())

        if current_section:
            sections.append(current_section)

        # If no sections found, treat entire content as one
        if not sections:
            sections = [{
                "title": format_type.capitalize(),
                "content": content.split("\n")
            }]

        return sections
