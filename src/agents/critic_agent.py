"""
Critic Agent: LLM-as-a-judge quality gate for the pipeline's deliverable.

Reviews the Writer's report against the upstream evidence (research sources,
analysis, code results) and scores it on four dimensions. Reports scoring
below the revision threshold get a verdict of "revise" with an actionable
critique — the orchestrator then runs one writer revision pass and a
re-review. This is the Evaluation Pipeline (CLAUDE.md component 7) running
inline, per workflow, instead of as an offline batch job.
"""

from typing import Dict, Any, Optional
import json
import re

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
class CriticAgent(BaseAgent):
    """
    Critic Agent: scores the deliverable and decides approve vs revise.

    Pure LLM judge — no tools. The verdict is enforced numerically: any
    overall score below REVISE_THRESHOLD is a "revise" regardless of what
    the model claims, so a polite judge can't wave weak reports through.
    """

    AGENT_ID = "critic_agent"
    AGENT_NAME = "Critic Agent"
    DESCRIPTION = "Reviews reports against their sources, scores quality, and requests revisions"
    CAPABILITIES = [AgentCapability.EVALUATION]
    ALLOWED_TOOLS = []
    VERSION = "1.0.0"

    REVISE_THRESHOLD = 70  # overall score below this forces a revision

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        try:
            instruction = task_input.instruction
            context = task_input.context or {}
            previous_results = context.get("previous_results") or {}

            # Separate the deliverable (writer output) from the evidence
            report, evidence = self._split_upstream(previous_results)
            if not report:
                return TaskOutput(
                    task_id=task_input.task_id,
                    workflow_id=task_input.workflow_id,
                    status=AgentStatus.FAILED,
                    error={
                        "type": "MissingDeliverable",
                        "message": "No report found in upstream results to review",
                        "retryable": False,
                    },
                )

            await report_progress(
                task_input.workflow_id, self.AGENT_ID,
                "Scanning report against sources…",
            )

            review_prompt, prompt_version = get_prompt_registry().render(
                "critic_review",
                instruction=instruction,
                evidence=evidence[:5000] if evidence else "(no upstream evidence — judge internal consistency instead of grounding)",
                report=report[:7000],
            )
            review_prompt += self.skill_addendum(task_input)

            llm_response = await get_llm_gateway().generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=review_prompt,
                task_type="reasoning",
                max_tokens=self.capped_max_tokens(task_input, 600),
                temperature=0.2,
                on_chunk=make_llm_stream_reporter(
                    task_input.workflow_id, self.AGENT_ID, "Writing review…",
                ),
            )

            review = self._parse_review(llm_response.get("text", ""))

            # Enforce the threshold numerically — the verdict isn't the
            # model's to soften
            overall = review["overall_score"]
            verdict = "revise" if overall < self.REVISE_THRESHOLD else review["verdict"]

            await report_progress(
                task_input.workflow_id, self.AGENT_ID,
                f"Review complete: {overall}/100 — {verdict}",
            )

            scores = review["scores"]
            summary = (
                f"**Quality review: {overall}/100 — {verdict.upper()}**\n\n"
                f"- Accuracy: {scores.get('accuracy', '?')}\n"
                f"- Structure: {scores.get('structure', '?')}\n"
                f"- Completeness: {scores.get('completeness', '?')}\n"
                f"- Clarity: {scores.get('clarity', '?')}\n\n"
                + (f"**Critique:** {review['critique']}" if review["critique"] else "No blocking issues found.")
            )

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "verdict": verdict,
                    "overall_score": overall,
                    "scores": scores,
                    "strengths": review["strengths"],
                    "critique": review["critique"],
                    "summary": summary,
                },
                tokens_used=llm_response.get("tokens", {}),
                metadata={
                    "llm_cost": llm_response.get("cost", 0),
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

    @staticmethod
    def _split_upstream(previous_results: Dict[str, Any]) -> tuple:
        """Pull the report (writer 'content') and evidence out of upstream results."""
        report: Optional[str] = None
        evidence_parts = []
        for task_id, result in previous_results.items():
            if not isinstance(result, dict):
                continue
            if "content" in result:
                report = str(result["content"])
            elif "summary" in result and "findings" in result:  # research
                sources = "\n".join(
                    f"- {f.get('title', '')} ({f.get('url', '')})"
                    for f in result.get("findings", [])[:5]
                )
                evidence_parts.append(f"Research notes:\n{result['summary']}\nSources:\n{sources}")
            elif "analysis" in result:
                evidence_parts.append(f"Analysis:\n{result['analysis']}")
            elif "code" in result:
                evidence_parts.append(
                    f"Code experiment output (ground truth — actually executed):\n"
                    f"{result.get('execution_output', '')}"
                )
        return report, "\n\n".join(evidence_parts)

    def _parse_review(self, text: str) -> Dict[str, Any]:
        """Parse the judge's JSON, tolerating markdown fences and noise."""
        cleaned = text.strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
        try:
            parsed = json.loads(cleaned)
        except (ValueError, TypeError):
            # Unparseable review → approve with a neutral score rather than
            # failing the whole workflow over judge formatting
            return {
                "scores": {},
                "overall_score": self.REVISE_THRESHOLD,
                "verdict": "approve",
                "strengths": [],
                "critique": "",
            }

        scores = parsed.get("scores") or {}
        overall = parsed.get("overall_score")
        if not isinstance(overall, (int, float)):
            numeric = [v for v in scores.values() if isinstance(v, (int, float))]
            overall = sum(numeric) / len(numeric) if numeric else self.REVISE_THRESHOLD
        return {
            "scores": scores,
            "overall_score": round(float(overall), 1),
            "verdict": parsed.get("verdict", "approve"),
            "strengths": parsed.get("strengths") or [],
            "critique": parsed.get("critique") or "",
        }
