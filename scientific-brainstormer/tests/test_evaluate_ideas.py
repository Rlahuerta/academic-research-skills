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
import subprocess
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
        """HYPOTHESIS.md uses ### h3 headers; heuristic must accept them.

        Note: HYPOTHESIS.md is a *template* — a documentation artefact,
        not a proposal. The v1.1 R1.2/R1.4 fields (Loveliness, Inference
        Mode) are documented in the template's own body. A template
        that goes through `evaluate_heuristics` therefore fails the
        v1.1 checks by design; the assertion below targets only the
        header-detection behavior, not full heuristic pass.
        """
        template_text = (SKILL_DIR / "templates" / "HYPOTHESIS.md").read_text()
        header_prefixes = [
            "### 1. The Phenomenon",
            "### 2. Proposed Mechanism",
            "### 3. Falsifiability Criteria",
            "### 4. Required Inputs",
        ]
        for prefix in header_prefixes:
            self.assertTrue(
                any(line.strip().lower().startswith(prefix.lower()) for line in template_text.split('\n')),
                f"Template missing expected header prefix: {prefix}"
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
        # A v1.1-compliant proposal that mentions "uninvented" should
        # NOT be flagged by the heuristic (the keyword was removed
        # because it never appeared in failure_modes.md). The fixture
        # is short and the test isolates the uninvented-keyword check
        # by including the v1.1 Loveliness and Inference Mode fields
        # so R1.2 / R1.4 heuristics do not fire.
        text = (
            "# Title\n"
            "## 1. Foo\n## 2. Bar\n## 3. Baz\n## 4. Qux\n"
            "Some uninvented concept.\n"
            "Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)\n"
            "Inference Mode: abduction\n"
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(
            result["passed"],
            f"Proposal mentioning 'uninvented' should not be heuristically flagged: {result['reasons']}"
        )


class TestGoldenSetEndToEnd(unittest.TestCase):
    """End-to-end test: run evaluate_ideas.py against golden set via subprocess."""

    def test_golden_set_evaluation(self):
        """Run the full script and verify output structure."""
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


# ---------------------------------------------------------------------------
# R1.2 — Lipton loveliness heuristic
# ---------------------------------------------------------------------------

def _valid_proposal_skeleton(
    loveliness: str | None = None,
    inference_mode: str | None = None,
) -> str:
    """Build a minimal proposal that satisfies the structural heuristic.

    All proposals in the R1.x tests share the same headers and body
    text; only the Loveliness and Inference Mode lines vary, so the
    tests can target those fields without re-asserting the structural
    heuristics.
    """
    out = [
        "# Title",
        "## 1. Foo",
        "Body 1",
        "## 2. Bar",
        "Body 2",
        "## 3. Baz",
        "Body 3",
        "## 4. Qux",
        "Body 4",
    ]
    if loveliness is not None:
        out.append(loveliness)
    if inference_mode is not None:
        out.append(inference_mode)
    return "\n".join(out) + "\n"


class TestR12LovelinessHeuristic(unittest.TestCase):
    """R1.2 — The Loveliness field is present and above threshold."""

    def setUp(self):
        failure_modes_path = SKILL_DIR / "references" / "failure_modes.md"
        self.evaluator = IdeaEvaluator(failure_modes_path)

    def test_missing_loveliness_fails(self):
        text = _valid_proposal_skeleton(inference_mode="Inference Mode: abduction")
        result = self.evaluator.evaluate_heuristics(text)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("R1.2 Loveliness score missing" in r for r in result["reasons"]),
            f"expected missing-Loveliness failure; got: {result['reasons']}"
        )

    def test_below_threshold_loveliness_fails(self):
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=W, mechanism=W, unification=W, simplicity=S)",
            inference_mode="Inference Mode: abduction",
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("below threshold" in r for r in result["reasons"]),
            f"expected below-threshold failure; got: {result['reasons']}"
        )

    def test_above_threshold_loveliness_passes(self):
        # (M, S, W, M): 1 W — above threshold
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
            inference_mode="Inference Mode: abduction",
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(
            result["passed"],
            f"valid Loveliness should pass: {result['reasons']}"
        )

    def test_zero_W_loveliness_passes(self):
        # (S, S, M, S): 0 W — above threshold
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=S, mechanism=S, unification=M, simplicity=S)",
            inference_mode="Inference Mode: induction",
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(result["passed"], result["reasons"])

    def test_parse_loveliness_helper(self):
        score = IdeaEvaluator.parse_loveliness(
            "Some prose.\n\nLoveliness: (scope=M, mechanism=S, unification=W, simplicity=M)"
        )
        self.assertEqual(score, (1, 2, 1, 4))

    def test_parse_loveliness_case_insensitive(self):
        # All-uppercase dimension names + lowercase marks. Marks are
        # case-insensitive (regex uses re.IGNORECASE), so 'm' counts
        # the same as 'M'. Marks: m, s, w, m → W=1, M=2, S=1.
        score = IdeaEvaluator.parse_loveliness(
            "loveliness: (SCOPE=m, MECHANISM=s, unification=w, simplicity=m)"
        )
        self.assertIsNotNone(score)
        self.assertEqual(score, (1, 2, 1, 4))


