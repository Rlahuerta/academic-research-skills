#!/usr/bin/env python3
"""Static audit for the v3.7+ Csikszentmihalyi / Toulmin / Lipton discipline
applied to `deep-research/agents/synthesis_agent.md`.

Spec: docs/design/2026-06-01-ars-v3.7-creative-process-discipline-spec.md
(parent: docs/design/2026-04-29-ars-v3.6.7-downstream-agent-pattern-protection-spec.md).

Greps the synthesis agent prompt for the keywords and obligation phrases that
make each v3.7+ clause detectable. Static only — does not validate runtime
behaviour. Behavioural validation belongs to live pipeline evaluation and is
out of scope here.

Falsifiability discipline (inherited from check_v3_6_7_pattern_protection.py):
- Agent-prompt checks scope grep to the `PATTERN PROTECTION (v3.7+)` block
  via `block_marker`. A keyword that lands outside the block in unrelated
  prose does not count toward passing.
- Obligation-bearing patterns (forbidden / required / only-if) are enforced
  via `must_contain_regex` so the prohibition is grep-detectable as a
  contiguous fragment, not as two unrelated nouns elsewhere in the file.

Exit codes: 0 on pass, 1 on any failure.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# NOTE: This file deliberately does NOT use `from __future__ import annotations`.
# The Check dataclass below has `List[str]` annotations, and with the
# __future__ import the dataclass decorator would try to resolve the
# annotation string against the module's globals() at class definition
# time — which fails when the module is loaded via importlib's
# module_from_spec (the test harness does this), because the module is
# not yet registered in sys.modules and its namespace is None.

REPO_ROOT = Path(__file__).resolve().parent.parent

SYNTHESIS_AGENT = REPO_ROOT / "deep-research" / "agents" / "synthesis_agent.md"

# Markdown heading pattern that closes a `block_marker` scope. A check's scope
# starts at the marker and ends at the next H1/H2/H3 heading or EOF.
# (Inherited from check_v3_6_7_pattern_protection.py to keep scoping rules
# consistent across v3.6.7 and v3.7+ pattern-protection checks.)
_HEADING_RE = re.compile(r"^#{1,3} ", re.MULTILINE)

# Negation / weakening patterns, in two groups. (Inherited from v3.6.7.)
# - GENERAL_NEGATION_PATTERNS: imperative prohibitions and weakening modals.
#   These would also reject a legitimate "DO NOT ..." prohibition; callers
#   handle that by passing `allow_prohibition=True` if needed. v3.7+ does
#   not currently use that flag (no checks assert a DO NOT prohibition).
# - ALWAYS_NEGATION_PATTERNS: weakening verbs and adverbs that never
#   constitute a valid prohibition signal.
GENERAL_NEGATION_PATTERNS = [
    r"\bdoes\s+not\b",
    r"\bdo\s+not\b",
    r"\bdon'?t\b",
    r"\bshould\s+not\b",
    r"\bshall\s+not\b",
    r"\bmust\s+not\b",
    r"\bcannot\b",
    r"\bcan'?t\b",
]
ALWAYS_NEGATION_PATTERNS = [
    r"\brarely\b",
    r"\bsometimes\b",
    r"\bfails\s+to\b",
    r"\binstead\s+of\b",
    r"\bis\s+unable\s+to\b",
]


def _run_pattern(
    pattern: str,
    block_text: str,
    allow_prohibition: bool = False,
) -> tuple[bool, str]:
    """Return (passed, detail) for one regex pattern.

    Matching is done on the whitespace-normalized form of `block_text` so
    that line-wrapped phrases in the source (e.g., "three or\\nfour W's")
    are still detected. Negation filtering is done against the original
    line text (since "DO NOT" / "must not" etc. are line-local signals).
    """
    rx = re.compile(pattern, re.IGNORECASE)
    normalized = _normalize(block_text)
    matches = list(rx.finditer(normalized))
    if not matches:
        return False, f"missing required pattern: {pattern!r}"
    if not any(
        not _is_negated(block_text, m, allow_prohibition=allow_prohibition)
        for m in matches
    ):
        return (
            False,
            f"required pattern {pattern!r} found, but every occurrence is "
            f"in a negated or weakened context",
        )
    return True, ""


@dataclass
class Check:
    """One content-presence check inside the v3.7+ PATTERN PROTECTION block."""

    code: str
    description: str
    must_contain_regex: List[str] = field(default_factory=list)
    # If True, the negation filter will NOT reject matches inside lines
    # containing a GENERAL negation pattern (e.g., "DO NOT", "must not").
    # Use this for checks that *themselves assert* a DO NOT-style prohibition.
    allow_prohibition: bool = False

    def run(self, block_text: str) -> list[str]:
        """Return a list of failure messages (empty = pass)."""
        failures: list[str] = []
        for pattern in self.must_contain_regex:
            passed, detail = _run_pattern(
                pattern, block_text, allow_prohibition=self.allow_prohibition
            )
            if not passed:
                failures.append(
                    f"[{self.code}] {detail} ({self.description})"
                )
        return failures


def _is_negated(
    text: str,
    match: re.Match,
    allow_prohibition: bool = False,
) -> bool:
    """True if the match sits inside a line (of the ORIGINAL text) that
    contains a negation pattern. Match positions are interpreted in the
    normalized-text space, so we project them back to the original text by
    finding the original substring (case-insensitive) that the match
    covers.

    If `allow_prohibition=True`, the GENERAL_NEGATION_PATTERNS (which
    include "DO NOT", "does not", "must not", etc.) are NOT applied. This
    is used for checks that *themselves assert* a DO NOT-style prohibition
    — applying the negation filter there would be self-referential and
    would reject every match. (Inherited from
    check_v3_6_7_pattern_protection.py's `allow_prohibition` flag.)
    """
    matched_text = match.group(0)
    # Find the first occurrence of matched_text in the original text.
    # The match is on the normalized form, so the substring should be
    # contiguous whitespace; locate it case-insensitively.
    original_pos = text.lower().find(matched_text.lower())
    if original_pos == -1:
        # Match not found in original (shouldn't happen since _normalize
        # is whitespace-preserving on word chars). Default to non-negated.
        return False
    # Find the line containing the original position.
    line_start = text.rfind("\n", 0, original_pos) + 1
    line_end = text.find("\n", original_pos)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    patterns = ALWAYS_NEGATION_PATTERNS[:]
    if not allow_prohibition:
        patterns = GENERAL_NEGATION_PATTERNS + patterns
    for pat in patterns:
        if re.search(pat, line, re.IGNORECASE):
            return True
    return False


def _extract_block(text: str, marker: str) -> str:
    """Return the substring of `text` starting at the line containing
    `marker` and ending at the next H1/H2/H3 heading AFTER the marker
    (or EOF)."""
    idx = text.find(marker)
    if idx == -1:
        return ""
    # Find the start of the line containing the marker.
    line_start = text.rfind("\n", 0, idx) + 1
    # Skip past the marker's own line so the heading search does not match
    # the marker itself.
    after_marker_line = text.find("\n", line_start)
    if after_marker_line == -1:
        return ""
    rest = text[after_marker_line + 1 :]
    m = _HEADING_RE.search(rest)
    if m is None:
        return rest
    return rest[: m.start()]


def _normalize(text: str) -> str:
    """Collapse all whitespace runs (newlines, tabs, multiple spaces) to a
    single space. This makes grep targets robust to line-wrapping in the
    source file. Use ONLY for matching; do not write normalized text back."""
    return re.sub(r"\s+", " ", text)


# --- v3.7+ checks ---------------------------------------------------------

# P1: Insight-stage rejection logging is required. (See PATTERN PROTECTION
# (v3.7+) bullet 1.) Grep targets are line-friendly fragments, not a
# multi-line sequence, so the line-wrap "the rejection" in the agent file
# is captured by either of two complementary greps.
CHECK_P1 = Check(
    code="P1",
    description=(
        "Every rejected Insight-stage candidate must be recorded with its "
        "loveliness score before the elaborated claims are written."
    ),
    must_contain_regex=[
        r"rejected at Evaluation stage",
        r"rejection must be recorded",
        r"loveliness score that triggered",
    ],
)

# P2: All 6 Toulmin components must be present per non-trivial claim.
# (See PATTERN PROTECTION (v3.7+) bullet 2.) The 6 components are checked
# as individual grep targets rather than a single multi-line regex, to
# remain robust against line wraps in the source. The obligation phrase
# is matched case-insensitively (the source has "Missing" with a capital
# M).
CHECK_P2 = Check(
    code="P2",
    description=(
        "Every non-trivial integrative claim must carry all 6 Toulmin "
        "components (Claim, Data, Warrant, Backing, Qualifier, Rebuttal). "
        "Missing Qualifier or Rebuttal is a contract violation."
    ),
    must_contain_regex=[
        r"\bClaim\b",
        r"\bData\b",
        r"\bWarrant\b",
        r"\bBacking\b",
        r"\bQualifier\b",
        r"\bRebuttal\b",
        r"missing Qualifier or Rebuttal is.*contract violation",
    ],
)

# P3: Lipton loveliness score must be present per non-trivial claim.
# (See PATTERN PROTECTION (v3.7+) bullet 3.) Each dimension is a separate
# grep target so case / spacing variations in the source are tolerated.
CHECK_P3 = Check(
    code="P3",
    description=(
        "Every non-trivial integrative claim must carry a recorded Lipton "
        "loveliness score on the 4 dimensions (scope/mechanism/unification/"
        "simplicity), each in {W, M, S}."
    ),
    must_contain_regex=[
        r"Loveliness: \(scope=",
        r"mechanism=Y",
        r"unification=Z",
        r"simplicity=W",
        r"three or four W's is below the threshold",
    ],
)

# P4: The Csikszentmihalyi stages must be visible in the output, not just
# claimed in metadata. (See PATTERN PROTECTION (v3.7+) bullet 4.) This
# check *asserts* a DO NOT-style prohibition, so allow_prohibition=True
# is required to prevent the negation filter from rejecting every match.
CHECK_P4 = Check(
    code="P4",
    description=(
        "The output must contain the trace of the Csikszentmihalyi stages "
        "(candidate list, loveliness scores, rejected candidates), not just "
        "metadata claims of having executed them."
    ),
    must_contain_regex=[
        r"DO NOT simulate the Csikszentmihalyi stages",
        r"trace of the stages",
        r"candidate list, loveliness scores, rejected candidates",
    ],
    allow_prohibition=True,
)

# P5: The agent's body (not just the PATTERN PROTECTION block) must define
# the discipline. This is checked at file scope, not block scope, because
# the discipline definition is meant to be in the main body of the agent
# prompt (the "Creative Process Discipline (v3.7+)" section), not in the
# protection block. (This is the v3.7+ equivalent of v3.6.7's "PATTERN
# PROTECTION block must be present" check.)
CHECK_P5_BODY_CS = Check(
    code="P5-body-Csikszentmihalyi",
    description=(
        "The synthesis_agent.md main body must define the Csikszentmihalyi "
        "5-stage process (Preparation / Incubation / Insight / Evaluation / "
        "Elaboration)."
    ),
    must_contain_regex=[
        r"## Creative Process Discipline \(v3\.7\+\)",
        r"Csikszentmihalyi, 1996",
        r"\*\*Preparation\*\*",
        r"\*\*Incubation\*\*",
        r"\*\*Insight\*\*",
        r"\*\*Evaluation\*\*",
        r"\*\*Elaboration\*\*",
    ],
)

CHECK_P6_BODY_TOULMIN = Check(
    code="P6-body-Toulmin",
    description=(
        "The synthesis_agent.md main body must define the Toulmin 6-component "
        "claim structure (Claim / Data / Warrant / Backing / Qualifier / "
        "Rebuttal)."
    ),
    must_contain_regex=[
        r"Toulmin, 1958",
        r"\*\*Claim\*\*",
        r"\*\*Data\*\*",
        r"\*\*Warrant\*\*",
        r"\*\*Backing\*\*",
        r"\*\*Qualifier\*\*",
        r"\*\*Rebuttal\*\*",
    ],
)

CHECK_P7_BODY_LIPTON = Check(
    code="P7-body-Lipton",
    description=(
        "The synthesis_agent.md main body must define the Lipton 4-dimension "
        "loveliness rubric (scope / mechanism / unification / simplicity)."
    ),
    must_contain_regex=[
        r"Lipton, 2004",
        r"\*\*Scope\*\*",
        r"\*\*Mechanism\*\*",
        r"\*\*Unification\*\*",
        r"\*\*Simplicity\*\*",
    ],
)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Static audit for the v3.7+ Csikszentmihalyi / Toulmin / Lipton "
            "discipline applied to deep-research/agents/synthesis_agent.md."
        )
    )
    parser.add_argument(
        "--agent-path",
        type=Path,
        default=SYNTHESIS_AGENT,
        help=(
            "Path to the synthesis agent file to check. Defaults to the "
            "canonical repo path. Tests use this to point at a temp fixture."
        ),
    )
    args = parser.parse_args(argv)
    agent_path: Path = args.agent_path

    if not agent_path.exists():
        print(f"[FAIL] synthesis_agent.md not found at {agent_path}")
        return 1

    text = agent_path.read_text(encoding="utf-8")

    block = _extract_block(text, "## PATTERN PROTECTION (v3.7+)")
    if not block:
        print(
            "[FAIL] PATTERN PROTECTION (v3.7+) block not found in "
            f"{agent_path}. The v3.7+ discipline is required."
        )
        return 1

    print(f"[INFO] Scoping v3.7+ block-scoped checks to "
          f"{len(block)} chars starting at "
          f"'## PATTERN PROTECTION (v3.7+)'.")

    # Block-scoped checks (P1–P4): only the PATTERN PROTECTION (v3.7+) block.
    failures: list[str] = []
    for check in (CHECK_P1, CHECK_P2, CHECK_P3, CHECK_P4):
        failures.extend(check.run(block))

    # Body-scoped checks (P5–P7): the full file, because the discipline
    # definitions live in the main body of the agent prompt.
    for check in (CHECK_P5_BODY_CS, CHECK_P6_BODY_TOULMIN, CHECK_P7_BODY_LIPTON):
        failures.extend(check.run(text))

    if failures:
        print(f"[FAIL] {len(failures)} v3.7+ check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("[OK] All v3.7+ synthesis-agent pattern checks pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
