"""Shared Markdown validator for the scientific-brainstormer scripts.

Single source of truth for the structural checks that gate every patch
applied to SKILL.md. Previously duplicated (with already-drifted error
strings) in evaluate_ideas.py and merge_patches.py.
"""

import re


def validate_markdown_content(content: str) -> tuple:
    """Validates that patch content is well-formed Markdown.

    Returns (is_valid: bool, errors: list[str]).
    """
    errors = []

    # 1. Check for unbalanced fenced code blocks
    backtick_fences = [m for m in re.finditer(r'^```', content, re.MULTILINE)]
    if len(backtick_fences) % 2 != 0:
        errors.append("Unbalanced triple-backtick code fences (odd number of ``` markers)")

    # 2. Check that fenced code blocks have matching open/close pairs
    in_fence = False
    for i, line in enumerate(content.split('\n')):
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_fence:
                if stripped == '```' or re.match(r'^```\s*$', stripped):
                    in_fence = False  # legitimate closing fence
                else:
                    errors.append(f"Nested code fence near line {i + 1}: '{stripped[:40]}'")
            else:
                in_fence = True   # opening fence
    if in_fence:
        errors.append("Unclosed code fence at end of content")

    # 3. Check headers have proper format: "# " not "#text"
    for match in re.finditer(r'^#{1,6}[^#\s]', content, re.MULTILINE):
        errors.append(f"Malformed header (missing space after #): '{match.group()[:40]}'")

    # 4. Reject empty or whitespace-only content
    if not content.strip():
        errors.append("Content is empty or whitespace-only")

    # 5. Reject content that looks like raw JSON/structured data without markdown
    stripped = content.strip()
    if (stripped.startswith('{') and stripped.endswith('}')) or \
       (stripped.startswith('[') and stripped.endswith(']')):
        # Allow if there's at least one markdown header or list marker
        if not re.search(r'^(#{1,6}\s|\* |\- |\d+\. )', content, re.MULTILINE):
            errors.append("Content appears to be raw JSON/data without markdown structure")

    return (len(errors) == 0, errors)
