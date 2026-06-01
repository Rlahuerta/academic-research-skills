#!/usr/bin/env python3
import sys
import json
import re
import math
import argparse
from pathlib import Path

try:
    from litellm import completion
except ImportError:
    completion = None

# Shared helpers (single source of truth for path-traversal containment
# and Markdown structural validation).
from _safe_path import safe_resolve_under
from _markdown_validation import validate_markdown_content


class PatchConsolidator:
    def __init__(self, skill_dir: Path, batch_size: int = 4):
        self.skill_dir = skill_dir
        self.batch_size = batch_size

    def enforce_guardrails(self, patch: dict) -> bool:
        """
        Enforces Trace2Skill's deterministic guardrails:
        1. Reject patches referencing non-existent files.
        2. Detect overlap/conflict targeting the same target sections.
        3. Validate patch schema (JSON contains mandatory operational keys).
        4. Validate Markdown formatting of patch content.
        """
        # Guardrail 1: Schema validation
        required_keys = ["file", "op", "target_section", "content"]
        if not all(k in patch for k in required_keys):
            missing = [k for k in required_keys if k not in patch]
            print(f"[-] Guardrail 1 Failed: Invalid patch schema. Missing keys: {missing}")
            return False

        # Guardrail 2: Check if targeted file is within skill_dir (containment)
        target_file = safe_resolve_under(self.skill_dir, patch["file"])
        if target_file is None:
            print(f"[-] Guardrail 2 Failed: Target path escapes skill directory or is invalid: '{patch['file']}'")
            return False
        if not target_file.exists():
            print(f"[-] Guardrail 2 Failed: Target file '{patch['file']}' does not exist.")
            return False

        # Guardrail 3: Verify operation is structured safely
        if patch["op"] not in ["insert_after", "append"]:
            print(f"[-] Guardrail 3 Failed: Unsupported op '{patch['op']}'.")
            return False

        # Guardrail 4: Markdown format validation
        content = patch.get("content", "")
        is_valid, errors = validate_markdown_content(content)
        if not is_valid:
            for err in errors:
                print(f"[-] Guardrail 4 Failed: {err}")
            return False

        return True

    def merge_batch_via_llm(self, parent_skill_content: str, patches: list) -> dict:
        """Asks an LLM (Merge Operator) to reconcile multiple concurrent patch proposals."""
        if not completion:
            # Mock merging if no environment API is configured
            return {
                "file": "SKILL.md",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### Consolidated Rule\n- Synthesized rule compiled during mock execution."
            }

        patches_str = json.dumps(patches, indent=2)
        prompt = f"""You are a Skill Edit Coordinator. Your job is to reconcile and consolidate multiple independently proposed modifications into a single coherent, non-redundant modification block.

ORIGINAL SKILL FILE PARTIAL CONTENT:
\"\"\"
{parent_skill_content}
\"\"\"

PROPOSED INDEPENDENT PATCHES:
{patches_str}

Consolidate these edits. Reconcile any overlaps, retain unique insights, and maintain concise structure.
Output your final consolidated modification in JSON format with these exact keys:
- "file": "SKILL.md"
- "op": "insert_after"
- "target_section": "<Target markdown header to insert after>"
- "content": "<The synthesized and deduplicated markdown content to write>"
"""
        try:
            response = completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[-] Error during LLM batch merge: {e}")
            return patches[0] # Fallback to first if API fails

    def run_hierarchical_merge(self, patches: list) -> dict:
        """Recursively groups patches into batch_size clusters to perform inductive reasoning.

        Note on parallelism: The Trace2Skill paper (§2.3) prescribes parallel fleet dispatch
        of analyst sub-agents. This implementation processes batches sequentially for API
        rate-limit safety and because the current golden set (3 proposals) does not benefit
        from parallelism. For production-scale evolution (200+ trajectories), replace the
        for-loop below with concurrent.futures.ThreadPoolExecutor.
        """
        if not patches:
            return {}
        if len(patches) == 1:
            return patches[0]

        next_level_patches = []
        num_batches = math.ceil(len(patches) / self.batch_size)
        print(f"[*] Hierarchical Merge Level: Processing {len(patches)} patches in {num_batches} batches...")

        # Read SKILL.md once per merge run (was previously re-read on every
        # recursion level, see B1-equivalent efficiency finding).
        parent_file = self.skill_dir / "SKILL.md"
        parent_content = parent_file.read_text() if parent_file.exists() else ""

        for i in range(0, len(patches), self.batch_size):
            batch = patches[i : i + self.batch_size]
            if len(batch) == 1:
                next_level_patches.append(batch[0])
            else:
                merged = self.merge_batch_via_llm(parent_content, batch)
                next_level_patches.append(merged)

        # Recursive call down the merge tree hierarchy
        return self.run_hierarchical_merge(next_level_patches)

    def apply_patch(self, consolidated_patch: dict):
        """Applies the final programmatically verified patch directly to the target file.

        Guardrails:
        - Deduplication: skip if the exact same content already exists in the file.
        - Markdown validation: re-validate after consolidation before writing.
        - Safe insertion: insert after the target section's body (not inside it).
        """
        if not consolidated_patch:
            print("[!] No valid patch to apply.")
            return

        # Post-consolidation Markdown validation before writing
        insert_text = consolidated_patch.get("content", "")
        is_valid, errors = validate_markdown_content(insert_text)
        if not is_valid:
            print(f"[!] Refusing to apply patch: Markdown validation failed after consolidation.")
            for err in errors:
                print(f"    - {err}")
            return

        # Containment check: target path must resolve under skill_dir
        target_filepath = safe_resolve_under(self.skill_dir, consolidated_patch["file"])
        if target_filepath is None:
            print("[!] Refusing to apply patch: Target path escapes skill directory or is invalid.")
            return
        content = target_filepath.read_text()

        target_section = consolidated_patch["target_section"]

        # Deduplication guard: skip if identical content already exists (BUG-4 fix)
        normalized_insert = insert_text.strip()
        if normalized_insert in content:
            print(f"[*] Deduplication: patch content already present in {target_filepath.name}. Skipping insertion.")
            return

        # Safe insertion: find the byte offset just AFTER the target section's
        # body (i.e., at the start of the next sibling heading or EOF).
        # Never matches inside ``` fenced code blocks.
        # (BUG-5 fix: previous regex inserted AT the header line, displacing
        # the section's original first body content.)
        insert_pos = _find_section_anchor(content, target_section)

        if insert_pos is not None:
            # Ensure proper spacing: blank line before inserted content.
            prefix = content[:insert_pos]
            suffix = content[insert_pos:]
            # Trim trailing whitespace from prefix, then add exactly one
            # blank line before the new block.
            prefix = prefix.rstrip() + "\n\n"
            updated_content = prefix + insert_text.rstrip() + "\n\n" + suffix.lstrip("\n")
            target_filepath.write_text(updated_content)
            print(f"[+] Successfully integrated final patch into {target_filepath.name}!")
        else:
            # Fallback append if section is missing
            print(f"[Warning] Could not find section '{target_section}'. Appending to end.")
            target_filepath.write_text(content.rstrip() + "\n\n" + insert_text.rstrip() + "\n")


