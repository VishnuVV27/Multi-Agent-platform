from typing import List, Dict, Any
import json

from src.agents.base import (
    BaseAgent,
    TaskInput,
    TaskOutput,
    AgentStatus,
    AgentCapability,
    register_agent,
)


class TaskDefinition(dict):
    """A single task in the DAG."""
    def __init__(self, task_id: str, agent: str, input: str, depends_on: List[str] = None):
        super().__init__(
            id=task_id,
            agent=agent,
            input=input,
            depends_on=depends_on or []
        )


@register_agent
class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent: Analyzes user prompts and generates task DAGs.

    For MVP: Uses hardcoded rules to map requests to agent pipelines.
    Later: Will use LLM to dynamically generate DAGs.

    Examples:
    - "Research competitors" → [research_agent]
    - "Research and analyze competitors" → [research_agent → analysis_agent]
    - "Write a report on X" → [research_agent → writer_agent]
    """

    AGENT_ID = "supervisor_agent"
    AGENT_NAME = "Supervisor Agent"
    DESCRIPTION = "Analyzes user requests and generates task DAGs for multi-agent execution"
    CAPABILITIES = [AgentCapability.PLANNING]
    ALLOWED_TOOLS = []  # Supervisor doesn't need tools yet
    VERSION = "1.0.0-hardcoded"

    # Hardcoded rules for MVP (will be replaced with LLM logic)
    KEYWORD_RULES = {
        # Keywords that trigger research
        ("research", "search", "find", "gather", "collect"): ["research_agent"],

        # Keywords that trigger analysis
        ("analyze", "compare", "evaluate", "metrics", "data"): ["analysis_agent"],

        # Keywords that trigger both research and analysis
        ("research and analyze", "analyze competitors", "research competitors"): ["research_agent", "analysis_agent"],

        # Keywords that trigger writing
        ("write", "report", "document", "generate", "create"): ["writer_agent"],

        # Combined workflows (most common patterns)
        ("research and write", "write about"): ["research_agent", "writer_agent"],
        ("research analyze and write", "comprehensive report", "detailed report"): ["research_agent", "analysis_agent", "writer_agent"],
        ("analyze and write", "report on"): ["analysis_agent", "writer_agent"],
    }

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Generate a task DAG based on the instruction.

        Input: {instruction: "Research competitors and analyze them"}
        Output: {
            result: {
                tasks: [
                    {id: "t1", agent: "research_agent", input: "..."},
                    {id: "t2", agent: "analysis_agent", input: "...", depends_on: ["t1"]}
                ]
            }
        }
        """
        try:
            instruction = task_input.instruction.lower()

            # Step 1: Determine which agents are needed (hardcoded rules for MVP)
            agents_needed = self._match_agents_to_request(instruction)

            if not agents_needed:
                # Default: assume research is always needed
                agents_needed = ["research_agent"]

            # Step 2: Build task DAG with dependencies
            task_dag = self._build_task_dag(
                agents=agents_needed,
                original_instruction=task_input.instruction,
                context=task_input.context,
            )

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "tasks": task_dag,
                    "agent_count": len(agents_needed),
                    "planning_method": "hardcoded_rules",  # Will change to "llm" later
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
                    "retryable": False,
                },
            )

    def _match_agents_to_request(self, instruction: str) -> List[str]:
        """
        Match user instruction to required agents using hardcoded rules.

        Args:
            instruction: User request (lowercase)

        Returns:
            List of agent IDs needed for this request
        """
        matched_agents = []

        # Check against all rules (longest match first to avoid conflicts)
        for keywords, agents in sorted(
            self.KEYWORD_RULES.items(),
            key=lambda x: max(len(kw) for kw in x[0]),
            reverse=True
        ):
            for keyword in keywords:
                if keyword in instruction:
                    matched_agents = agents
                    break
            if matched_agents:
                break

        return matched_agents

    def _build_task_dag(
        self,
        agents: List[str],
        original_instruction: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build a task DAG (list of tasks with dependencies).

        For MVP, dependencies are sequential (each task depends on the previous one).
        Later: Can add parallel tasks, dynamic parallelization, etc.

        Args:
            agents: List of agent IDs in order
            original_instruction: The original user instruction
            context: Request context

        Returns:
            List of task definitions with IDs and dependencies
        """
        task_dag = []
        previous_task_id = None

        for i, agent_id in enumerate(agents):
            task_id = f"t{i + 1}"

            # Create task input for this agent
            task_input = self._create_task_input(
                agent_id=agent_id,
                instruction=original_instruction,
                context=context,
                previous_task_id=previous_task_id,
            )

            task_def = {
                "id": task_id,
                "agent": agent_id,
                "input": task_input,
                "depends_on": [previous_task_id] if previous_task_id else [],
            }

            task_dag.append(task_def)
            previous_task_id = task_id

        return task_dag

    def _create_task_input(
        self,
        agent_id: str,
        instruction: str,
        context: Dict[str, Any],
        previous_task_id: str = None,
    ) -> str:
        """
        Create the instruction for a specific agent in the pipeline.

        Args:
            agent_id: Target agent ID
            instruction: Original user instruction
            context: Request context
            previous_task_id: ID of previous task (if any)

        Returns:
            Tailored instruction for this agent
        """
        prev_note = (
            f"(You will receive results from task {previous_task_id}). "
            if previous_task_id
            else ""
        )

        # Map agent IDs to specific instructions
        if agent_id == "research_agent":
            return f"Research and gather information on: {instruction}"

        elif agent_id == "analysis_agent":
            return f"Analyze the data/findings related to: {instruction}. {prev_note}Provide insights and patterns."

        elif agent_id == "writer_agent":
            return f"Write a professional report about: {instruction}. {prev_note}Make it well-structured, clear, and actionable."

        else:
            return instruction

    def get_manifest(self) -> Dict[str, Any]:
        """Return agent manifest."""
        return {
            **super().get_manifest(),
            "planning_method": "hardcoded_rules",
            "future_planning_method": "llm_powered",
        }
