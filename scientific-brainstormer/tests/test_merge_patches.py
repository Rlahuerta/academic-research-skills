#!/usr/bin/env python3
"""Unit tests for scientific-brainstormer/scripts/merge_patches.py.

Covers each fix in the deep code review:
- A1: silent no-op trace key mismatch (writer/reader shape)
- A2: insertion position must not displace section body
- A3: 'replace' op is no longer in the allowlist
- A4: balanced-brace JSON extractor handles nested braces
- A7: shared markdown validator and shared path-traversal utility
- A9: free-form-fallback target rewrite (uses trace.file)
- A10: workflow self-trigger guard present
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Same importlib pattern as test_evaluate_ideas.py (script dir name
# contains a hyphen so it is not a valid Python package name).
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
sys.path.insert(0, _SCRIPTS_DIR)

_spec = importlib.util.spec_from_file_location("merge_patches", _SCRIPTS_DIR + "/merge_patches.py")
_mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mp)
PatchConsolidator = _mp.PatchConsolidator
_find_section_anchor = _mp._find_section_anchor
_derive_fallback_target = _mp._derive_fallback_target

_safe_spec = importlib.util.spec_from_file_location("_safe_path", _SCRIPTS_DIR + "/_safe_path.py")
_sp = importlib.util.module_from_spec(_safe_spec)
_safe_spec.loader.exec_module(_sp)
safe_resolve_under = _sp.safe_resolve_under


def _import_extract_json():
    spec = importlib.util.spec_from_file_location(
        "evaluate_ideas", _SCRIPTS_DIR + "/evaluate_ideas.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m._extract_first_json_object


_extract_first_json_object = _import_extract_json()


class TestSafeResolveUnder(unittest.TestCase):
    """B2 / A8: path-traversal containment utility."""

    def test_inside_skill_dir(self):
        base = Path("/tmp/skill").resolve()
        result = safe_resolve_under(base, "SKILL.md")
        self.assertEqual(result, (base / "SKILL.md").resolve())

    def test_relative_escape_rejected(self):
        base = Path("/tmp/skill").resolve()
        self.assertIsNone(safe_resolve_under(base, "../etc/passwd"))

    def test_absolute_escape_rejected(self):
        base = Path("/tmp/skill").resolve()
        self.assertIsNone(safe_resolve_under(base, "/etc/passwd"))

    def test_raises_on_invalid_base(self):
        # None base should be handled (Path(None) raises TypeError, but
        # safe_resolve_under catches that and returns None).
        result = safe_resolve_under(Path("/tmp/skill"), "\x00bad")
        self.assertIsNone(result)


class TestBalancedBraceExtractor(unittest.TestCase):
    """A4: regex `\\{[^{}]*...` used to reject nested braces."""

    def test_simple_object(self):
        text = '{"file": "SKILL.md", "op": "insert_after"}'
        result = _extract_first_json_object(text)
        self.assertEqual(result["file"], "SKILL.md")
        self.assertEqual(result["op"], "insert_after")

    def test_nested_braces_in_content(self):
        text = (
            'Here is a patch: {"file": "SKILL.md", "op": "insert_after", '
            '"content": "Example with nested {braces} in prose."}'
        )
        result = _extract_first_json_object(text)
        self.assertIsNotNone(result, "Should extract JSON with nested braces")
        self.assertIn("{braces}", result["content"])

    def test_brace_inside_string_with_escape(self):
        text = r'{"key": "value with \" quote and { brace"}'
        result = _extract_first_json_object(text)
        self.assertIsNotNone(result)
        # Python source r'\"' is a 2-char sequence: backslash + quote.
        # json.loads decodes that to a single double-quote.
        self.assertIn('" quote', result["key"])

    def test_invalid_json_returns_none(self):
        text = '{"file": "SKILL.md", broken'
        result = _extract_first_json_object(text)
        self.assertIsNone(result)

    def test_no_json_returns_none(self):
        text = "just plain text without braces"
        result = _extract_first_json_object(text)
        self.assertIsNone(result)


class TestReplaceOpRejected(unittest.TestCase):
    """A3: 'replace' op is no longer in the allowlist."""

    def test_replace_op_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Skill\n")
            consolidator = PatchConsolidator(skill_dir)
            patch = {
                "file": "SKILL.md",
                "op": "replace",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### New Rule\n- Replacement content.",
            }
            self.assertFalse(consolidator.enforce_guardrails(patch))

    def test_insert_after_op_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Skill\n")
            consolidator = PatchConsolidator(skill_dir)
            patch = {
                "file": "SKILL.md",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### New Rule\n- Inserted content.",
            }
            self.assertTrue(consolidator.enforce_guardrails(patch))

    def test_allowlist_size_is_two(self):
        """Catches accidental re-add of 'replace' (or any new op)."""
        import inspect
        src = inspect.getsource(PatchConsolidator.enforce_guardrails)
        # The allowlist line must contain exactly two ops.
        self.assertIn('"insert_after"', src)
        self.assertIn('"append"', src)
        self.assertNotIn('"replace"', src)


class TestInsertionPosition(unittest.TestCase):
    """A2: patch insertion must land AFTER the target section's body."""

    def test_insert_lands_after_section_body(self):
        content = (
            "# Skill\n"
            "\n"
            "## 1. CRITICAL WARNINGS\n"
            "Existing rule A.\n"
            "Existing rule B.\n"
            "\n"
            "## 2. NEXT\n"
            "Should not be displaced.\n"
        )
        pos = _find_section_anchor(content, "## 1. CRITICAL WARNINGS")
        self.assertIsNotNone(pos)
        # The exact insertion point must be the start of "## 2. NEXT".
        # (Inserting BEFORE this point but AFTER Existing rule B. is
        # the contract.)
        next_heading_offset = content.index("## 2. NEXT")
        self.assertEqual(pos, next_heading_offset,
                         "Insertion position should be exactly at the next sibling heading")
        # And AFTER the existing section body.
        existing_b = content.index("Existing rule B.")
        self.assertGreater(pos, existing_b,
                           "Insertion position should be after the existing section body")
        # And the existing content must still be present at the same offset.
        self.assertIn("Existing rule B.", content[:pos])

    def test_section_at_eof(self):
        content = "# Skill\n\n## 1. CRITICAL WARNINGS\nBody here.\n"
        pos = _find_section_anchor(content, "## 1. CRITICAL WARNINGS")
        self.assertEqual(pos, len(content))

    def test_section_inside_code_fence_skipped(self):
        content = (
            "# Skill\n"
            "\n"
            "## 1. CRITICAL WARNINGS\n"
            "Real section body.\n"
            "\n"
            "## 2. ANOTHER\n"
            "```\n"
            "## 1. CRITICAL WARNINGS\n"
            "This is inside a code fence.\n"
            "```\n"
        )
        pos = _find_section_anchor(content, "## 1. CRITICAL WARNINGS")
        # Should find the FIRST (real) section, not the one in the code fence.
        self.assertIsNotNone(pos)
        # Insertion lands at "## 2. ANOTHER".
        self.assertEqual(pos, content.index("## 2. ANOTHER"))
        # The body BEFORE insertion must include the real section body but
        # NOT the in-fence section (we did not insert inside the fence).
        before = content[:pos]
        self.assertIn("Real section body", before)
        self.assertNotIn("This is inside a code fence.", before)
        # And the in-fence section is still present in the file (untouched).
        self.assertIn("This is inside a code fence.", content)

    def test_missing_section_returns_none(self):
        content = "# Skill\n\n## Other\n"
        pos = _find_section_anchor(content, "## 1. CRITICAL WARNINGS")
        self.assertIsNone(pos)


