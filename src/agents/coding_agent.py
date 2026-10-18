"""
Coding Agent: Writes and executes Python code to solve tasks.

Flow:
1. LLM generates Python code for the task (using any upstream context)
2. Code runs in the sandboxed code_executor tool (isolated subprocess,
   AST-validated, hard timeout) through the Tool Gateway
3. On failure, the LLM gets one shot at fixing its own code from the error
4. Returns the code, its real stdout, and an explanation
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
from src.tools.gateway import get_tool_gateway
from src.llm.gateway import get_llm_gateway
from src.observability.progress import report_progress, make_llm_stream_reporter
from src.prompts.registry import get_prompt_registry


@register_agent
class CodingAgent(BaseAgent):
    """
    Coding Agent: Generates and executes Python code.

    The code runs for real in the code_executor sandbox — output shown to
    the user is actual stdout, not an LLM's guess at what the code would do.
    """

    AGENT_ID = "coding_agent"
    AGENT_NAME = "Coding Agent"
    DESCRIPTION = "Writes Python code and executes it in a sandbox to solve computational tasks"
    CAPABILITIES = [AgentCapability.CODE_GENERATION]
    ALLOWED_TOOLS = ["code_executor"]
    VERSION = "1.0.0"

    # Sandbox constraints the generated code must respect (mirrors
    # CodeExecutorTool._is_safe_code — the LLM needs to know the rules
    # or its code gets rejected before it ever runs)
    SANDBOX_RULES = (
        "The code runs in a restricted sandbox. Allowed imports ONLY: math, "
        "random, statistics, itertools, collections, functools, json, "
        "datetime, re, decimal, fractions, heapq, string, bisect, textwrap. "
        "NO file I/O, no network, no exec/eval, no other imports (no numpy/"
        "pandas). Print all results — stdout is the only output channel."
    )

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute a coding task: generate → run → (fix once if broken).
        """
        try:
            instruction = task_input.instruction
            context = task_input.context or {}
            previous_results = context.get("previous_results") or {}

            total_cost = 0.0
            total_tokens = {"input": 0, "output": 0, "total": 0}

            # Step 1: Generate code
            await report_progress(
                task_input.workflow_id, self.AGENT_ID, "Writing code…",
            )
            code, gen_meta = await self._generate_code(
                task_input, instruction, previous_results
            )
            total_cost += gen_meta["cost"]
            self._add_tokens(total_tokens, gen_meta["tokens"])

            # Step 2: Execute in the sandbox via Tool Gateway
            await report_progress(
                task_input.workflow_id, self.AGENT_ID, "Executing in sandbox…",
            )
            tool_gateway = get_tool_gateway()
            exec_result = await tool_gateway.execute_tool(
                agent_id=self.AGENT_ID,
                tool_name="code_executor",
                tool_input={"code": code},
            )

            # Step 3: One self-fix attempt on failure
            attempts = 1
            if not exec_result.get("success"):
                attempts = 2
                await report_progress(
                    task_input.workflow_id, self.AGENT_ID,
                    "Code failed — fixing from the error…",
                    detail=str(exec_result.get("error", ""))[:120],
                )
                code, fix_meta = await self._fix_code(
                    task_input, instruction, code,
                    exec_result.get("error", "unknown error"),
                )
                total_cost += fix_meta["cost"]
                self._add_tokens(total_tokens, fix_meta["tokens"])

                exec_result = await tool_gateway.execute_tool(
                    agent_id=self.AGENT_ID,
                    tool_name="code_executor",
                    tool_input={"code": code},
                )

            output_text = exec_result.get("output", "")
            succeeded = bool(exec_result.get("success"))

            # Step 4: Brief explanation of what the code does + what it found
            summary_prompt, _ = get_prompt_registry().render(
                "coding_summary",
                instruction=instruction,
                code=code,
                outcome_label="output" if succeeded else "FAILED with error",
                outcome_text=output_text if succeeded else exec_result.get("error", ""),
            )
            summary_response = await get_llm_gateway().generate(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                prompt=summary_prompt,
                task_type="fast",
                max_tokens=self.capped_max_tokens(task_input, 250),
            )
            total_cost += summary_response.get("cost", 0)
            self._add_tokens(total_tokens, summary_response.get("tokens", {}))

            if not succeeded:
                return TaskOutput(
                    task_id=task_input.task_id,
                    workflow_id=task_input.workflow_id,
                    status=AgentStatus.FAILED,
                    error={
                        "type": "CodeExecutionError",
                        "message": f"Code failed after {attempts} attempts: {exec_result.get('error')}",
                        "retryable": True,
                    },
                    tokens_used=total_tokens,
                    metadata={"llm_cost": total_cost},
                )

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "code": code,
                    "execution_output": output_text,
                    "summary": summary_response.get("text", ""),
                    "execution_time_ms": exec_result.get("execution_time_ms"),
                    "attempts": attempts,
                },
                tokens_used=total_tokens,
                metadata={
                    "llm_cost": total_cost,
                    "model": summary_response.get("model"),
                    "prompt_version": getattr(self, "_prompt_version", None),
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

    async def _generate_code(
        self,
        task_input: TaskInput,
        instruction: str,
        previous_results: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        """Ask the LLM for sandbox-compatible Python code."""
        upstream = ""
        if previous_results:
            upstream = (
                "\nUpstream context from previous agents (use relevant "
                "facts/numbers from it):\n"
                + json.dumps(previous_results, default=str)[:3000]
            )

        prompt, self._prompt_version = get_prompt_registry().render(
            "coding_generate",
            instruction=instruction,
            upstream=upstream,
            sandbox_rules=self.SANDBOX_RULES,
        )
        prompt += self.skill_addendum(task_input)

        response = await get_llm_gateway().generate(
            workflow_id=task_input.workflow_id,
            agent_id=self.AGENT_ID,
            prompt=prompt,
            task_type="coding",
            max_tokens=self.capped_max_tokens(task_input, 800),
            temperature=0.2,
            on_chunk=make_llm_stream_reporter(
                task_input.workflow_id, self.AGENT_ID, "Writing code…",
            ),
        )
        code = self._strip_fences(response.get("text", ""))
        return code, {"cost": response.get("cost", 0), "tokens": response.get("tokens", {})}

    async def _fix_code(
        self,
        task_input: TaskInput,
        instruction: str,
        code: str,
        error: str,
    ) -> tuple[str, Dict[str, Any]]:
        """One repair attempt from the real execution error."""
        prompt, _ = get_prompt_registry().render(
            "coding_fix",
            instruction=instruction,
            code=code,
            error=error,
            sandbox_rules=self.SANDBOX_RULES,
        )
        response = await get_llm_gateway().generate(
            workflow_id=task_input.workflow_id,
            agent_id=self.AGENT_ID,
            prompt=prompt,
            task_type="coding",
            max_tokens=self.capped_max_tokens(task_input, 800),
            temperature=0.2,
        )
        code = self._strip_fences(response.get("text", ""))
        return code, {"cost": response.get("cost", 0), "tokens": response.get("tokens", {})}

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences if the model added them anyway."""
        text = text.strip()
        match = re.match(r"^```(?:python)?\s*\n(.*?)\n?```$", text, re.DOTALL)
        return match.group(1).strip() if match else text

    @staticmethod
    def _add_tokens(total: Dict[str, int], tokens: Optional[Dict[str, int]]) -> None:
        for key in ("input", "output", "total"):
            total[key] = total.get(key, 0) + (tokens or {}).get(key, 0)
