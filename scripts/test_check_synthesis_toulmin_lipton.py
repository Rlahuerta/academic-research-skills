"""Unit tests for check_synthesis_toulmin_lipton.py.

Patterned after test_check_data_access_level.py: subprocess the linter
against temp-file fixtures, assert exit code and stdout substrings.

Covers:
- happy path: a fully-formed synthesis_agent.md passes
- missing v3.7+ block: linter exits 1 and reports the block is missing
- regressed Toulmin component: removing "Backing" from the v3.7+ block
  is detected
- regressed body section: removing the "Creative Process Discipline"
  body section is detected
- negation-falsifiability: a v3.7+ block that uses "DO NOT reject" /
  "must NOT" etc. to deny every required phrase is detected
- block-scoping: keywords in the body but NOT in the v3.7+ block are
  correctly scoped to body-only checks (P5–P7) and do not satisfy the
  block-scoped checks (P1–P4)
- _run_pattern helper: handles case-insensitive matching, multi-line
  normalization, and the allow_prohibition flag
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_synthesis_toulmin_lipton.py"
SYNTHESIS_AGENT = REPO_ROOT / "deep-research" / "agents" / "synthesis_agent.md"

# A minimal-but-valid synthesis_agent.md fixture. Mirrors the canonical
# structure closely enough to pass the v3.7+ check. The body sections
# (Csikszentmihalyi / Toulmin / Lipton) are present in the form the
# check greps for.
VALID_FIXTURE = textwrap.dedent("""\
    # Synthesis Agent

    ## Creative Process Discipline (v3.7+)

    ### Csikszentmihalyi's 5-stage creative process (Csikszentmihalyi, 1996)

    1. **Preparation**
    2. **Incubation**
    3. **Insight**
    4. **Evaluation**
    5. **Elaboration**

    ### Toulmin's 6-component claim structure (Toulmin, 1958)

    - **Claim**
    - **Data**
    - **Warrant**
    - **Backing**
    - **Qualifier**
    - **Rebuttal**

    ### Lipton's loveliness rubric (Lipton, 2004)

    - **Scope**
    - **Mechanism**
    - **Unification**
    - **Simplicity**

    ## PATTERN PROTECTION (v3.7+)

    - For every Insight-stage candidate that is rejected at Evaluation stage:
      the rejection must be recorded, with the loveliness score that triggered
      the rejection, before the elaborated claims are written. Skipping
      Evaluation-stage rejection logging is a contract violation.
    - For every non-trivial integrative claim emitted in the synthesis
      narrative: all 6 Toulmin components (Claim, Data, Warrant, Backing,
      Qualifier, Rebuttal) must be present. A claim missing Qualifier or
      Rebuttal is an overclaim and a contract violation. Recording a claim
      with a missing Qualifier or Rebuttal is itself a contract violation,
      independent of whether the missing component changes the substantive
      claim.
    - For every non-trivial integrative claim: a Lipton loveliness score of
      the form `Loveliness: (scope=X, mechanism=Y, unification=Z, simplicity=W)`
      with each X/Y/Z/W in {W, M, S} must be present. A claim with three or
      four W's is below the threshold and is not eligible for the narrative.
      Recording a loveliness score with three or four W's is itself a
      contract violation.
    - DO NOT simulate the Csikszentmihalyi stages by claiming them in the
      output metadata without actually executing them. The output must contain
      the trace of the stages (candidate list, loveliness scores, rejected
      candidates) as well as the final narrative.

    ## Two-Layer Citation Emission (v3.7.1)
    """)


def _run(agent_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--agent-path", str(agent_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


class TestHappyPath(unittest.TestCase):
    def test_canonical_synthesis_agent_passes(self):
        """The real synthesis_agent.md should pass the v3.7+ check."""
        if not SYNTHESIS_AGENT.exists():
            self.skipTest(f"canonical agent file not found: {SYNTHESIS_AGENT}")
        result = _run(SYNTHESIS_AGENT)
        self.assertEqual(
            result.returncode, 0,
            f"Canonical synthesis_agent.md should pass the v3.7+ check, "
            f"but got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        self.assertIn("All v3.7+", result.stdout)

    def test_minimal_valid_fixture_passes(self):
        """A minimal-but-valid synthesis_agent.md (with all required sections)
        should pass the check. This is the 'round-trip' test: a fresh
        file produced by the same template should pass."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "synthesis_agent.md", VALID_FIXTURE)
            result = _run(p)
            self.assertEqual(
                result.returncode, 0,
                f"Minimal valid fixture should pass, got exit "
                f"{result.returncode}.\nstdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )


class TestBlockPresence(unittest.TestCase):
    def test_missing_v37_block_fails(self):
        """A file with no PATTERN PROTECTION (v3.7+) block at all fails."""
        import tempfile
        content = textwrap.dedent("""\
            # Synthesis Agent

            ## Creative Process Discipline (v3.7+)

            ### Csikszentmihalyi (Csikszentmihalyi, 1996)
            1. **Preparation**
            2. **Incubation**
            3. **Insight**
            4. **Evaluation**
            5. **Elaboration**

            ### Toulmin (Toulmin, 1958)
            - **Claim**
            - **Data**
            - **Warrant**
            - **Backing**
            - **Qualifier**
            - **Rebuttal**

            ### Lipton (Lipton, 2004)
            - **Scope**
            - **Mechanism**
            - **Unification**
            - **Simplicity**

            ## Two-Layer Citation Emission (v3.7.1)
            """)
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "synthesis_agent.md", content)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            self.assertIn("PATTERN PROTECTION (v3.7+)", result.stdout)
            self.assertIn("not found", result.stdout)