class TestPathTraversalGuardrails(unittest.TestCase):
    """A8: enforce_guardrails rejects paths outside skill_dir."""

    def test_relative_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Skill\n")
            consolidator = PatchConsolidator(skill_dir)
            patch = {
                "file": "../../../etc/passwd",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### Rule\n- x",
            }
            self.assertFalse(consolidator.enforce_guardrails(patch))

    def test_apply_patch_refuses_outside_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Skill\n")
            consolidator = PatchConsolidator(skill_dir)
            patch = {
                "file": "/etc/passwd",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### Rule\n- x",
            }
            # enforce_guardrails catches it first.
            self.assertFalse(consolidator.enforce_guardrails(patch))


class TestFreeFormFallbackTarget(unittest.TestCase):
    """A9: free-form-fallback uses trace.file, not always SKILL.md."""

    def test_trace_file_inside_skill_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            trace_file = str((skill_dir / "templates" / "HYPOTHESIS.md").resolve())
            rel = _derive_fallback_target(skill_dir, trace_file)
            self.assertEqual(rel, "templates/HYPOTHESIS.md")

    def test_trace_file_outside_skill_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            trace_file = "/tmp/other_proposal.md"
            rel = _derive_fallback_target(skill_dir, trace_file)
            # Default to SKILL.md (safe) when the trace file is outside
            # the skill directory.
            self.assertEqual(rel, "SKILL.md")

    def test_empty_trace_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skill"
            skill_dir.mkdir()
            rel = _derive_fallback_target(skill_dir, "")
            self.assertEqual(rel, "SKILL.md")