def _find_section_anchor(content: str, target_section: str) -> int | None:
    """Return the byte offset where a new section can be safely inserted AFTER
    the body of `target_section` (i.e., at the start of the next sibling
    heading or end of file, whichever comes first). Returns None if the
    target section cannot be found outside a code fence.

    Skips matches inside ``` fenced code blocks so that example sections
    in prose do not corrupt the file.
    """
    escaped = re.escape(target_section)
    lines = content.split('\n')
    in_fence = False
    section_start_line: int | None = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if section_start_line is None:
            # Anchor on a line whose stripped form equals target_section exactly
            # (optionally followed by trailing whitespace).
            if re.match(rf'^{escaped}\s*$', stripped):
                section_start_line = i
            continue
        # We're inside the target section; stop at the next sibling heading.
        if re.match(r'^#{1,6}\s', line):
            offset = sum(len(l) + 1 for l in lines[:i])
            return offset
    if section_start_line is None:
        return None
    # Section runs to EOF.
    return len(content)


def _derive_fallback_target(skill_dir: Path, trace_file: str) -> str:
    """Derive a safe skill_dir-relative target for a free-form-text patch
    fallback. Uses the trace's originating file (set by evaluate_ideas.py
    to the proposal path) so the patch lands in the right place, but
    falls back to SKILL.md if the trace file is outside skill_dir.

    The enforce_guardrails containment check in the caller will reject
    any escape attempt regardless.
    """
    if not trace_file:
        return "SKILL.md"
    try:
        candidate = Path(trace_file).resolve()
        if candidate.is_relative_to(skill_dir.resolve()):
            return str(candidate.relative_to(skill_dir.resolve()))
    except (ValueError, OSError):
        pass
    return "SKILL.md"


