"""
Supervisor Agent Prompts for LLM-powered planning.

Defines the system prompts and templates for LLM-based DAG generation.
"""

# System prompt for LLM-based task planning
SUPERVISOR_SYSTEM_PROMPT = """You are an intelligent workflow planner. Your job is to analyze user requests and create an execution plan using available agents.

You have access to these agents:

1. **research_agent**
   - Capabilities: web_search, document_analysis
   - Tools: web_search
   - Purpose: Gather information from web and documents
   - Output: Research findings, summaries, aggregated data

2. **analysis_agent**
   - Capabilities: data_analysis, web_search, document_analysis
   - Tools: database_query, web_search
   - Purpose: Analyze data, identify patterns, generate insights
   - Output: Insights, patterns, recommendations, metrics analysis

3. **writer_agent**
   - Capabilities: writing
   - Tools: document_reader
   - Purpose: Generate professional written content
   - Output: Reports, summaries, documentation, structured content

Your task: Given a user request, determine which agents are needed and in what order.

Rules:
1. Always research BEFORE analyzing (analysis needs data)
2. Always analyze/research BEFORE writing (writing needs content)
3. Use the minimum agents needed to fulfill the request
4. If the request is complex, use multiple agents in sequence
5. Each agent depends on previous agents (linear execution for MVP)

Output format MUST be valid JSON:
{
  "agents": ["research_agent", "analysis_agent", "writer_agent"],
  "reasoning": "Brief explanation of why these agents are needed",
  "confidence": 0.95
}

The "agents" array should contain agent IDs in execution order.
"""

SUPERVISOR_USER_PROMPT_TEMPLATE = """
User request: {instruction}

Analyze this request and determine which agents are needed.

Consider:
1. Does the request ask for research/information gathering? → research_agent
2. Does the request ask for analysis/insights? → analysis_agent
3. Does the request ask for writing/reporting? → writer_agent
4. Is it a combination? → Use multiple agents in logical order

Provide your response in the required JSON format.
"""


def get_supervisor_planning_prompt(instruction: str) -> str:
    """
    Get the full planning prompt for the Supervisor.

    Args:
        instruction: User request/instruction

    Returns:
        Full prompt to send to LLM
    """
    return SUPERVISOR_USER_PROMPT_TEMPLATE.format(instruction=instruction)


# Validation rules for generated DAGs
def validate_generated_dag(agents: list[str]) -> tuple[bool, str]:
    """
    Validate a generated DAG.

    Args:
        agents: List of agent IDs

    Returns:
        (is_valid, error_message)
    """
    valid_agents = {"research_agent", "analysis_agent", "writer_agent"}

    # Check all agents are valid
    for agent in agents:
        if agent not in valid_agents:
            return False, f"Unknown agent: {agent}"

    # Check no duplicates
    if len(agents) != len(set(agents)):
        return False, "Duplicate agents in plan"

    # Check valid ordering (research before analysis, analysis before write)
    agent_indices = {agent: idx for idx, agent in enumerate(agents)}

    if "analysis_agent" in agent_indices and "research_agent" in agent_indices:
        if agent_indices["analysis_agent"] < agent_indices["research_agent"]:
            return False, "Analysis must come after research"

    if "writer_agent" in agent_indices:
        # Writer should come last
        if agent_indices["writer_agent"] < len(agents) - 1:
            return False, "Writer must be last (or standalone)"

    return True, ""


# Example good DAG patterns
GOOD_DAG_PATTERNS = [
    ["research_agent"],
    ["analysis_agent"],
    ["writer_agent"],
    ["research_agent", "writer_agent"],
    ["research_agent", "analysis_agent"],
    ["analysis_agent", "writer_agent"],
    ["research_agent", "analysis_agent", "writer_agent"],
]
