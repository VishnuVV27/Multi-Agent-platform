from typing import List, Dict, Any, Optional
import json

from src.agents.base import (
    BaseAgent,
    TaskInput,
    TaskOutput,
    AgentStatus,
    AgentCapability,
    register_agent,
)
from src.llm.gateway import get_llm_gateway
from src.prompts.registry import get_prompt_registry
from src.agents.supervisor_prompts import (
    validate_generated_dag,
    GOOD_DAG_PATTERNS,
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
    Supervisor Agent: Analyzes user prompts and generates task DAGs using LLM.

    Now LLM-powered: Uses Claude to intelligently plan multi-agent workflows.

    Examples:
    - "Research competitors" → [research_agent]
    - "Research and analyze competitors" → [research_agent → analysis_agent]
    - "Write a report on X" → [research_agent → writer_agent]
    - Natural language requests → Optimal agent pipeline
    """

    AGENT_ID = "supervisor_agent"
    AGENT_NAME = "Supervisor Agent"
    DESCRIPTION = "Uses LLM to analyze user requests and generate optimal task DAGs"
    CAPABILITIES = [AgentCapability.PLANNING]
    ALLOWED_TOOLS = []  # Supervisor doesn't need tools
    VERSION = "2.0.0-llm-powered"  # Updated to LLM version

    # Hardcoded rules — fallback path only, used when LLM planning fails.
    # research_agent/analysis_agent produce raw notes, not a deliverable, so
    # real users get a coherent answer regardless of exact phrasing: these
    # default to ending in writer_agent rather than requiring the user to
    # separately say "write" or "report" (see SUPERVISOR_SYSTEM_PROMPT for
    # the same principle applied to the LLM-powered path).
    # Note: _match_agents_to_request() sorts by longest keyword phrase, not
    # dict order, so multi-word phrases below correctly take priority over
    # the shorter single-word groups regardless of listing order.
    KEYWORD_RULES = {
        ("research analyze and write", "comprehensive report", "detailed report"): ["research_agent", "analysis_agent", "writer_agent", "critic_agent"],
        ("research and analyze", "analyze competitors", "research competitors"): ["research_agent", "analysis_agent", "writer_agent", "critic_agent"],
        ("research and write", "write about"): ["research_agent", "writer_agent"],
        ("analyze and write", "report on"): ["analysis_agent", "writer_agent"],

        # Code + research combos run their source agents in parallel
        ("research and code", "code and research", "calculate and research"): ["research_agent", "coding_agent", "writer_agent"],

        # Code-oriented requests
        ("write code", "python script", "calculate", "compute", "simulate", "algorithm"): ["coding_agent", "writer_agent"],

        # Research-oriented requests: still end in writer_agent by default
        ("research", "search", "find", "gather", "collect"): ["research_agent", "writer_agent"],

        # Analysis-oriented requests: still end in writer_agent by default
        ("analyze", "compare", "evaluate", "metrics", "data"): ["analysis_agent", "writer_agent"],

        # Pure writing requests (no research/analysis keyword matched above) —
        # assume the instruction itself has enough content to write from.
        ("write", "report", "document", "generate", "create"): ["writer_agent"],
    }

    async def execute(self, task_input: TaskInput) -> TaskOutput:
        """
        Generate a task DAG using LLM-based planning.

        Input: {instruction: "Research competitors and write a comprehensive report"}
        Output: {
            result: {
                tasks: [
                    {id: "t1", agent: "research_agent", input: "..."},
                    {id: "t2", agent: "writer_agent", input: "...", depends_on: ["t1"]}
                ],
                planning_method: "llm"
            }
        }
        """
        try:
            instruction = task_input.instruction

            # Step 1: Use LLM to determine which agents are needed (NEW!)
            agents_needed = await self._plan_with_llm(instruction, task_input)

            if not agents_needed:
                # Fallback: use hardcoded rules
                agents_needed = self._match_agents_to_request(instruction.lower())

            if not agents_needed:
                # Last resort: research + synthesize, not raw research notes
                agents_needed = ["research_agent", "writer_agent"]

            # Skill-targeted agents must be in the plan: skills are
            # instruction modules injected into specific agents — enabling
            # one is meaningless if its target agent never runs. (Additive
            # only; skills never REMOVE agents from the plan.)
            enabled_skills = (task_input.context or {}).get("enabled_skills") or []
            if enabled_skills:
                from src.skills.catalog import SKILLS_BY_ID
                targeted = {
                    agent
                    for sid in enabled_skills
                    for agent in (SKILLS_BY_ID.get(sid).agents if SKILLS_BY_ID.get(sid) else [])
                }
                # Skip the all-agent skills (e.g. caveman) — they apply to
                # whatever runs, they don't demand everything runs
                if len(targeted) < len(self.AGENT_ORDER):
                    for agent in self.AGENT_ORDER:
                        if agent in targeted and agent not in agents_needed:
                            agents_needed.append(agent)
                    agents_needed = [a for a in self.AGENT_ORDER if a in agents_needed]

            # Quality-gate POLICY (not left to the LLM planner): every fresh
            # deliverable gets a critic review. The planner tends to omit the
            # critic because RAG memory feeds it pre-critic historical plans;
            # a platform guarantee shouldn't depend on prompt luck. Follow-up
            # revisions skip it — the user is already steering quality by hand.
            if (
                "writer_agent" in agents_needed
                and "critic_agent" not in agents_needed
                and not (task_input.context or {}).get("follow_up")
            ):
                agents_needed.append("critic_agent")

            # Step 2: Build task DAG with dependencies
            task_dag = self._build_task_dag(
                agents=agents_needed,
                original_instruction=instruction,
                context=task_input.context,
            )

            return TaskOutput(
                task_id=task_input.task_id,
                workflow_id=task_input.workflow_id,
                status=AgentStatus.COMPLETED,
                result={
                    "tasks": task_dag,
                    "agent_count": len(agents_needed),
                    "planning_method": "llm",  # Now LLM-powered!
                    "agents_selected": agents_needed,
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

    # Agents that gather primary material and can run CONCURRENTLY when the
    # plan contains more than one of them (no data dependency between a web
    # research pass and a coding pass — both start from the user request).
    SOURCE_AGENTS = {"research_agent", "coding_agent"}

    # Canonical pipeline order (used for skill-hint formatting)
    AGENT_ORDER = ["research_agent", "coding_agent", "analysis_agent", "writer_agent", "critic_agent"]

    def _build_task_dag(
        self,
        agents: List[str],
        original_instruction: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build a task DAG with real parallelism.

        Dependency rules:
        - Source agents (research, coding) have no dependencies on each
          other — Temporal executes them in the same wave, concurrently.
        - Every non-source agent (analysis, writer) depends on ALL tasks
          before it in the plan, joining the parallel branches.

        Example: [research, coding, writer] →
          t1 research (no deps) ─┐
          t2 coding  (no deps) ─┴→ t3 writer (depends on t1, t2)

        Args:
            agents: List of agent IDs in plan order
            original_instruction: The original user instruction
            context: Request context

        Returns:
            List of task definitions with IDs and dependencies
        """
        task_dag: List[Dict[str, Any]] = []
        completed_ids: List[str] = []

        for i, agent_id in enumerate(agents):
            task_id = f"t{i + 1}"

            if agent_id in self.SOURCE_AGENTS and all(
                task_dag[j]["agent"] in self.SOURCE_AGENTS for j in range(i)
            ):
                # Still in the initial source wave — run concurrently
                depends_on: List[str] = []
            else:
                # Join point: depend on everything planned so far
                depends_on = list(completed_ids)

            task_input = self._create_task_input(
                agent_id=agent_id,
                instruction=original_instruction,
                context=context,
                previous_task_id=depends_on[-1] if depends_on else None,
            )

            task_dag.append({
                "id": task_id,
                "agent": agent_id,
                "input": task_input,
                "depends_on": depends_on,
            })
            completed_ids.append(task_id)

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

        elif agent_id == "coding_agent":
            return f"Write and execute Python code for the computational part of: {instruction}"

        elif agent_id == "analysis_agent":
            return f"Analyze the data/findings related to: {instruction}. {prev_note}Provide insights and patterns."

        elif agent_id == "writer_agent":
            return f"Write a professional report about: {instruction}. {prev_note}Make it well-structured, clear, and actionable."

        elif agent_id == "critic_agent":
            return (
                f"Review the report produced for: {instruction}. {prev_note}"
                "Score it against the upstream evidence and decide approve or revise."
            )

        else:
            return instruction

    async def _plan_with_llm(
        self,
        instruction: str,
        task_input: TaskInput,
    ) -> Optional[List[str]]:
        """
        Use LLM to plan the optimal agent pipeline.

        Enhanced with memory context: retrieves similar past workflows
        to inform planning decisions.

        Args:
            instruction: User request
            task_input: Task input for context

        Returns:
            List of agent IDs in execution order, or None if planning fails
        """
        try:
            # Step 1: Retrieve similar workflows from memory for context
            memory_context = ""
            try:
                from src.memory.memory_store import MemoryStore
                from src.memory.models import RetrievalRequest

                memory_store = MemoryStore()
                retrieval_request = RetrievalRequest(
                    query=instruction,
                    top_k=3,
                    min_similarity=0.6,
                    filter_success_only=True,  # Only learn from successful workflows
                )

                memory_response = await memory_store.retrieve_workflows(
                    retrieval_request
                )

                # Format memory context for LLM
                if memory_response.results:
                    memory_context = "Here are 3 similar past requests and how they were handled:\n"
                    for i, ranked in enumerate(memory_response.results, 1):
                        memory = ranked.workflow_memory
                        agents_str = ", ".join(memory.agents_selected)
                        success_pct = memory.success_rate * 100
                        memory_context += (
                            f"{i}. Request: \"{memory.user_request}\"\n"
                            f"   Agents used: [{agents_str}]\n"
                            f"   Success rate: {success_pct:.0f}%\n"
                            f"   Cost: ${memory.total_cost:.4f}\n\n"
                        )

                    memory_context += (
                        "Use these successful patterns to inform your planning decision.\n\n"
                    )

            except Exception as e:
                print(f"Warning: Failed to retrieve memory context: {e}")
                # Continue without memory context if retrieval fails

            # Step 2: Create planning prompt from the Prompt Registry
            # (memory context and follow-up hints are runtime prefixes, not
            # part of the versioned template)
            registry = get_prompt_registry()
            planning_prompt, _ = registry.render(
                "supervisor_planning", instruction=instruction,
            )
            system_prompt, _ = registry.render("supervisor_system")
            if memory_context:
                planning_prompt = memory_context + planning_prompt

            # Skill hint: tell the planner which agents the user's enabled
            # skills target so it includes them where relevant
            enabled_skills = (task_input.context or {}).get("enabled_skills") or []
            if enabled_skills:
                from src.skills.catalog import SKILLS_BY_ID
                skill_notes = [
                    f"{SKILLS_BY_ID[s].label} (targets: {', '.join(SKILLS_BY_ID[s].agents)})"
                    for s in enabled_skills if s in SKILLS_BY_ID
                ]
                if skill_notes:
                    planning_prompt = (
                        "The user enabled these skill modules for this workflow: "
                        + "; ".join(skill_notes)
                        + ". Include the targeted agents in your plan where relevant.\n\n"
                        + planning_prompt
                    )

            # Follow-up runs continue an existing thread: the previous output
            # is already available to the agents, so don't re-plan the full
            # research pipeline for what is usually a revision request.
            if (task_input.context or {}).get("follow_up"):
                planning_prompt = (
                    "NOTE: This is a FOLLOW-UP request refining previous work in an "
                    "existing thread. The previous report/output is automatically "
                    "provided to the agents. For revisions, reformatting, shortening, "
                    "or tone changes prefer just [\"writer_agent\"]. Include "
                    "research_agent only if genuinely new information must be "
                    "gathered, analysis_agent only if new analysis is required.\n\n"
                    + planning_prompt
                )

            # Step 3: Get LLM Gateway
            llm_gateway = get_llm_gateway()

            # Step 4: Call LLM for planning with enhanced context
            response = await llm_gateway.chat(
                workflow_id=task_input.workflow_id,
                agent_id=self.AGENT_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": planning_prompt},
                ],
                task_type="reasoning",
                max_tokens=500,
            )

            # Parse LLM response
            response_text = response.get("text", "").strip()

            # Try to extract JSON from response
            try:
                # Handle case where LLM wraps JSON in markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                else:
                    json_str = response_text

                plan = json.loads(json_str)
                agents = plan.get("agents", [])

                # Validate generated DAG
                is_valid, error = validate_generated_dag(agents)
                if not is_valid:
                    print(f"LLM plan validation failed: {error}. Falling back to hardcoded rules.")
                    return None

                return agents

            except json.JSONDecodeError as e:
                print(f"Failed to parse LLM response as JSON: {e}. Falling back to hardcoded rules.")
                return None

        except Exception as e:
            print(f"LLM planning failed: {e}. Falling back to hardcoded rules.")
            return None

    def get_manifest(self) -> Dict[str, Any]:
        """Return agent manifest."""
        return {
            **super().get_manifest(),
            "planning_method": "llm_powered",
        }