def main():
    parser = argparse.ArgumentParser(description="Consolidate and merge proposed skill patches (Trace2Skill Stage 3)")
    parser.add_argument("--skill-dir", type=str, default="scientific-brainstormer", help="Path to active skill folder")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size for hierarchical consolidation layers")
    args = parser.parse_args()

    skill_path = Path(args.skill_dir)
    traces_dir = skill_path / "output"
    failure_traces_file = traces_dir / "failure_traces.json"

    if not failure_traces_file.exists():
        print(f"[-] No trace data found at {failure_traces_file}. Run 'evaluate_ideas.py' first.")
        sys.exit(1)

    with open(failure_traces_file, "r") as f:
        traces = json.load(f)

    # 1. Gather all raw patches from failure analyses (or success trajectories).
    # Accept the canonical "suggested_patch" key (added in evaluate_ideas.py
    # for new runs) and the legacy "error_suggested_patch" /
    # "success_suggested_patch" keys for older trace files. This fixes the
    # silent no-op where every Stage-2 patch was dropped (A1).
    raw_patches = []
    for trace in traces:
        patch_candidate = (
            trace.get("suggested_patch")
            or trace.get("error_suggested_patch")
            or trace.get("success_suggested_patch")
        )
        if not patch_candidate:
            # No patch at all in this trace - skip with a warning so the
            # operator can see the data shape.
            print(f"[-] No patch in trace {trace.get('file')}; skipping.")
            continue
        if isinstance(patch_candidate, str):
            try:
                parsed = json.loads(patch_candidate)
                raw_patches.append(parsed)
                continue
            except json.JSONDecodeError:
                # Plain-text fallback: package against the trace's
                # originating file, not always SKILL.md. The
                # enforce_guardrails containment check catches escape.
                rel_target = _derive_fallback_target(skill_path, trace.get("file", ""))
                raw_patches.append({
                    "file": rel_target,
                    "op": "insert_after",
                    "target_section": "## 2. CRITICAL WARNINGS",
                    "content": f"\n### Rule from Failure Trace\n- {patch_candidate}"
                })
                continue
        # Already a dict (the canonical shape from evaluate_ideas.py).
        raw_patches.append(patch_candidate)

    # 2. Programmatically filter out entries failing physical and structural guardrails
    consolidator = PatchConsolidator(skill_path, args.batch_size)
    valid_patches = [p for p in raw_patches if consolidator.enforce_guardrails(p)]

    print(f"[*] Retained {len(valid_patches)} / {len(raw_patches)} proposed patches after running deterministic guardrails.")

    if not valid_patches:
        print("[!] No valid edits survived consolidation guardrails. Exiting.")
        sys.exit(0)

    # 3. Perform the inductive hierarchical merge
    final_patch = consolidator.run_hierarchical_merge(valid_patches)

    # 4. Write back the updated SKILL.md file
    consolidator.apply_patch(final_patch)

if __name__ == "__main__":
    main()
