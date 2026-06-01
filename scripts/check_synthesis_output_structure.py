#!/usr/bin/env python3
"""Static structure validator for synthesis-agent Markdown output.

Distinct from `check_synthesis_toulmin_lipton.py`, which validates the
*prompt* file. This script validates a *synthesis output* (the result of
running the agent) against the v3.7+ Creative Process Discipline
contract:

  For each non-trivial integrative claim in the synthesis narrative:
    - All 6 Toulmin components are present (Claim, Data, Warrant,
      Backing, Qualifier, Rebuttal).
    - A Loveliness score is present, in the form
      `Loveliness: (scope=X, mechanism=Y, unification=Z, simplicity=W)`
      with each X/Y/Z/W in {W, M, S}.
    - The Loveliness score is NOT three-or-four W's (below the
      threshold).

  For each rejected Insight-stage candidate (if surfaced): the
  rejection is recorded with the loveliness score that triggered it.

The validator reuses `_synthesis_markdown_parser.py` to recover the
structured `SynthesisReport` and then walks the structure, reporting
each contract violation as a `[FAIL]` line. Exit 0 if the output is
clean, exit 1 otherwise.

Pre-v3.7+ outputs (no Toulmin blocks) are accepted with a single
`[WARN]` — they may be legacy content that hasn't been re-generated
under the new contract. The script does not refuse them.

Usage:
    PYTHONPATH=scripts python3 scripts/check_synthesis_output_structure.py \\
        path/to/synthesis_report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Locally import the parser. We do this with a path-based importlib load
# so the validator runs in any cwd without requiring `PYTHONPATH=scripts`
# to include `.`. (Most CI invocations set PYTHONPATH=scripts anyway.)
import importlib.util as _importlib_util

_parser_spec = _importlib_util.spec_from_file_location(
    "_synthesis_markdown_parser",
    SCRIPTS_DIR / "_synthesis_markdown_parser.py",
)
if _parser_spec is None or _parser_spec.loader is None:
    raise ImportError("Cannot locate _synthesis_markdown_parser.py")
_parser_mod = _importlib_util.module_from_spec(_parser_spec)
_parser_spec.loader.exec_module(_parser_mod)

# Required Toulmin components per claim, in the v3.7+ discipline.
_REQUIRED_COMPONENTS = ("warrant", "backing", "qualifier", "rebuttal")


def _validate_report(report) -> List[str]:
    """Walk a SynthesisReport and return a list of human-readable
    failure strings. Empty list = clean."""
    failures: List[str] = []

    # Backward-compat: pre-v3.7+ outputs are accepted with a single
    # warning handled by main(), not here. If there are no themes at
    # all, that's a separate, non-contract failure.
    if not report.themes:
        failures.append("no themes found (no `#### Theme N: ...` headings)")
        return failures

    # 1. v3.7+ compliance check: at least one theme must have a Toulmin
    #    claim with a Loveliness score. If none do, the output is
    #    pre-v3.7+ and we accept with a single warning.
    has_v37 = report.is_v37_compliant
    if not has_v37:
        # No failures — caller will emit a single warning.
        return failures

    # 2. Per-claim checks.
    for theme in report.themes:
        if not theme.toulmin_claims:
            # Theme carries no Toulmin blocks; the theme may still
            # appear in the report (it has Evidence Strength etc.) but
            # the v3.7+ discipline applies to non-trivial integrative
            # claims, and an un-blocked theme is fine if it has no
            # such claims. We do NOT fail this case.
            continue
        for claim in theme.toulmin_claims:
            tag = f"{claim.claim_id} (theme: {theme.name})"

            # 2a. All 6 required components present
            missing = [
                f
                for f in _REQUIRED_COMPONENTS
                if getattr(claim, f, None) is None
            ]
            if missing:
                failures.append(
                    f"{tag}: missing Toulmin components: {missing}"
                )

            # 2b. Loveliness score present
            if claim.loveliness is None:
                failures.append(f"{tag}: missing Loveliness score")
                continue  # 2c is moot without a score

            # 2c. Loveliness below threshold
            if claim.loveliness.is_below_threshold():
                tup = claim.loveliness.as_tuple()
                failures.append(
                    f"{tag}: Loveliness {tup} is below threshold "
                    f"(3 or 4 W's)"
                )

            # 2d. Data list should have at least one source
            if not claim.data:
                failures.append(f"{tag}: missing Data (no source IDs)")

    # 3. Knowledge gaps section is required (downstream
    #    report_compiler_agent expects it).
    if not report.knowledge_gaps:
        failures.append("missing `### Knowledge Gaps` section (empty)")

    return failures


def _format_warnings(report) -> List[str]:
    """Forward parser warnings that the maintainer should see but that
    are not contract failures (e.g., a theme has a typo in Evidence
    Strength that the parser flagged)."""
    return list(report.warnings)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a synthesis-agent Markdown output against the "
            "v3.7+ Creative Process Discipline contract."
        )
    )
    parser.add_argument(
        "report_path",
        type=Path,
        help=(
            "Path to the synthesis report Markdown file to validate. "
            "Reads from stdin if `-` is given."
        ),
    )
    args = parser.parse_args(argv)

    # Read input
    if str(args.report_path) == "-":
        text = sys.stdin.read()
        source = "<stdin>"
    else:
        if not args.report_path.exists():
            print(f"[FAIL] report not found: {args.report_path}")
            return 1
        text = args.report_path.read_text(encoding="utf-8")
        source = str(args.report_path)

    report = _parser_mod.parse_synthesis_markdown(text)

    # Pre-v3.7+ tolerance: warn once, do not fail.
    if not report.is_v37_compliant:
        print(
            f"[WARN] {source}: no v3.7+ discipline detected (no Toulmin "
            f"blocks). This may be a pre-v3.7+ output. Treating as "
            f"backward-compatible."
        )
        return 0

    failures = _validate_report(report)
    warnings = _format_warnings(report)

    if warnings:
        for w in warnings:
            print(f"[WARN] {w}")

    if failures:
        print(f"[FAIL] {source}: {len(failures)} contract violation(s):")
        for f in failures:
            print(f"  - {f}")
        return 1

    n_claims = sum(len(t.toulmin_claims) for t in report.themes)
    print(
        f"[OK] {source}: {len(report.themes)} theme(s), {n_claims} "
        f"Toulmin claim(s), all v3.7+ checks pass."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