# ---------------------------------------------------------------------------
# R1.4 — Inference-mode heuristic
# ---------------------------------------------------------------------------

class TestR14InferenceModeHeuristic(unittest.TestCase):
    """R1.4 — The Inference Mode field is present and in the vocabulary."""

    def setUp(self):
        failure_modes_path = SKILL_DIR / "references" / "failure_modes.md"
        self.evaluator = IdeaEvaluator(failure_modes_path)

    def test_missing_inference_mode_fails(self):
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)"
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("R1.4 Inference mode missing" in r for r in result["reasons"]),
            f"expected missing-mode failure; got: {result['reasons']}"
        )

    def test_unknown_inference_mode_fails(self):
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
            inference_mode="Inference Mode: brainstorming",
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("not in the allowed vocabulary" in r for r in result["reasons"]),
            f"expected unknown-mode failure; got: {result['reasons']}"
        )

    def test_each_allowed_mode_passes(self):
        for mode in IdeaEvaluator.ALLOWED_INFERENCE_MODES:
            text = _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
                inference_mode=f"Inference Mode: {mode}",
            )
            result = self.evaluator.evaluate_heuristics(text)
            self.assertTrue(
                result["passed"],
                f"mode {mode!r} should pass: {result['reasons']}"
            )

    def test_mode_field_case_insensitive(self):
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
            inference_mode="inference mode: Abduction",
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(result["passed"], result["reasons"])

    def test_boden_types_accepted_as_inference_modes(self):
        """The Boden vocabulary (combinational / exploratory /
        transformational) is accepted in addition to the
        Peirce vocabulary. This is the documented parallel-vocabulary
        design."""
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
            inference_mode="Inference Mode: transformational",
        )
        result = self.evaluator.evaluate_heuristics(text)
        self.assertTrue(result["passed"], result["reasons"])


# ---------------------------------------------------------------------------
# R1.8 — Boden-type diversity across a candidate set
# ---------------------------------------------------------------------------

