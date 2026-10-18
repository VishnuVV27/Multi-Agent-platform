"""
API endpoints for the Prompt Registry (CLAUDE.md component 6).

Read-only for now: prompts change via git (new template file = new version),
so the API surfaces the catalog rather than mutating it.
"""

from fastapi import APIRouter, HTTPException

from src.prompts.registry import get_prompt_registry

router = APIRouter(prefix="/api/prompts", tags=["Prompts"])


@router.get("/")
async def list_prompts():
    """All registered prompts with their versions and active previews."""
    try:
        catalog = get_prompt_registry().catalog()
        return {"prompts": catalog, "count": len(catalog)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str):
    """Full active template for one prompt."""
    try:
        prompt = get_prompt_registry().get(prompt_id)
        return {
            "prompt_id": prompt.prompt_id,
            "version": prompt.version,
            "template": prompt.template,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown prompt: {prompt_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
