"""
Skill Catalog: real agent skills loaded from authentic SKILL.md files.

Each skill in src/skills/library/<id>/SKILL.md is the GENUINE file from its
source repository (Anthropic's official skills, obra/superpowers,
nextlevelbuilder's ui-ux-pro-max) — frontmatter and instruction body exactly
as published, not paraphrased. Enabling a skill injects its real instruction
body into the prompts of the agents it targets.

What's ours vs theirs:
- SKILL.md content: theirs, verbatim (fetched from the source repo)
- PLATFORM_META (which of OUR agents each skill targets, category): ours —
  the platform has to decide which of its agents a skill applies to.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import re

LIBRARY_DIR = Path(__file__).resolve().parent / "library"

# Cap per-skill injection size: full bodies run 7-20KB; nano handles the
# context fine but there's no need to ship an entire OCR how-to into every
# prompt — the head of a SKILL.md carries its core methodology.
INJECT_MAX_CHARS = 3500

# Platform-side mapping: which of OUR agents each skill's instructions are
# injected into, plus display category and the source repository.
PLATFORM_META: Dict[str, Dict] = {
    "pdf": {
        "agents": ["writer_agent"],
        "category": "documents",
        "source": "anthropics/skills",
    },
    "docx": {
        "agents": ["writer_agent"],
        "category": "documents",
        "source": "anthropics/skills",
    },
    "pptx": {
        "agents": ["writer_agent"],
        "category": "documents",
        "source": "anthropics/skills",
    },
    "xlsx": {
        "agents": ["analysis_agent", "writer_agent"],
        "category": "documents",
        "source": "anthropics/skills",
    },
    "mcp-builder": {
        "agents": ["coding_agent"],
        "category": "development",
        "source": "anthropics/skills",
    },
    "frontend-design": {
        "agents": ["coding_agent", "writer_agent"],
        "category": "development",
        "source": "anthropics/skills",
    },
    "ui-ux-pro-max": {
        "agents": ["coding_agent", "writer_agent"],
        "category": "development",
        "source": "nextlevelbuilder/ui-ux-pro-max-skill",
    },
    "brainstorming": {
        "agents": ["analysis_agent", "writer_agent"],
        "category": "methodology",
        "source": "obra/superpowers",
    },
    "systematic-debugging": {
        "agents": ["coding_agent"],
        "category": "methodology",
        "source": "obra/superpowers",
    },
    "test-driven-development": {
        "agents": ["coding_agent"],
        "category": "methodology",
        "source": "obra/superpowers",
    },
}


@dataclass(frozen=True)
class Skill:
    id: str
    label: str
    description: str
    category: str
    source: str
    agents: List[str] = field(default_factory=list)
    body: str = ""  # the real SKILL.md instruction body (after frontmatter)
    raw: str = ""  # the complete SKILL.md file, untouched


def _parse_skill_md(text: str) -> Dict[str, str]:
    """
    Parse SKILL.md frontmatter (name/description) + body.

    Tolerant line-based parsing rather than a YAML dependency: real skill
    frontmatter is flat key/value, with values sometimes quoted or spilling
    to following indented lines.
    """
    name, description, body = "", "", text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if match:
        frontmatter, body = match.group(1), match.group(2)
        current_key = None
        values: Dict[str, List[str]] = {}
        for line in frontmatter.splitlines():
            key_match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
            if key_match:
                current_key = key_match.group(1)
                values[current_key] = [key_match.group(2)]
            elif current_key and line.startswith((" ", "\t")):
                values[current_key].append(line.strip())
        name = " ".join(values.get("name", [])).strip().strip('"').strip("'")
        description = " ".join(values.get("description", [])).strip().strip('"').strip("'")
    return {"name": name, "description": description, "body": body.strip()}


def _load_skills() -> List[Skill]:
    skills: List[Skill] = []
    for skill_id, meta in PLATFORM_META.items():
        path = LIBRARY_DIR / skill_id / "SKILL.md"
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        parsed = _parse_skill_md(raw)
        skills.append(
            Skill(
                id=skill_id,
                label=parsed["name"] or skill_id,
                description=parsed["description"] or "",
                category=meta["category"],
                source=meta["source"],
                agents=meta["agents"],
                body=parsed["body"],
                raw=raw,
            )
        )
    return skills


SKILLS: List[Skill] = _load_skills()
SKILLS_BY_ID: Dict[str, Skill] = {s.id: s for s in SKILLS}


def instructions_by_agent(enabled_skill_ids: List[str]) -> Dict[str, str]:
    """
    Resolve enabled skills into one instruction block per target agent,
    using the REAL SKILL.md bodies (size-capped per skill).

    Returns {agent_id: combined instruction text}; unknown IDs ignored.
    """
    per_agent: Dict[str, List[str]] = {}
    for skill_id in enabled_skill_ids:
        skill = SKILLS_BY_ID.get(skill_id)
        if not skill:
            continue
        excerpt = skill.body[:INJECT_MAX_CHARS]
        block = f"=== Skill: {skill.label} (source: {skill.source}) ===\n{excerpt}"
        for agent_id in skill.agents:
            per_agent.setdefault(agent_id, []).append(block)
    return {agent: "\n\n".join(items) for agent, items in per_agent.items()}


def catalog_json() -> List[Dict]:
    """Serializable catalog for the API/frontend."""
    return [
        {
            "id": s.id,
            "label": s.label,
            "description": s.description,
            "category": s.category,
            "source": s.source,
            "agents": s.agents,
            "size_bytes": len(s.raw.encode("utf-8")),
        }
        for s in SKILLS
    ]


def get_skill(skill_id: str) -> Optional[Skill]:
    return SKILLS_BY_ID.get(skill_id)
