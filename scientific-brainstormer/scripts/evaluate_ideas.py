#!/usr/bin/env python3
"""
Trace2Skill Stage 1 & 2: Evaluate scientific brainstorm proposals.

Stage 1: Fast deterministic heuristic checks (structural completeness, forbidden keywords).
Stage 2: Multi-turn ReAct loop critique — the Error Analyst inspects reference
         documents, diagnoses failures, and proposes targeted patches. The Success
         Analyst records winning patterns.

The ReAct loop replaces the single-pass LLM call from v1.0.0 with a multi-turn
agent that can read files, verify its own corrections, and iterate before
committing a patch.
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path

try:
    from litellm import completion
except ImportError:
    print("[Warning] 'litellm' is not installed. LLM-based verification will fall back to mock evaluation.", file=sys.stderr)
    completion = None

# ---------------------------------------------------------------------------
# Shared Markdown validator (same logic as merge_patches.py)
# ---------------------------------------------------------------------------

def validate_markdown_content(content: str) -> tuple:
    """Returns (is_valid: bool, errors: list[str])."""
    errors = []

    backtick_fences = [m for m in re.finditer(r'^```', content, re.MULTILINE)]
    if len(backtick_fences) % 2 != 0:
        errors.append("Unbalanced triple-backtick code fences")

    # Check for nested/unclosed fences
    in_fence = False
    for i, line in enumerate(content.split('\n')):
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_fence:
                # Already inside a fence — this is a closing fence (or a nested one)
                if stripped == '```' or re.match(r'^```\s*$', stripped):
                    in_fence = False  # legitimate closing fence
                else:
                    # ```something while already in fence = nested (invalid)
                    errors.append(f"Nested code fence near line {i + 1}: '{stripped[:40]}'")
            else:
                in_fence = True   # opening fence
    if in_fence:
        errors.append("Unclosed code fence at end of content")

    # Headers need "# " not "#text"
    for m in re.finditer(r'^#{1,6}[^#\s]', content, re.MULTILINE):
        errors.append(f"Malformed header (missing space after #): '{m.group()[:40]}'")

    if not content.strip():
        errors.append("Content is empty or whitespace-only")

    stripped = content.strip()
    if (stripped.startswith('{') and stripped.endswith('}')) or \
       (stripped.startswith('[') and stripped.endswith(']')):
        if not re.search(r'^(#{1,6}\s|\* |\- |\d+\. )', content, re.MULTILINE):
            errors.append("Content appears to be raw JSON/data without markdown structure")

    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# ReAct Error / Success Analyst
# ---------------------------------------------------------------------------

class ReActAnalyst:
    """
    Multi-turn ReAct-loop analyst for scientific proposal evaluation.

    Replaces the single-pass LLM critique with an iterative agent that can:
    - Read reference files (failure_modes.md, SKILL.md, proposal files)
    - Diagnose failures through multiple reasoning turns
    - Self-verify proposed patches before committing them
    - Fall back gracefully after max_turns
    """

    MAX_TURNS = 5
    MODEL = "gpt-4o-mini"

    def __init__(self, skill_dir: Path, role: str = "error_analyst"):
        """
        Args:
            skill_dir: Path to the skill directory (contains SKILL.md, references/, etc.)
            role: "error_analyst" or "success_analyst"
        """
        self.skill_dir = Path(skill_dir)
        self.role = role
        self._file_cache: dict[str, str] = {}

    def _read_file(self, relative_path: str) -> str:
        """Read a file from the skill directory, with caching."""
        if relative_path in self._file_cache:
            return self._file_cache[relative_path]
        filepath = self.skill_dir / relative_path
        if not filepath.exists():
            return f"[FILE NOT FOUND: {relative_path}]"
        content = filepath.read_text(encoding="utf-8")
        self._file_cache[relative_path] = content
        return content

    def _build_system_prompt(self) -> str:
        """Build the system prompt with available tools."""
        role_descriptions = {
            "error_analyst": (
                "You are an Error Analyst (A⁻) in the Trace2Skill framework. "
                "Your job is to diagnose WHY a scientific proposal failed evaluation, "
                "identify the root cause in the brainstorming guidelines, and propose "
                "a targeted, minimal patch to SKILL.md that would prevent this class "
                "of failure in the future."
            ),
            "success_analyst": (
                "You are a Success Analyst (A⁺) in the Trace2Skill framework. "
                "Your job is to identify WHAT made this scientific proposal succeed, "
                "extract the effective search or reasoning pattern, and propose a "
                "minimal addition to SKILL.md that would reinforce this winning "
                "pattern in future brainstorming sessions."
            ),
        }
        return f"""{role_descriptions.get(self.role, role_descriptions['error_analyst'])}

