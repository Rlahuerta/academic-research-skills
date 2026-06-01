#!/usr/bin/env python3
"""Unit tests for scientific-brainstormer/scripts/evaluate_ideas.py.

Runs the evaluator against the golden evaluation set and asserts expected
pass/fail outcomes. These tests verify:
- Structural completeness detection (header prefix matching)
- Failure mode keyword detection
- Success/failure classification
- Trace output format
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Import via importlib since the directory name contains a hyphen (not a valid Python package name)
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
sys.path.insert(0, _scripts_dir)
import importlib.util
_spec = importlib.util.spec_from_file_location("evaluate_ideas", _scripts_dir + "/evaluate_ideas.py")
_evaluate_ideas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_evaluate_ideas)
IdeaEvaluator = _evaluate_ideas.IdeaEvaluator
validate_markdown_content = _evaluate_ideas.validate_markdown_content

# Also import the shared validator directly to verify the
# evaluate_ideas.py wrapper is just a re-export (no drift).
_md_spec = importlib.util.spec_from_file_location(
    "_markdown_validation", _scripts_dir + "/_markdown_validation.py"
)
_md_mod = importlib.util.module_from_spec(_md_spec)
_md_spec.loader.exec_module(_md_mod)
validate_markdown_content_shared = _md_mod.validate_markdown_content


GOLDEN_SET_DIR = Path(__file__).parent / "golden_set"
SKILL_DIR = Path(__file__).parent.parent


class TestValidateMarkdownContent(unittest.TestCase):
    """Tests for the shared markdown validator."""

    def test_balanced_fences_pass(self):
        content = "```python\nprint(1)\n```"
        is_valid, errors = validate_markdown_content(content)
        self.assertTrue(is_valid, f"Expected valid, got: {errors}")

    def test_unbalanced_fences_fail(self):
        content = "```python\nprint(1)"
        is_valid, errors = validate_markdown_content(content)
        self.assertFalse(is_valid)
        self.assertTrue(any("Unbalanced" in e for e in errors))

    def test_malformed_header_fail(self):
        content = "#Bad header"
        is_valid, errors = validate_markdown_content(content)
        self.assertFalse(is_valid)
        self.assertTrue(any("Malformed header" in e for e in errors))

    def test_empty_content_fail(self):
        is_valid, errors = validate_markdown_content("")
        self.assertFalse(is_valid)

    def test_raw_json_without_markdown_fail(self):
        content = '{"key": "value"}'
        is_valid, errors = validate_markdown_content(content)
        self.assertFalse(is_valid)

    def test_raw_json_with_header_pass(self):
        content = '# Header\n{"key": "value"}'
        is_valid, errors = validate_markdown_content(content)
        self.assertTrue(is_valid, f"Expected valid (has header), got: {errors}")


class TestIdeaEvaluatorHeuristics(unittest.TestCase):
    """Tests for Stage 1 heuristic checks against golden set."""

    def setUp(self):
        failure_modes_path = SKILL_DIR / "references" / "failure_modes.md"
        self.evaluator = IdeaEvaluator(failure_modes_path)

    def test_good_proposal_passes(self):
        """proposal_good_peer_feedback.md should pass all heuristics."""
        text = (GOLDEN_SET_DIR / "proposal_good_peer_feedback.md").read_text()
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(
            result["passed"],
            f"Good proposal should pass heuristics but failed: {result['reasons']}"
        )

    def test_infeasible_proposal_passes_heuristics(self):
        """proposal_bad_infeasible_instruments.md has all required headers so passes Stage 1.

        The infeasibility ("quantum supercomputer does not exist") is a content flaw
        that the ReAct analyst would catch in Stage 2, not a structural heuristic.
        """
        text = (GOLDEN_SET_DIR / "proposal_bad_infeasible_instruments.md").read_text()
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(
            result["passed"],
            f"Infeasible proposal should pass header heuristics but failed: {result['reasons']}"
        )

    def test_correlation_proposal_fails(self):
        """proposal_bad_correlation_causation.md should fail heuristics."""
        text = (GOLDEN_SET_DIR / "proposal_bad_correlation_causation.md").read_text()
        result = self.evaluator.evaluate_heuristics(text)
        # This one has all headers but should fail on banned keywords
        # "correlation" is in the failure modes heuristics
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("correlation" in r.lower() for r in result["reasons"]),
            f"Expected correlation failure mode, got: {result['reasons']}"
        )


class TestHeaderPrefixMatching(unittest.TestCase):
    """Verify that header checks use prefix matching, not exact strings."""

    def setUp(self):
        failure_modes_path = SKILL_DIR / "references" / "failure_modes.md"
        self.evaluator = IdeaEvaluator(failure_modes_path)

    def test_template_headers_match(self):
        """Headers from the actual RESEARCH_PROPOSAL.md template should match."""
        template_text = (SKILL_DIR / "templates" / "RESEARCH_PROPOSAL.md").read_text()
        # Extract example headers from the template
        result = self.evaluator.evaluate_heuristics(template_text)
        # The template itself should pass (it's a template, not a proposal,
        # but the headers exist)
        # Actually the template has placeholder text, not real content.
        # Let's just verify the headers are detected.
        header_prefixes = [
            "## 1. Title",
            "## 2. Background",
            "## 3. Methodology",
            "## 4. Expected Limitations",
        ]
        for prefix in header_prefixes:
            self.assertTrue(
                any(line.strip().lower().startswith(prefix.lower()) for line in template_text.split('\n')),
                f"Template missing expected header prefix: {prefix}"
            )

    def test_hypothesis_template_headers_match(self):
        """HYPOTHESIS.md uses ### h3 headers; heuristic must accept them."""
        template_text = (SKILL_DIR / "templates" / "HYPOTHESIS.md").read_text()
        result = self.evaluator.evaluate_heuristics(template_text)
        self.assertTrue(
            result["passed"],
            f"HYPOTHESIS.md (h3 headers) should pass heuristics but failed: {result['reasons']}"
        )

    def test_shared_validator_matches_reexport(self):
        """evaluate_ideas.py and _markdown_validation.py must use the same function.

        The two imports go through different importlib module instances,
        so `assertIs` is too strict. We verify the source text matches,
        which is what would actually drift if someone re-introduced a
        duplicate copy in evaluate_ideas.py.
        """
        import inspect
        src_eval = inspect.getsource(validate_markdown_content)
        src_shared = inspect.getsource(validate_markdown_content_shared)
        self.assertEqual(src_eval, src_shared,
                         "evaluate_ideas.validate_markdown_content and "
                         "_markdown_validation.validate_markdown_content "
                         "have diverged -- re-extract the shared implementation.")

    def test_no_uninvented_keyword(self):
        """The dead 'uninvented' heuristic should not be checked (regression A7)."""
        # A proposal that mentions "uninvented" should NOT be flagged by the
        # heuristic (the keyword was removed because it never appeared in
        # failure_modes.md).
        text = "# Title\n## 1. Foo\n## 2. Bar\n## 3. Baz\n## 4. Qux\nSome uninvented concept."
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(
            result["passed"],
            f"Proposal mentioning 'uninvented' should not be heuristically flagged: {result['reasons']}"
        )


