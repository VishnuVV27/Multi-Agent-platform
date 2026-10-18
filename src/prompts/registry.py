"""
Prompt Registry: versioned, file-based prompt management (CLAUDE.md §6).

Prompts live as template files, NOT hardcoded strings in agent code:

    src/prompts/templates/<prompt_id>/v<MAJOR.MINOR.PATCH>.md

- The highest semver in a prompt's directory is the ACTIVE version — editing
  behavior means adding a new file (v1.1.0.md), never mutating history, so
  every change is a reviewable git diff and instantly rollback-able by
  deleting the newest file.
- Templates use {{variable}} placeholders. Rendering is plain token
  replacement (not str.format), so literal braces in templates — JSON output
  examples, code snippets — need no escaping.
- Agents stamp the version they used into TaskOutput.metadata, which lands
  on the agent_runs row: every recorded run says exactly which prompt
  produced it.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import logging
import re
import threading

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.md$")
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Prompt:
    """A resolved prompt template."""
    prompt_id: str
    version: str
    template: str

    def render(self, **variables: str) -> str:
        """
        Fill {{placeholders}}. Raises on placeholders left unfilled so a
        renamed variable fails loudly at call time, not silently in the LLM.
        """
        text = self.template
        for name, value in variables.items():
            text = text.replace("{{" + name + "}}", str(value))

        unfilled = _PLACEHOLDER_RE.findall(text)
        if unfilled:
            raise ValueError(
                f"Prompt '{self.prompt_id}' v{self.version} has unfilled "
                f"placeholders: {sorted(set(unfilled))}"
            )
        return text


class PromptRegistry:
    """Loads and caches versioned prompt templates from disk."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR):
        self._dir = templates_dir
        self._cache: Dict[str, Prompt] = {}
        self._lock = threading.Lock()

    def get(self, prompt_id: str) -> Prompt:
        """Get the ACTIVE (highest) version of a prompt."""
        with self._lock:
            if prompt_id in self._cache:
                return self._cache[prompt_id]

        versions = self._versions_of(prompt_id)
        if not versions:
            raise KeyError(f"No prompt templates found for '{prompt_id}'")

        version, path = versions[-1]
        prompt = Prompt(
            prompt_id=prompt_id,
            version=".".join(map(str, version)),
            template=path.read_text(encoding="utf-8"),
        )
        with self._lock:
            self._cache[prompt_id] = prompt
        return prompt

    def render(self, prompt_id: str, **variables: str) -> Tuple[str, str]:
        """Render the active version. Returns (text, version) for stamping."""
        prompt = self.get(prompt_id)
        return prompt.render(**variables), prompt.version

    def catalog(self) -> List[Dict]:
        """All prompts with their versions — for the /api/prompts endpoint."""
        entries = []
        if not self._dir.is_dir():
            return entries
        for prompt_dir in sorted(self._dir.iterdir()):
            if not prompt_dir.is_dir():
                continue
            versions = self._versions_of(prompt_dir.name)
            if not versions:
                continue
            active_version, active_path = versions[-1]
            entries.append({
                "prompt_id": prompt_dir.name,
                "active_version": ".".join(map(str, active_version)),
                "versions": [".".join(map(str, v)) for v, _ in versions],
                "preview": active_path.read_text(encoding="utf-8")[:200],
            })
        return entries

    def _versions_of(self, prompt_id: str) -> List[Tuple[Tuple[int, int, int], Path]]:
        """Sorted (ascending) list of (semver_tuple, path) for a prompt."""
        prompt_dir = self._dir / prompt_id
        if not prompt_dir.is_dir():
            return []
        found = []
        for path in prompt_dir.iterdir():
            match = _VERSION_RE.match(path.name)
            if match:
                found.append((tuple(int(g) for g in match.groups()), path))
        return sorted(found)


_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    """Get the global prompt registry."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
