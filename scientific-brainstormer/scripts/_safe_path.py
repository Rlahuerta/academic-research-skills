"""Path-traversal-safe path resolution for the scientific-brainstormer scripts.

Centralizes the (skill_dir / relpath).resolve() + is_relative_to() check
that was previously duplicated across evaluate_ideas.py and merge_patches.py.
A future caller that needs to consume a user-supplied path should call
safe_resolve_under() rather than reinvent the check.
"""

from pathlib import Path


def safe_resolve_under(base: Path, relpath: str) -> Path | None:
    """Resolve `relpath` under `base` and confirm containment.

    Returns the resolved Path on success, or None if the path escapes
    `base`, is invalid, or cannot be resolved. Symlinks inside `base`
    are followed (which is what the LLM analyst needs for in-tree
    references); paths that resolve to a location outside `base` are
    rejected.
    """
    try:
        resolved = (Path(base) / relpath).resolve()
    except (ValueError, OSError):
        return None
    try:
        if not resolved.is_relative_to(Path(base).resolve()):
            return None
    except (ValueError, OSError):
        return None
    return resolved
