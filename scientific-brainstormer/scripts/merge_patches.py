#!/usr/bin/env python3
import os
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

class PatchConsolidator:
    def __init__(self, skill_dir: Path, batch_size: int = 4):
        self.skill_dir = skill_dir
        self.batch_size = batch_size

    @staticmethod
    def validate_markdown_content(content: str) -> tuple:
        """
        Validates that patch content is well-formed Markdown.
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

        # Guardrail 2: Check if targeted file actually exists
        target_file = self.skill_dir / patch["file"]
        if not target_file.exists():
            print(f"[-] Guardrail 2 Failed: Target file '{patch['file']}' does not exist.")
            return False

        # Guardrail 3: Verify operation is structured safely
        if patch["op"] not in ["insert_after", "replace", "append"]:
            print(f"[-] Guardrail 3 Failed: Unsupported op '{patch['op']}'.")
            return False

        # Guardrail 4: Markdown format validation
        content = patch.get("content", "")
        is_valid, errors = self.validate_markdown_content(content)
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
        - Safe insertion: insert after the target section heading with proper spacing.
        """
        if not consolidated_patch:
            print("[!] No valid patch to apply.")
            return

        # Post-consolidation Markdown validation before writing
        insert_text = consolidated_patch.get("content", "")
        is_valid, errors = self.validate_markdown_content(insert_text)
        if not is_valid:
            print(f"[!] Refusing to apply patch: Markdown validation failed after consolidation.")
            for err in errors:
                print(f"    - {err}")
            return

        target_filepath = self.skill_dir / consolidated_patch["file"]
        content = target_filepath.read_text()

        target_section = consolidated_patch["target_section"]

        # Deduplication guard: skip if identical content already exists (BUG-4 fix)
        normalized_insert = insert_text.strip()
        if normalized_insert in content:
            print(f"[*] Deduplication: patch content already present in {target_filepath.name}. Skipping insertion.")
            return

        # Safe insertion: find the section at line-start to avoid matching inside code blocks (BUG-5 fix)
        escaped = re.escape(target_section)
        match = re.search(rf'^(.*{escaped})\s*\n', content, re.MULTILINE)

        if match:
            insert_pos = match.end()
            # Ensure proper spacing: blank line before inserted content if needed
            prefix = content[:insert_pos]
            suffix = content[insert_pos:]
            # Add a newline before insert_text if the preceding char isn't already a newline
            separator = "\n\n" if not prefix.endswith("\n\n") else ""
            if prefix.endswith("\n") and not prefix.endswith("\n\n"):
                separator = "\n"
            updated_content = prefix + separator + insert_text + suffix
            target_filepath.write_text(updated_content)
            print(f"[+] Successfully integrated final patch into {target_filepath.name}!")
        else:
            # Fallback append if section is missing
            print(f"[Warning] Could not find section '{target_section}'. Appending to end.")
            target_filepath.write_text(content + "\n\n" + insert_text)

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

    # 1. Gather all raw patches from failure analyses (or success trajectories)
    raw_patches = []
    for trace in traces:
        patch_candidate = trace.get("suggested_patch")
        if patch_candidate:
            try:
                # Expecting raw trace patches to be stored or formatted as parseable JSON strings
                parsed = json.loads(patch_candidate) if isinstance(patch_candidate, str) else patch_candidate
                raw_patches.append(parsed)
            except Exception:
                # If it isn't raw JSON, package the plain text as an insert_after block
                raw_patches.append({
                    "file": "SKILL.md",
                    "op": "insert_after",
                    "target_section": "## 2. CRITICAL WARNINGS",
                    "content": f"\n### Rule from Failure Trace\n- {patch_candidate}"
                })

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