You have access to the following files in the skill directory:
- SKILL.md — the main skill guidelines
- references/failure_modes.md — known scientific pitfalls

You can READ any file by responding with: READ:<relative_path>

WORKFLOW (multi-turn):
1. ANALYZE: Read relevant reference files. Understand the failure/success context.
2. DIAGNOSE: Identify the root cause (not just the symptom).
3. PROPOSE: Draft a patch with keys: file, op, target_section, content.
4. VERIFY: Check your own patch against these criteria:
   - Does it address the ROOT CAUSE, not just the symptom?
   - Is it MINIMAL — the smallest change that fixes the issue?
   - Does it avoid duplicating existing guidelines?
   - Is the markdown content well-formed (balanced code fences, proper headers)?
5. OUTPUT: When satisfied, output ONLY the final JSON patch.

PATCH FORMAT (output as JSON):
{{
  "file": "SKILL.md",
  "op": "insert_after",
  "target_section": "## <exact markdown header to insert after>",
  "content": "<well-formed markdown with the new guideline>",
  "diagnosis": "<brief root-cause analysis>",
  "rigorous": true/false
}}

CRITICAL RULES:
- Do NOT propose patches that duplicate content already in SKILL.md or failure_modes.md.
- Do NOT propose patches longer than 15 lines of markdown.
- Always READ relevant files before diagnosing — do not guess what they contain.
- After proposing, VERIFY your patch meets all criteria before outputting.
- Output ONLY the final JSON — no extra commentary after the JSON."""

    def _call_llm(self, messages: list[dict]) -> str:
        """Call the LLM and return the response text."""
        if not completion:
            return json.dumps({
                "file": "SKILL.md",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### Mock Rule (litellm unavailable)\n- This is a placeholder patch generated without LLM access.",
                "diagnosis": "litellm not available — mock response",
                "rigorous": False,
            })
        try:
            response = completion(
                model=self.MODEL,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            return json.dumps({
                "file": "SKILL.md",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": f"\n### Rule from Failed Evaluation\n- LLM call failed: {e}",
                "diagnosis": f"LLM error: {e}",
                "rigorous": False,
            })

    def evaluate(self, proposal_text: str, proposal_path: str = "") -> dict:
        """
        Run the multi-turn ReAct evaluation loop.

        Returns a dict with keys: passed, critique, suggested_patch, diagnosis, turns_used.
        """
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""PROPOSAL TO EVALUATE:

File: {proposal_path}

{proposal_text}

Begin your ReAct analysis. You may READ files, then DIAGNOSE, PROPOSE, VERIFY, and OUTPUT.
Start by reading SKILL.md and references/failure_modes.md to understand the expected standards."""}
        ]

        final_output = None
        turns_used = 0

        for turn in range(1, self.MAX_TURNS + 1):
            turns_used = turn
            response = self._call_llm(messages)

            # Check for file-read requests
            read_matches = re.findall(r'READ:(\S+)', response)
            if read_matches:
                # Agent wants to read files — fulfill and continue
                for filepath in read_matches:
                    content = self._read_file(filepath)
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"FILE CONTENT ({filepath}):\n\n{content[:3000]}\n\n[End of file preview. Continue your analysis.]"})
                continue

            # Try to extract JSON patch from response
            json_match = re.search(r'\{[^{}]*"file"\s*:\s*"[^"]*"[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    candidate = json.loads(json_match.group())
                    # Self-verification: validate the patch content
                    patch_content = candidate.get("content", "")
                    is_valid, errors = validate_markdown_content(patch_content)
                    if not is_valid:
                        # Patch failed self-verification — feed back to agent
                        messages.append({"role": "assistant", "content": response})
                        messages.append({"role": "user", "content": f"Your patch failed Markdown validation:\n" + "\n".join(f"- {e}" for e in errors) + "\n\nPlease fix the patch and output the corrected JSON."})
                        continue

                    final_output = candidate
                    break
                except json.JSONDecodeError:
                    pass

            # Response didn't contain a valid patch — add to history and continue
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Continue your analysis. If ready, output the final JSON patch. If you need to read more files, use READ:<path>."})

        if final_output is None:
            # Max turns exhausted — use the last response as best-effort
            final_output = {
                "file": "SKILL.md",
                "op": "insert_after",
                "target_section": "## 2. CRITICAL WARNINGS",
                "content": "\n### Rule from Incomplete Analysis\n- ReAct loop did not converge within max turns.",
                "diagnosis": "ReAct loop exhausted — analysis incomplete",
                "rigorous": False,
            }

        return {
            "passed": final_output.get("rigorous", False),
            "critique": final_output.get("diagnosis", ""),
            "suggested_patch": json.dumps(final_output),
            "turns_used": turns_used,
        }


# ---------------------------------------------------------------------------
# IdeaEvaluator (Stage 1: heuristic + Stage 2: ReAct)
# ---------------------------------------------------------------------------

class IdeaEvaluator:
    def __init__(self, failure_modes_path: Path):
        self.failure_modes_path = failure_modes_path
        self.forbidden_keywords = []
        self._load_failure_modes()

    def _load_failure_modes(self):
        """Extracts key phrases from failure_modes.md for rule-based heuristics."""
        if not self.failure_modes_path.exists():
            return

        content = self.failure_modes_path.read_text().lower()
        heuristics = ["sci-fi", "infinite budget", "uninvented", "correlation", "trendy tool"]
        for word in heuristics:
            if word in content:
                self.forbidden_keywords.append(word)

    def evaluate_heuristics(self, proposal_text: str) -> dict:
        """Applies fast, deterministic rule checks to the proposal."""
        failures = []
        proposal_lower = proposal_text.lower()

        # Check for structural completion
        # NOTE: These are prefix checks, not exact matches, to accommodate
        # template variants (e.g., "## 2. Background and Targeted Gap").
        required_header_prefixes = [
            "## 1. Title",
            "## 2. Background",
            "## 3. Methodology",
            "## 4. Expected Limitations"
        ]
        for prefix in required_header_prefixes:
            if not any(line.strip().lower().startswith(prefix.lower()) for line in proposal_text.split('\n')):
                failures.append(f"Missing mandatory section: {prefix}")

        # Check for banned concepts/phrases derived from failure_modes.md
        for kw in self.forbidden_keywords:
            if kw in proposal_lower:
                failures.append(f"Potential violation of failure mode: '{kw}' detected.")

        return {
            "passed": len(failures) == 0,
            "reasons": failures
        }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate scientific brainstorm proposals (Trace2Skill Stage 1 & 2)"
    )
    parser.add_argument(
        "--proposals-dir", type=str, required=True,
        help="Directory containing generated proposal markdown files"
    )
    parser.add_argument(
        "--skill-dir", type=str, default="scientific-brainstormer",
        help="Path to the active skill folder"
    )
    parser.add_argument(
        "--max-turns", type=int, default=5,
        help="Maximum ReAct loop turns per proposal (default: 5)"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o-mini",
        help="LLM model for ReAct analyst (default: gpt-4o-mini)"
    )
    args = parser.parse_args()

    skill_path = Path(args.skill_dir)
    proposals_path = Path(args.proposals_dir)
    failure_modes_file = skill_path / "references" / "failure_modes.md"

    evaluator = IdeaEvaluator(failure_modes_file)
    error_analyst = ReActAnalyst(skill_path, role="error_analyst")
    success_analyst = ReActAnalyst(skill_path, role="success_analyst")
    error_analyst.MAX_TURNS = args.max_turns
    success_analyst.MAX_TURNS = args.max_turns
    error_analyst.MODEL = args.model
    success_analyst.MODEL = args.model

    success_pool = []
    failure_pool = []

    print(f"[*] Starting evaluation of proposals in: {proposals_path}")
    for file_path in sorted(proposals_path.glob("*.md")):
        print(f"\nAnalyzing {file_path.name}...")
        text = file_path.read_text(encoding="utf-8")

        # Stage 1: Heuristic Check
        h_res = evaluator.evaluate_heuristics(text)

        if not h_res["passed"]:
            print(f" -> [FAILED Stage 1] Heuristic issues: {h_res['reasons']}")
            # Run Error Analyst (ReAct) for diagnosis
            react_res = error_analyst.evaluate(text, str(file_path))
            failure_pool.append({
                "file": str(file_path),
                "stage": "heuristic",
                "heuristic_reasons": h_res["reasons"],
                "critique": react_res["critique"],
                "suggested_patch": react_res["suggested_patch"],
                "turns_used": react_res["turns_used"],
            })
            continue

        # Stage 2: ReAct Analyst Evaluation
        print(f" -> [PASSED Stage 1] Running ReAct analysis ({args.max_turns} turns max)...")
        # Run both analysts in parallel-style (sequentially here for simplicity)
        error_result = error_analyst.evaluate(text, str(file_path))
        success_result = success_analyst.evaluate(text, str(file_path))

        # Validate patch markdown before saving (DESIGN-1 fix)
        for result, label in [(error_result, "error"), (success_result, "success")]:
            patch_text = result.get("suggested_patch", "")
            if patch_text:
                try:
                    patch_dict = json.loads(patch_text) if isinstance(patch_text, str) else patch_text
                    patch_content = patch_dict.get("content", "")
                    is_valid, errors = validate_markdown_content(patch_content)
                    if not is_valid:
                        print(f"    [Warning] {label} analyst patch failed markdown validation: {errors}")
                        # Mark patch as invalid but keep the trace
                        result["patch_valid"] = False
                        result["patch_errors"] = errors
                    else:
                        result["patch_valid"] = True
                except (json.JSONDecodeError, TypeError):
                    result["patch_valid"] = False

        result_entry = {
            "file": str(file_path),
            "error_critique": error_result["critique"],
            "error_suggested_patch": error_result["suggested_patch"],
            "error_turns_used": error_result["turns_used"],
            "error_patch_valid": error_result.get("patch_valid", False),
            "success_critique": success_result["critique"],
            "success_suggested_patch": success_result["suggested_patch"],
            "success_turns_used": success_result["turns_used"],
            "success_patch_valid": success_result.get("patch_valid", False),
        }

        if error_result["passed"]:
            print(f" -> [SUCCESS] Passed all validation criteria. (ReAct: {error_result['turns_used']} turns)")
            success_pool.append(result_entry)
        else:
            print(f" -> [FAILURE] Flagged by ReAct analyst after {error_result['turns_used']} turns.")
            print(f"    Diagnosis: {error_result['critique'][:120]}")
            failure_pool.append(result_entry)

    # Save results as Trace Pools
    output_dir = skill_path / "output"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "success_traces.json", "w") as f:
        json.dump(success_pool, f, indent=2)
    with open(output_dir / "failure_traces.json", "w") as f:
        json.dump(failure_pool, f, indent=2)

    print(f"\n[+] Evaluation finished.")
    print(f"    Successes (T⁺): {len(success_pool)}")
    print(f"    Failures  (T⁻): {len(failure_pool)}")


if __name__ == "__main__":
    main()