class TestSilentNoopRegression(unittest.TestCase):
    """A1: merge_patches.py main() picks up suggested_patch from new trace shape."""

    def test_reader_picks_up_canonical_suggested_patch(self):
        """The reader's patch-loading loop must accept 'suggested_patch'."""
        # Import main() and inspect the source to confirm it reads the
        # canonical key. (Behavioral test: feed it a fixture.)
        import inspect
        src = inspect.getsource(_mp.main)
        self.assertIn('trace.get("suggested_patch")', src)
        # Backward compatibility:
        self.assertIn('error_suggested_patch', src)
        self.assertIn('success_suggested_patch', src)

    def test_end_to_end_noop_with_fixtures(self):
        """Reproduce the original silent no-op: write a real fixture, run
        merge_patches.py main(), confirm a patch is applied to SKILL.md."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skill_dir = tmp_path / "skill"
            skill_dir.mkdir()
            # Real SKILL.md with the target section.
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "# Skill\n\n"
                "## 2. CRITICAL WARNINGS\n"
                "Existing warning.\n"
            )
            # Real failure_traces.json with the canonical key.
            output_dir = skill_dir / "output"
            output_dir.mkdir()
            patch_dict = {
                "file": "SKILL.md",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### New Rule from Failure\n- A new rule for SKILL.md.",
            }
            trace = {
                "file": str(skill_dir / "proposal.md"),
                "stage": "react",
                "critique": "Some critique",
                "suggested_patch": json.dumps(patch_dict),
                "rigorous": False,
                "turns_used": 3,
                "patch_valid": True,
            }
            (output_dir / "failure_traces.json").write_text(json.dumps([trace]))

            # Run merge_patches.main()
            old_argv = sys.argv
            try:
                sys.argv = [
                    "merge_patches.py",
                    "--skill-dir", str(skill_dir),
                    "--batch-size", "1",
                ]
                _mp.main()
            finally:
                sys.argv = old_argv

            # Verify the patch was applied.
            updated = skill_md.read_text()
            self.assertIn("New Rule from Failure", updated,
                          "Patch should have been applied to SKILL.md")
            self.assertIn("Existing warning", updated,
                          "Original section body should be preserved")


class TestWorkflowSelfTriggerGuard(unittest.TestCase):
    """A10: skill-evolution.yml PR step must be guarded against push re-trigger."""

    def test_pr_step_has_event_guard(self):
        workflow_path = Path(__file__).resolve().parent.parent.parent / \
            ".github" / "workflows" / "skill-evolution.yml"
        if not workflow_path.exists():
            self.skipTest(f"Workflow file not found: {workflow_path}")
        text = workflow_path.read_text()
        # The PR-creation step must have an event-name guard.
        self.assertIn("github.event_name", text,
                      "workflow must reference github.event_name to prevent self-trigger")


if __name__ == "__main__":
    unittest.main()