class TestToulminRegression(unittest.TestCase):
    def test_missing_backing_in_v37_block_fails(self):
        """Removing 'Backing' from the v3.7+ block is detected by P2."""
        import tempfile
        import re
        # Start from the valid fixture and remove Backing ONLY from the
        # v3.7+ block (not from the body section, which would also satisfy
        # the body-scoped P6 check).
        m = re.search(
            r"(## PATTERN PROTECTION \(v3\.7\+\).*?)(?=## Two-Layer)",
            VALID_FIXTURE,
            flags=re.DOTALL,
        )
        v37_block = m.group(1)
        regressed = v37_block.replace("Backing,", "").replace("Backing", "")
        content = VALID_FIXTURE.replace(v37_block, regressed, 1)
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "synthesis_agent.md", content)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            self.assertIn("[P2]", result.stdout)
            self.assertIn("Backing", result.stdout)


class TestBodySectionRegression(unittest.TestCase):
    def test_missing_creative_process_discipline_fails(self):
        """Removing the 'Creative Process Discipline (v3.7+)' body section
        is detected by P5/P6/P7 (body-scoped checks)."""
        import tempfile
        # Remove the body section entirely.
        content = re.sub(
            r"## Creative Process Discipline \(v3\.7\+\).*?(?=## PATTERN PROTECTION)",
            "",
            VALID_FIXTURE,
            flags=re.DOTALL,
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "synthesis_agent.md", content)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            # All three body-scoped checks should fire.
            self.assertIn("[P5-body-Csikszentmihalyi]", result.stdout)
            self.assertIn("[P6-body-Toulmin]", result.stdout)
            self.assertIn("[P7-body-Lipton]", result.stdout)


class TestNegationFalsifiability(unittest.TestCase):
    def test_negated_v37_block_fails(self):
        """A v3.7+ block that uses 'DO NOT' / 'must NOT' / 'rarely' to deny
        every required phrase is detected (negation filter works)."""
        import tempfile
        negated = textwrap.dedent("""\
            # Synthesis Agent

            ## Creative Process Discipline (v3.7+)

            ### Csikszentmihalyi (Csikszentmihalyi, 1996)
            1. **Preparation**
            2. **Incubation**
            3. **Insight**
            4. **Evaluation**
            5. **Elaboration**

            ### Toulmin (Toulmin, 1958)
            - **Claim**
            - **Data**
            - **Warrant**
            - **Backing**
            - **Qualifier**
            - **Rebuttal**

            ### Lipton (Lipton, 2004)
            - **Scope**
            - **Mechanism**
            - **Unification**
            - **Simplicity**

            ## PATTERN PROTECTION (v3.7+)

            These rules are aspirational.

            - DO NOT reject the candidate at Evaluation stage; rejection
              must NOT be recorded, and there is no loveliness score that
              triggered the rejection. We rarely log rejections.
            - A non-trivial claim does NOT contain all 6 Toulmin components;
              it may omit Claim or Data or Warrant or Backing or Qualifier
              or Rebuttal. Missing Qualifier or Rebuttal is NOT a contract
              violation.
            - A Lipton loveliness score should NOT be recorded; the form
              `Loveliness: (scope=M, mechanism=Y, unification=Z, simplicity=W)`
              is sometimes used. A claim with three or four W's is rarely
              below the threshold.
            - DO NOT simulate the Csikszentmihalyi stages by claiming them in
              the output metadata without actually executing them. The output
              must contain the trace of the stages (candidate list, loveliness
              scores, rejected candidates) as well as the final narrative.

            ## Two-Layer Citation Emission (v3.7.1)
            """)
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "synthesis_agent.md", negated)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            # The negation filter should reject the P1–P3 patterns
            # that are claimed in a "must NOT" / "does NOT" sentence.
            # (P4 has allow_prohibition=True, so its "DO NOT simulate"
            # match is allowed and the second/third patterns should
            # still satisfy the check.)
            self.assertIn("negated", result.stdout)


