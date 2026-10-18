"""API endpoints serving the skill catalog (real SKILL.md files)."""

from fastapi import APIRouter, HTTPException

from src.skills.catalog import catalog_json, get_skill

router = APIRouter(prefix="/api/skills", tags=["Skills"])


@router.get("/")
async def list_skills():
    """All enable-able skills with descriptions and target agents."""
    skills = catalog_json()
    return {"skills": skills, "count": len(skills)}


@router.get("/{skill_id}")
async def get_skill_detail(skill_id: str):
    """The complete, unmodified SKILL.md for one skill."""
    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {skill_id}")
    return {
        "id": skill.id,
        "label": skill.label,
        "description": skill.description,
        "category": skill.category,
        "source": skill.source,
        "agents": skill.agents,
        "skill_md": skill.raw,
    }
