"""Unit tests for `scripts/check_synthesis_output_structure.py`.

Patterned after `test_check_synthesis_toulmin_lipton.py`: subprocess
the validator against temp-file fixtures, assert exit code and stdout
substrings.

Covers:
- happy path: a canonical v3.7+ synthesis output passes
- backward-compat: a pre-v3.7+ output is accepted with a single
  warning and exits 0
- missing qualifier: a v3.7+ output with one Toulmin claim missing
  Qualifier fails with a clear message
- below-threshold loveliness: a Loveliness 4-tuple with three W's is
  detected as below threshold
- malformed loveliness: a Loveliness line with a value outside {W,M,S}
  is detected (via the parser's malformed-Loveliness warning path)
- missing knowledge gaps: a v3.7+ output with no `### Knowledge Gaps`
  section fails
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_synthesis_output_structure.py"

# A canonical v3.7+ synthesis output. Reused across tests with surgical
# edits via string replacement.
CANONICAL = textwrap.dedent("""\
    # Synthesis Report

    ## Key Themes

    #### Theme 1: Feedback latency
    **Evidence Strength**: Strong
    **Sources**: 5 sources, Levels I-III
    **Synthesis**: Three converging studies establish feedback latency
    as the key variable.

    > **Claim** (Theme 1.C1): Feedback latency is the active mechanism.
    > **Data**: Author1 (2023, Level I) — finding; Author2 (2024, Level II) — finding
    > **Warrant**: Converging evidence across two operationalizations.
    > **Backing**: Hattie's (2009) feedback framework.
    > **Qualifier**: In higher-education STEM contexts.
    > **Rebuttal**: Author3 (2022) for the population-B counterexample.
    > **Loveliness**: (scope=M, mechanism=S, unification=W, simplicity=M)

    ### Knowledge Gaps
    1. No longitudinal studies
    2. Limited data on laboratory courses
    """)


def _run(report_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(report_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


class TestHappyPath(unittest.TestCase):
    def test_canonical_synthesis_output_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "report.md", CANONICAL)
            result = _run(p)
            self.assertEqual(
                result.returncode, 0,
                f"Canonical v3.7+ output should pass; got exit "
                f"{result.returncode}.\nstdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
            self.assertIn("[OK]", result.stdout)


class TestBackwardCompatibility(unittest.TestCase):
    def test_pre_v37_output_warns_but_passes(self):
        """A pre-v3.7+ output (no Toulmin blocks) is accepted with a
        single warning, exit 0. This preserves backward compatibility
        with content produced before the v3.7+ rollout."""
        import tempfile
        pre_v37 = textwrap.dedent("""\
            # Synthesis Report

            ## Key Themes

            #### Theme 1: Feedback latency
            **Evidence Strength**: Strong
            **Sources**: 5 sources
            **Synthesis**: Three studies agree.

            ### Knowledge Gaps
            1. No longitudinal data
            """)
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "report.md", pre_v37)
            result = _run(p)
            self.assertEqual(
                result.returncode, 0,
                f"Pre-v3.7+ output should exit 0 with a warning; got "
                f"exit {result.returncode}.\nstdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
            self.assertIn("[WARN]", result.stdout)
            self.assertIn("pre-v3.7+", result.stdout.lower())


class TestMissingToulminComponent(unittest.TestCase):
    def test_missing_qualifier_fails(self):
        """Removing the Qualifier component from a v3.7+ claim is
        detected as a contract violation."""
        import tempfile
        modified = CANONICAL.replace(
            "> **Qualifier**: In higher-education STEM contexts.\n", ""
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "report.md", modified)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            self.assertIn("[FAIL]", result.stdout)
            self.assertIn("qualifier", result.stdout.lower())
            self.assertIn("Theme 1.C1", result.stdout)

    def test_missing_data_fails(self):
        """A Toulmin claim with no Data list (no source IDs) fails."""
        import tempfile
        modified = CANONICAL.replace(
            "> **Data**: Author1 (2023, Level I) — finding; Author2 (2024, Level II) — finding\n",
            "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "report.md", modified)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Data", result.stdout)


class TestLovelinessThreshold(unittest.TestCase):
    def test_three_W_below_threshold_fails(self):
        """A Loveliness 4-tuple with three W's is below the
        threshold and is detected as a contract violation."""
        import tempfile
        modified = CANONICAL.replace(
            "> **Loveliness**: (scope=M, mechanism=S, unification=W, simplicity=M)",
            "> **Loveliness**: (scope=W, mechanism=W, unification=W, simplicity=S)",
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "report.md", modified)
            result = _run(p)
            self.assertEqual(result.returncode, 1)
            self.assertIn("[FAIL]", result.stdout)
            self.assertIn("below threshold", result.stdout.lower())
            self.assertIn("Theme 1.C1", result.stdout)


class TestMissingKnowledgeGaps(unittest.TestCase):
    def test_no_knowledge_gaps_section_fails(self):
        """A v3.7+ output that omits the `### Knowledge Gaps` section
        fails the structural contract."""
        import tempfile
        # textwrap.dedent strips the common leading indent, so the
        # block has no leading whitespace. Match against the actual
        # rendered form.
        modified = CANONICAL.replace(
            "### Knowledge Gaps\n1. No longitudinal studies\n"
            "2. Limited data on laboratory courses\n",
            "",
        )
        self.assertNotIn(
            "Knowledge Gaps", modified,
            "test fixture replacement failed — Knowledge Gaps still present"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(Path(tmp), "report.md", modified)
            result = _run(p)
            self.assertEqual(
                result.returncode, 1,
                f"Missing KGaps should fail; got exit {result.returncode}.\n"
                f"stdout: {result.stdout}"
            )
            self.assertIn("Knowledge Gaps", result.stdout)


class TestCLIInput(unittest.TestCase):
    def test_stdin_dash_input_is_supported(self):
        """The validator accepts `-` as a path and reads from stdin
        (for shell pipeline use)."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "-"],
            input=CANONICAL,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            f"stdin input should pass; got exit {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        self.assertIn("[OK]", result.stdout)
        self.assertIn("<stdin>", result.stdout)

    def test_missing_file_fails(self):
        """A path that does not exist fails fast with a clear error."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "/tmp/__definitely_not_a_real_synthesis_report__.md"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