class TestBlockScoping(unittest.TestCase):
    def test_body_keywords_do_not_satisfy_block_checks(self):
        """The 6 Toulmin keywords in the body section alone do NOT satisfy
        the block-scoped P2 check. Block scoping is correct."""
        import tempfile
        # Remove the v3.7+ block but keep the body sections.
        content = re.sub(
            r"## PATTERN PROTECTION \(v3\.7\+\).*?(?=## Two-Layer)",
            "",
            VALID_FIXTURE,
            flags=re.DOTALL,
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "synthesis_agent.md", content)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            # The failure message should be about the missing v3.7+ block,
            # NOT about a missing P2 pattern. This proves P2 is correctly
            # scoped to the v3.7+ block.
            self.assertIn("PATTERN PROTECTION (v3.7+)", result.stdout)
            self.assertIn("not found", result.stdout)


class TestHelperFunctions(unittest.TestCase):
    """Direct unit tests of the helper functions in
    check_synthesis_toulmin_lipton.py."""

    def _import_check(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "check_synthesis_toulmin_lipton",
            SCRIPT,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_normalize_collapses_whitespace(self):
        mod = self._import_check()
        self.assertEqual(
            mod._normalize("hello\n  world\t\t!"),
            "hello world !",
        )

    def test_run_pattern_finds_line_wrapped_phrase(self):
        mod = self._import_check()
        # Phrase "three or four" is line-wrapped in this input.
        text = "a claim with three or\nfour W's is below the threshold"
        passed, detail = mod._run_pattern(
            "three or four W's is below the threshold", text
        )
        self.assertTrue(passed, f"Expected match; got: {detail}")

    def test_run_pattern_returns_missing_when_absent(self):
        mod = self._import_check()
        passed, detail = mod._run_pattern("not in the text", "hello world")
        self.assertFalse(passed)
        self.assertIn("missing", detail)

    def test_run_pattern_detects_negation(self):
        mod = self._import_check()
        # Pattern: "rejection must be recorded" appears in a line that
        # ALSO contains "must not" — the negation filter must reject.
        # The regex matches the longer phrase on its own first
        # (case-insensitively) then the negation filter disqualifies the
        # match because the line also contains "must not".
        text_neg = (
            "the rejection must be recorded, with the loveliness score "
            "that triggered the rejection; in some cases this must not be "
            "logged"
        )
        # "loveliness score that triggered" is a real check pattern. The
        # line contains "must not" later, so the negation filter should
        # reject it.
        passed, detail = mod._run_pattern(
            "loveliness score that triggered", text_neg
        )
        self.assertFalse(passed)
        self.assertIn("negated", detail)

        # Sanity: same pattern in a non-negated line should pass.
        text_pos = (
            "the rejection must be recorded, with the loveliness score "
            "that triggered the rejection"
        )
        passed_pos, _ = mod._run_pattern(
            "loveliness score that triggered", text_pos
        )
        self.assertTrue(passed_pos, "non-negated text should match")

    def test_run_pattern_allow_prohibition_lets_do_not_through(self):
        mod = self._import_check()
        # "DO NOT simulate the Csikszentmihalyi stages" should be allowed
        # when allow_prohibition=True (the P4 check uses this).
        text = "DO NOT simulate the Csikszentmihalyi stages"
        passed, detail = mod._run_pattern(
            "DO NOT simulate the Csikszentmihalyi stages",
            text,
            allow_prohibition=True,
        )
        self.assertTrue(passed, f"Expected pass; got: {detail}")

    def test_run_pattern_allow_prohibition_still_rejects_rarely(self):
        mod = self._import_check()
        # Even with allow_prohibition=True, ALWAYS_NEGATION_PATTERNS
        # (rarely, sometimes, fails to, etc.) still apply.
        text = "DO rarely something"
        passed, detail = mod._run_pattern("DO rarely something", text, allow_prohibition=True)
        self.assertFalse(passed)
        self.assertIn("negated", detail)


if __name__ == "__main__":
    unittest.main()