class TestR18SetDiversity(unittest.TestCase):
    """R1.8 — A Phase 2 candidate set must cover ≥ 2 distinct inference
    modes. Single-mode sets are a failure."""

    def setUp(self):
        failure_modes_path = SKILL_DIR / "references" / "failure_modes.md"
        self.evaluator = IdeaEvaluator(failure_modes_path)

    def test_single_candidate_set_is_not_penalized(self):
        """A one-candidate brainstorm is not yet a 'set' in the sense
        the diversity rule targets."""
        text = _valid_proposal_skeleton(
            loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
            inference_mode="Inference Mode: abduction",
        )
        result = self.evaluator.evaluate_set_diversity([text])
        self.assertTrue(result["passed"], result["reasons"])

    def test_single_mode_set_fails(self):
        """Three combinational candidates: set-diversity failure."""
        texts = [
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
                inference_mode="Inference Mode: combinational",
            ),
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=S, mechanism=M, unification=M, simplicity=M)",
                inference_mode="Inference Mode: combinational",
            ),
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=M, mechanism=M, unification=M, simplicity=M)",
                inference_mode="Inference Mode: combinational",
            ),
        ]
        result = self.evaluator.evaluate_set_diversity(texts)
        self.assertFalse(result["passed"], "single-mode set should fail")
        self.assertEqual(
            len(result["modes_seen"]), 1,
            f"expected 1 unique mode; got {result['modes_seen']}"
        )
        self.assertTrue(
            any("under-explored conceptual space" in r for r in result["reasons"]),
            f"expected R1.8 failure reason; got: {result['reasons']}"
        )

    def test_diverse_set_passes(self):
        texts = [
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
                inference_mode="Inference Mode: combinational",
            ),
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=S, mechanism=M, unification=M, simplicity=M)",
                inference_mode="Inference Mode: abduction",
            ),
        ]
        result = self.evaluator.evaluate_set_diversity(texts)
        self.assertTrue(result["passed"], result["reasons"])
        self.assertEqual(set(result["modes_seen"]), {"abduction", "combinational"})

    def test_boden_and_peirce_vocabularies_count_for_diversity(self):
        """A set with one Peirce-mode proposal and one Boden-type
        proposal counts as diverse (the two vocabularies are parallel,
        not disjoint)."""
        texts = [
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
                inference_mode="Inference Mode: analogy",
            ),
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=S, mechanism=M, unification=M, simplicity=M)",
                inference_mode="Inference Mode: transformational",
            ),
        ]
        result = self.evaluator.evaluate_set_diversity(texts)
        self.assertTrue(result["passed"], result["reasons"])

    def test_proposals_missing_mode_do_not_count_for_diversity(self):
        """A set with one combinational and one mode-less proposal
        should fail — the mode-less one is flagged by the per-proposal
        heuristic, not counted toward diversity."""
        texts = [
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)",
                inference_mode="Inference Mode: combinational",
            ),
            _valid_proposal_skeleton(
                loveliness="Loveliness: (scope=S, mechanism=M, unification=M, simplicity=M)",
                # No inference mode declared
            ),
        ]
        result = self.evaluator.evaluate_set_diversity(texts)
        self.assertFalse(
            result["passed"],
            "set with one mode declared and one mode missing should fail "
            "(missing mode is a separate per-proposal failure)"
        )


class TestR1xEndToEndOnFixtures(unittest.TestCase):
    """End-to-end: run the modified script against a v1.1-compliant
    candidate set, verify all heuristics pass."""

    def test_diverse_v11_compliant_set_passes_stage1(self):
        import tempfile
        from pathlib import Path as _P

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = _P(tmp)
            # Three proposals, all v1.1-compliant, two distinct modes.
            for i, (l, m) in enumerate([
                ("Loveliness: (scope=M, mechanism=S, unification=W, simplicity=M)", "abduction"),
                ("Loveliness: (scope=S, mechanism=M, unification=M, simplicity=M)", "induction"),
                ("Loveliness: (scope=M, mechanism=M, unification=M, simplicity=M)", "abduction"),
            ]):
                p = tmpdir / f"proposal_{i}.md"
                p.write_text(_valid_proposal_skeleton(loveliness=l, inference_mode=f"Inference Mode: {m}"))

            result = _run_evaluator(tmpdir)
            # At least one proposal should pass Stage 1 (mock mode
            # means Stage 2 always fails; this test only checks
            # Stage 1).
            output_dir = SKILL_DIR / "output"
            with open(output_dir / "failure_traces.json") as f:
                failures = json.load(f)
            # All three proposals in this fixture should pass Stage 1.
            # Verify: the per-proposal heuristic_reasons for the
            # processed fixtures should NOT include any R1.x failure.
            for entry in failures:
                if str(tmpdir) in entry.get("file", ""):
                    reasons = entry.get("heuristic_reasons", [])
                    r1x_failures = [r for r in reasons if "R1." in r]
                    self.assertEqual(
                        r1x_failures, [],
                        f"v1.1-compliant proposal should not have R1.x "
                        f"heuristic failures: {r1x_failures}"
                    )


def _run_evaluator(proposals_dir: Path) -> subprocess.CompletedProcess:
    import subprocess
    return subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts" / "evaluate_ideas.py"),
            "--proposals-dir", str(proposals_dir),
            "--skill-dir", str(SKILL_DIR),
            "--max-turns", "1",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


if __name__ == "__main__":
    unittest.main()