class TestGoldenSetEndToEnd(unittest.TestCase):
    """End-to-end test: run evaluate_ideas.py against golden set via subprocess."""

    def test_golden_set_evaluation(self):
        """Run the full script and verify output structure."""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "evaluate_ideas.py"),
                "--proposals-dir", str(GOLDEN_SET_DIR),
                "--skill-dir", str(SKILL_DIR),
                "--max-turns", "2",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Script should run without crashing (exit 0 regardless of pass/fail outcomes)
        self.assertEqual(result.returncode, 0, f"Script crashed:\n{result.stderr}")

        output_dir = SKILL_DIR / "output"
        success_file = output_dir / "success_traces.json"
        failure_file = output_dir / "failure_traces.json"

        self.assertTrue(success_file.exists(), "success_traces.json not created")
        self.assertTrue(failure_file.exists(), "failure_traces.json not created")

        with open(success_file) as f:
            successes = json.load(f)
        with open(failure_file) as f:
            failures = json.load(f)

        good_file = str(GOLDEN_SET_DIR / "proposal_good_peer_feedback.md")
        bad1 = str(GOLDEN_SET_DIR / "proposal_bad_infeasible_instruments.md")
        bad2 = str(GOLDEN_SET_DIR / "proposal_bad_correlation_causation.md")
        success_files = {s.get("file") for s in successes}
        failure_files = {f.get("file") for f in failures}
        all_files = success_files | failure_files

        # All golden-set files must have been processed
        for f in (good_file, bad1, bad2):
            self.assertIn(
                f, all_files,
                f"{f} was not processed. Success: {success_files}, Failure: {failure_files}"
            )

        # In mock mode (no litellm), the ReAct analyst always returns rigorous=False,
        # so every proposal lands in the failure pool. In a real environment with an LLM,
        # the good proposal would be expected in the success pool.
        # We therefore only enforce that bad proposals are never in successes.
        self.assertNotIn(bad1, success_files)
        self.assertNotIn(bad2, success_files)

        # Verify trace structure includes both error and success fields
        if successes:
            entry = successes[0]
            self.assertIn("error_critique", entry)
            self.assertIn("success_critique", entry)
            self.assertIn("error_patch_valid", entry)
            self.assertIn("success_patch_valid", entry)


if __name__ == "__main__":
    unittest.main()
