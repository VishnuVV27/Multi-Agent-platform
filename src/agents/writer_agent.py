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
from src.observability.progress import report_progress, make_llm_stream_reporter
from src.prompts.registry import get_prompt_registry


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
            format_type = context.get("format", "report")

            # Extract upstream pipeline results (populated by the
            # orchestrator from dependency task outputs). Falls back to the
            # legacy explicit keys if a caller passes them directly.
            upstream_block = self._format_upstream(
                context.get("previous_results") or {},
                research=context.get("research_findings", ""),
                analysis=context.get("analysis_insights", ""),
            )

            # Step 1: Build writing prompt from the Prompt Registry
            writing_prompt, prompt_version = get_prompt_registry().render(
                "writer_report",
                format_type=format_type,
                instruction=instruction,
                upstream_block=upstream_block or "(No upstream results — write from your own knowledge and say so briefly.)",
            )
            writing_prompt += self.skill_addendum(task_input)

            # Step 2: Generate content using LLM (token-streamed so Mission
            # Control's DRAFT monitor shows the report writing itself live)
            await report_progress(
                task_input.workflow_id, self.AGENT_ID, "Drafting report…",
            )
            llm_gateway = get_llm_gateway()
            response = await llm_gateway.generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=writing_prompt,
                task_type="reasoning",
                max_tokens=self.capped_max_tokens(task_input, 2000),  # Larger for writing
                on_chunk=make_llm_stream_reporter(
                    task_input.workflow_id, self.AGENT_ID, "Drafting report…",
                ),
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
    def _format_upstream(previous_results: Dict[str, Any], research: str = "", analysis: str = "") -> str:
        """
        Render upstream task results into a prompt block.

        previous_results looks like {"t1": {research result}, "t2": {analysis
        result}} — pull the human-meaningful fields per agent output shape and
        fall back to compact JSON for anything unrecognized.
        """
        import json

        blocks = []
        for task_id, result in previous_results.items():
            if not isinstance(result, dict):
                blocks.append(f"[{task_id}] {str(result)[:2000]}")
                continue
            if "verdict" in result:  # critic output (check before "summary" — it has both)
                blocks.append(
                    f"[{task_id}] QUALITY REVIEW of your previous draft "
                    f"(score {result.get('overall_score', '?')}/100 — address EVERY point):\n"
                    f"{result.get('critique', '')}"
                )
            elif "code" in result:  # coding agent output (check before "summary")
                blocks.append(
                    f"[{task_id}] Code experiment:\n{result.get('summary', '')}\n"
                    f"Code:\n{str(result['code'])[:1500]}\n"
                    f"Real execution output:\n{str(result.get('execution_output', ''))[:800]}"
                )
            elif "summary" in result:  # research agent output
                sources = "\n".join(
                    f"  - {f.get('title', '')} ({f.get('url', '')})"
                    for f in result.get("findings", [])[:5]
                )
                blocks.append(
                    f"[{task_id}] Research notes:\n{result['summary']}\n"
                    + (f"Sources:\n{sources}" if sources else "")
                )
            elif "analysis" in result:  # analysis agent output
                blocks.append(f"[{task_id}] Analysis:\n{result['analysis']}")
            elif "content" in result:  # prior writer output (follow-up thread)
                blocks.append(
                    f"[{task_id}] Previous report (revise/extend this — do not "
                    f"start over unless asked):\n{str(result['content'])[:4000]}"
                )
            else:
                blocks.append(f"[{task_id}] {json.dumps(result, default=str)[:2000]}")

        if research:
            blocks.append(f"Research findings:\n{research}")
        if analysis:
            blocks.append(f"Analysis & insights:\n{analysis}")

        return "\n\n".join(blocks)

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
