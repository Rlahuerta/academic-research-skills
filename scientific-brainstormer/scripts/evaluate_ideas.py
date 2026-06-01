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

# Shared helpers (single source of truth for Markdown structural validation
# and path-traversal containment).
from _markdown_validation import validate_markdown_content
from _safe_path import safe_resolve_under


# ---------------------------------------------------------------------------
# Mock-patch fallback builder
# ---------------------------------------------------------------------------

def _make_fallback_patch(content: str, diagnosis: str) -> str:
    """Build a JSON patch string for the no-LLM-available and LLM-error paths.

    Centralizes the sentinel-patch construction that was previously
    duplicated at three sites in _call_llm / evaluate.
    """
    return json.dumps({
        "file": "SKILL.md",
        "op": "insert_after",
        "target_section": "## 2. CRITICAL WARNINGS",
        "content": content,
        "diagnosis": diagnosis,
        "rigorous": False,
    })


# ---------------------------------------------------------------------------
# Balanced-brace JSON extractor (replaces brace-restrictive regex)
# ---------------------------------------------------------------------------

def _extract_first_json_object(text: str) -> dict | None:
    """Find the first balanced top-level {...} in `text` and return its dict.

    Replaces the previous regex `\\{[^{}]*"file"\\s*:\\s*"[^"]*"[^{}]*\\}`
    which forbade any nested braces (rejecting any patch whose `content`
    field contained a JSON example or curly-brace code block).
    """
    depth = 0
    in_string = False
    escape = False
    start = -1
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if in_string and ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


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
        filepath = safe_resolve_under(self.skill_dir, relative_path)
        if filepath is None:
            return f"[ACCESS DENIED: {relative_path}]"
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
            return _make_fallback_patch(
                "\n### Mock Rule (litellm unavailable)\n- This is a placeholder patch generated without LLM access.",
                "litellm not available — mock response",
            )
        try:
            response = completion(
                model=self.MODEL,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            return _make_fallback_patch(
                f"\n### Rule from Failed Evaluation\n- LLM call failed: {e}",
                f"LLM error: {e}",
            )

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

            # Try to extract a balanced JSON patch from the response.
            # Uses a balanced-brace scanner (replaces the previous
            # regex that forbade nested braces, which silently rejected
            # any patch whose content field contained a JSON example
            # or curly-brace code block).
            candidate = _extract_first_json_object(response)
            if candidate:
                patch_content = candidate.get("content", "")
                is_valid, errors = validate_markdown_content(patch_content)
                if not is_valid:
                    # Patch failed self-verification — feed back to agent
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"Your patch failed Markdown validation:\n" + "\n".join(f"- {e}" for e in errors) + "\n\nPlease fix the patch and output the corrected JSON."})
                    continue

                final_output = candidate
                break

            # Response didn't contain a valid patch — add to history and continue
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Continue your analysis. If ready, output the final JSON patch. If you need to read more files, use READ:<path>."})

        if final_output is None:
            # Max turns exhausted — use a placeholder fallback.
            final_output = json.loads(_make_fallback_patch(
                "\n### Rule from Incomplete Analysis\n- ReAct loop did not converge within max turns.",
                "ReAct loop exhausted — analysis incomplete",
            ))

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
    # Allowed inference-mode values (R1.4). The set is the union of the
    # Peirce / Douven abduction vocabulary and the Boden 2004 creativity
    # vocabulary. Either form is accepted; the heuristic accepts any case.
    ALLOWED_INFERENCE_MODES = (
        "abduction", "induction", "analogy",
        "combinational", "exploratory", "transformational",
    )

    def __init__(self, failure_modes_path: Path):
        self.failure_modes_path = failure_modes_path
        self.forbidden_keywords = []
        self._load_failure_modes()

    def _load_failure_modes(self):
        """Extracts key phrases from failure_modes.md for rule-based heuristics."""
        if not self.failure_modes_path.exists():
            return

        content = self.failure_modes_path.read_text().lower()
        # Note: keep this list in sync with the verbatim phrases in
        # references/failure_modes.md. Only add a heuristic after the
        # corresponding phrase exists in that file.
        heuristics = ["sci-fi", "infinite budget", "correlation", "trendy tool"]
        for word in heuristics:
            if word in content:
                self.forbidden_keywords.append(word)

    # ------------------------------------------------------------------
    # R1.2 — Lipton loveliness parsing
    # ------------------------------------------------------------------

    _LOVELINESS_RE = re.compile(
        r"loveliness\s*:\s*\(\s*"
        r"scope\s*=\s*([WMSwms])"
        r"\s*,\s*mechanism\s*=\s*([WMSwms])"
        r"\s*,\s*unification\s*=\s*([WMSwms])"
        r"\s*,\s*simplicity\s*=\s*([WMSwms])"
        r"\s*\)",
        re.IGNORECASE,
    )

    @classmethod
    def parse_loveliness(cls, text: str) -> tuple[int, int, int, int] | None:
        """Return the 4-tuple (W_count, M_count, S_count, total) for the
        proposal, or None if no Loveliness line is present.

        The total is always 4. Returns (W, M, S, 4).
        """
        m = cls._LOVELINESS_RE.search(text)
        if not m:
            return None
        marks = [g.upper() for g in m.groups()]
        return (
            sum(1 for v in marks if v == "W"),
            sum(1 for v in marks if v == "M"),
            sum(1 for v in marks if v == "S"),
            4,
        )

    # ------------------------------------------------------------------
    # R1.4 — Inference-mode parsing
    # ------------------------------------------------------------------

    _INFERENCE_MODE_RE = re.compile(
        r"[Ii]nference\s+[Mm]ode\s*:\s*([A-Za-z][A-Za-z\-]*)"
    )

    @classmethod
    def parse_inference_mode(cls, text: str) -> str | None:
        """Return the declared inference mode (case-insensitive match
        against `ALLOWED_INFERENCE_MODES`), or None if absent."""
        m = cls._INFERENCE_MODE_RE.search(text)
        if not m:
            return None
        mode = m.group(1).strip().lower()
        if mode in cls.ALLOWED_INFERENCE_MODES:
            return mode
        return mode  # return the raw value so the caller can report it

    def evaluate_heuristics(self, proposal_text: str) -> dict:
        """Applies fast, deterministic rule checks to the proposal."""
        failures = []
        proposal_lower = proposal_text.lower()

        # Check for structural completion
        # NOTE: These are prefix checks, not exact matches, to accommodate
        # template variants (e.g., "## 2. Background and Targeted Gap").
        # Both depths are accepted: '## ' (RESEARCH_PROPOSAL.md) and '### '
        # (HYPOTHESIS.md). A proposal must have section "1", "2", "3", "4"
        # at EITHER depth — not both. Proposals rendered from HYPOTHESIS.md
        # would otherwise be wrongly rejected.
        section_number_prefixes = ["1. ", "2. ", "3. ", "4. "]
        header_prefixes = ["## ", "### "]
        lines = proposal_text.split('\n')
        present_sections: set[str] = set()
        for line in lines:
            stripped = line.strip().lower()
            for hp in header_prefixes:
                if not stripped.startswith(hp):
                    continue
                rest = stripped[len(hp):]
                for sp in section_number_prefixes:
                    if rest.startswith(sp):
                        present_sections.add(sp)
                        break
        for sp in section_number_prefixes:
            if sp not in present_sections:
                failures.append(f"Missing mandatory section: heading starting with section number '{sp.strip()}'")

        # Check for banned concepts/phrases derived from failure_modes.md
        for kw in self.forbidden_keywords:
            if kw in proposal_lower:
                failures.append(f"Potential violation of failure mode: '{kw}' detected.")

        # R1.2 — Loveliness field present and above threshold
        lovely = self.parse_loveliness(proposal_text)
        if lovely is None:
            failures.append(
                "R1.2 Loveliness score missing — add a 'Loveliness: "
                "(scope=X, mechanism=Y, unification=Z, simplicity=W)' line "
                "with each X/Y/Z/W in {W, M, S}."
            )
        else:
            w_count = lovely[0]
            if w_count >= 3:
                failures.append(
                    f"R1.2 Loveliness below threshold ({w_count}/4 W's) — "
                    f"the candidate should be pruned or revised."
                )

        # R1.4 — Inference-mode field present and in the allowed vocabulary
        mode = self.parse_inference_mode(proposal_text)
        if mode is None:
            failures.append(
                "R1.4 Inference mode missing — declare an 'Inference Mode: "
                "<mode>' line with one of: "
                f"{', '.join(self.ALLOWED_INFERENCE_MODES)}."
            )
        elif mode not in self.ALLOWED_INFERENCE_MODES:
            failures.append(
                f"R1.4 Inference mode '{mode}' is not in the allowed "
                f"vocabulary: {', '.join(self.ALLOWED_INFERENCE_MODES)}."
            )

        return {
            "passed": len(failures) == 0,
            "reasons": failures
        }

    # ------------------------------------------------------------------
    # R1.8 — Boden-type diversity check across a candidate set
    # ------------------------------------------------------------------

    def evaluate_set_diversity(self, proposal_texts: list[str]) -> dict:
        """R1.8 — Evaluate the diversity of a Phase 2 candidate set.

        A candidate set of ≥ 2 hypotheses must cover ≥ 2 distinct
        inference modes. A single-mode set is a Phase 2 failure (the
        *under-explored conceptual space* trap documented in
        `references/failure_modes.md` §4).

        Single-candidate sets are not penalized — a one-candidate
        brainstorm is not yet a "set" in the sense the diversity rule
        is targeting.

        Returns: `{"passed": bool, "reasons": list[str], "modes_seen": list[str]}`.
        """
        if len(proposal_texts) < 2:
            return {"passed": True, "reasons": [], "modes_seen": []}

        modes: list[str] = []
        for text in proposal_texts:
            mode = self.parse_inference_mode(text)
            if mode is not None and mode in self.ALLOWED_INFERENCE_MODES:
                modes.append(mode)

        # We require diversity only over proposals that actually
        # declared a mode. Proposals missing the field are flagged by
        # the per-proposal heuristic already; counting them toward
        # diversity would mask the missing-field problem.
        unique_modes = set(modes)
        if len(unique_modes) < 2:
            return {
                "passed": False,
                "reasons": [
                    "R1.8 Candidate-set diversity failure: "
                    f"only {len(unique_modes)} distinct inference mode(s) "
                    f"across {len(proposal_texts)} candidates "
                    f"({sorted(unique_modes) or 'none declared'}). The "
                    "under-explored conceptual space trap "
                    "(failure_modes.md §4) requires ≥ 2 distinct modes."
                ],
                "modes_seen": sorted(unique_modes),
            }
        return {
            "passed": True,
            "reasons": [],
            "modes_seen": sorted(unique_modes),
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
    proposals_path = Path(args.proposals_dir).resolve()
    failure_modes_file = skill_path / "references" / "failure_modes.md"

    # Verify --proposals-dir is a real directory. Without this, the
    # subsequent glob() would silently return [] and the operator would
    # see an empty trace pool with no diagnostic.
    if not proposals_path.is_dir():
        parser.error(f"--proposals-dir does not exist or is not a directory: {proposals_path}")
    if not proposals_path.is_relative_to(Path.cwd().resolve()):
        print(f"[Warning] --proposals-dir resolves outside CWD: {proposals_path}")

    evaluator = IdeaEvaluator(failure_modes_file)
    error_analyst = ReActAnalyst(skill_path, role="error_analyst")
    success_analyst = ReActAnalyst(skill_path, role="success_analyst")
    error_analyst.MAX_TURNS = args.max_turns
    success_analyst.MAX_TURNS = args.max_turns
    error_analyst.MODEL = args.model
    success_analyst.MODEL = args.model

    # First pass: collect the per-proposal Stage 1 heuristic verdict and
    # the proposal text (for the R1.8 set-diversity check at the end).
    # The diversity check is a Phase 2 *set* property; it cannot be
    # applied per-proposal because a single combinational hypothesis is
    # not a failure on its own — only a set of one mode is.
    per_proposal_stage1: list[tuple[Path, str, dict]] = []  # (path, text, h_res)
    proposal_files = sorted(proposals_path.glob("*.md"))
    for file_path in proposal_files:
        text = file_path.read_text(encoding="utf-8")
        h_res = evaluator.evaluate_heuristics(text)
        per_proposal_stage1.append((file_path, text, h_res))

    # R1.8 — Compute the set-level diversity verdict ONCE, then attach
    # it to every proposal's trace so the patch-suggestion loop and the
    # downstream merge_patches.py see it. The set diversity is a
    # property of the brainstorm run, not of any individual candidate.
    all_texts = [t for _, t, _ in per_proposal_stage1]
    diversity = evaluator.evaluate_set_diversity(all_texts)
    if not diversity["passed"]:
        print(
            f"\n[R1.8 set-diversity] {diversity['reasons'][0]}"
        )
    else:
        print(
            f"\n[R1.8 set-diversity] {len(all_texts)} candidate(s) "
            f"cover {len(diversity['modes_seen'])} distinct inference "
            f"modes: {diversity['modes_seen']}."
        )

    success_pool = []
    failure_pool = []

    print(f"[*] Starting evaluation of proposals in: {proposals_path}")
    for file_path, text, h_res in per_proposal_stage1:
        print(f"\nAnalyzing {file_path.name}...")

        # Stage 1: Heuristic Check (already done in the first pass).
        # The R1.8 set-diversity verdict is attached to the trace even
        # on proposals that pass Stage 1 — a single combinational
        # candidate is fine in isolation, but the *set* is not.
        r18_set_failure = (
            "r1_8_set_diversity" if not diversity["passed"] else "r1_8_set_ok"
        )

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
                "r1_8_set_status": r18_set_failure,
                "r1_8_modes_seen": diversity["modes_seen"],
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
            "stage": "react",
            # Canonical fields (used by merge_patches.py):
            "critique": error_result["critique"],
            "suggested_patch": error_result["suggested_patch"],
            "rigorous": error_result["passed"],
            "turns_used": error_result["turns_used"],
            "patch_valid": error_result.get("patch_valid", False),
            # R1.8 set-diversity verdict (a property of the brainstorm
            # run, attached to every candidate's trace for downstream
            # consumers that read the JSON).
            "r1_8_set_status": r18_set_failure,
            "r1_8_modes_seen": diversity["modes_seen"],
            # Aliases for backward compatibility with older trace readers:
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
