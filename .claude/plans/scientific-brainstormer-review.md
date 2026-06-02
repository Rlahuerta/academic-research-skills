# Plan: Review and Fix `scientific-brainstormer/` Skill

## 1. Problem Statement

The `scientific-brainstormer/` skill has structural integrity but contains **5 functional bugs** and **4 design flaws** that prevent it from operating correctly as a Trace2Skill self-evolution pipeline. The skill was built following the Trace2Skill paradigm (arXiv:2603.25158v3) but deviates from the paper's prescribed patterns in critical ways.

---

## 2. Findings

### BUG-1: Wrong Default Directory Path (Blocking)

**Location:** `scientific-brainstormer/scripts/merge_patches.py:202`
**Problem:** Default `--skill-dir` is `skills/scientific_brainstormer` (underscore) but actual directory is `scientific-brainstormer` (hyphen). Running the script without explicit `--skill-dir` fails with "Target file does not exist."

**Fix:** Change default to `scientific-brainstormer`.

### BUG-2: Header Mismatch Between Heuristic Check and Template (Blocking)

**Location:** `scientific-brainstormer/scripts/evaluate_ideas.py`
**Problem:** The heuristic check expects exact headers:
```python
required_headers = [
    "## 1. Title & Abstract",
    "## 2. Background",
    "## 3. Methodology",
    "## 4. Expected Limitations"
]
```
But the actual `RESEARCH_PROPOSAL.md` template uses:
- `## 1. Title & Abstract` ✓ (matches)
- `## 2. Background and Targeted Gap` ✗ (does NOT match "## 2. Background")
- `## 3. Methodology & Experimental Design` ✗ (does NOT match "## 3. Methodology")
- `## 4. Expected Limitations & Risk Mitigation` ✗ (does NOT match "## 4. Expected Limitations")

**Result:** ALL proposals generated from the official template will fail the heuristic check, meaning every proposal gets routed to the Error Analyst unnecessarily, and the Success Analyst never sees a passing proposal.

**Fix:** Update `required_headers` to match actual template headers, or use prefix matching (e.g., `line.startswith("## 2. Background")`) instead of exact string inclusion.

### BUG-3: Success Analyst Result Is Computed But Never Used (Medium)

**Location:** `scientific-brainstormer/scripts/evaluate_ideas.py:~374`
**Problem:** Both `error_result` and `success_result` are computed, but only `error_result["passed"]` determines the pass/fail classification. The `success_result` (including its patch suggestions, critique, and turns_used) is never written to `success_traces.json`.

**Result:** Successful trajectories carry no learning signal. The Success Analyst's output is silently discarded.

**Fix:** Write `success_result` into `success_traces.json` entries.

### BUG-4: No Duplication Prevention in Patch Application (Medium)

**Location:** `scientific-brainstormer/scripts/merge_patches.py:apply_patch()`
**Problem:** The `apply_patch()` method inserts content after a target section without checking whether the exact same content already exists. Running the evolution pipeline twice on the same failure mode will produce duplicate rules in SKILL.md.

**Fix:** Before inserting, check if `insert_text.strip()` is already a substring of the file content. If so, skip insertion and log a deduplication notice.

### BUG-5: Patch Application Is Fragile (Low)

**Location:** `scientific-brainstormer/scripts/merge_patches.py:apply_patch()`
**Problem:** Uses `content.split(target_section, 1)` which splits on the first occurrence. If the section heading appears inside a code block or another section's content, the insertion point is wrong. Also, inserting with `target_section + "\n" + insert_text` does not guarantee proper markdown spacing.

**Fix:** Use regex-based section boundary detection (`^## .*\n`) or ensure the section is at line-start. Add a blank line before inserted content.

---

### DESIGN-1: Missing Patch Validation in Trace Save (Medium)

**Location:** `scientific-brainstormer/scripts/evaluate_ideas.py`
**Problem:** The `suggested_patch` from the LLM is saved directly to `failure_traces.json` without validating that it is well-formed markdown. A malformed patch will later crash `merge_patches.py` during consolidation.

**Fix:** Call `validate_markdown_content()` on the patch content before saving to traces. If invalid, save the critique but mark the patch as `null`.

### DESIGN-2: No Golden Set Tests for the Scripts (Medium)

**Location:** `scientific-brainstormer/tests/`
**Problem:** There are no unit tests for `evaluate_ideas.py` or `merge_patches.py`. The golden set (`tests/golden_set/`) exists but there is no automated test that runs the scripts against it and asserts expected pass/fail outcomes.

**Fix:** Add `tests/test_evaluate_ideas.py` that runs the evaluator against each golden proposal and asserts PASS for the good proposal and FAIL for the bad ones.

### DESIGN-3: SKILL.md Still Claims "Error Analyst is single-pass" (Low)

**Location:** `scientific-brainstormer/SKILL.md:102`
**Problem:** The Known Limitations section says "The Error Analyst is currently single-pass. Multi-turn ReAct loop upgrade is planned." But the code was already upgraded to a multi-turn ReAct loop in Task C. This is stale documentation.

**Fix:** Remove this outdated limitation. The ReAct loop is implemented.

### DESIGN-4: Trace2Skill Consolidation Does Not Match Paper's Parallel Design (Low)

**Location:** `scientific-brainstormer/scripts/merge_patches.py:run_hierarchical_merge()`
**Problem:** The Trace2Skill paper (§2.3) describes "parallel multi-agent patch proposal" where "a fleet of success and error-analyst sub-agents independently processes batches of trajectories, proposing targeted patches." The current `merge_patches.py` runs sequentially (`for i in range(0, len(patches), self.batch_size)`), not in parallel.

**Fix:** Use Python's `concurrent.futures.ThreadPoolExecutor` to dispatch batch merges in parallel, or add a comment noting that true parallelism requires API rate-limit management and the current sequential approach is a pragmatic simplification.

---

## 3. Approach

Fix all bugs first (they break the pipeline), then address design flaws.

### Option A: Minimal Fix (chosen)
- Fix BUG-1 through BUG-5
- Add patch validation in trace save (DESIGN-1)
- Add unit tests (DESIGN-2)
- Remove stale limitation (DESIGN-3)
- Add comment on parallelism (DESIGN-4)

### Option B: Full Parallel Rewrite (rejected)
- Rewriting `merge_patches.py` for true parallel execution would add complexity (API rate limiting, result ordering) without clear benefit for the current golden set size (3 proposals). Parallelism matters at scale (200+ trajectories per the paper), but the current use case is small-batch.

## 4. Implementation Steps

### Step 1: Fix `merge_patches.py` default path and add deduplication
- Change `--skill-dir` default from `skills/scientific_brainstormer` to `scientific-brainstormer`
- Add duplication check in `apply_patch()`: skip if `insert_text.strip()` already in file
- Improve insertion spacing: add blank line before inserted content

### Step 2: Fix `evaluate_ideas.py` header checks and success analyst usage
- Update `required_headers` to use prefix matching or match actual template headers
- Write `success_result` data into `success_traces.json` entries
- Add markdown validation before saving traces

### Step 3: Remove stale limitation from SKILL.md
- Delete the "Error Analyst is currently single-pass" bullet

### Step 4: Add unit tests
- Create `scientific-brainstormer/tests/test_evaluate_ideas.py`
- Run against golden set and assert expected outcomes

### Step 5: Verify
- Run golden set through `evaluate_ideas.py` — good proposal should PASS, bad proposals should FAIL
- Run `merge_patches.py` — should produce valid SKILL.md updates
- Run all lints: `check_data_access_level.py`, `check_task_type.py`, `check_version_consistency.py`, `check_spec_consistency.py`

## 5. Verification Criteria

```
✓ evaluate_ideas.py --proposals-dir tests/golden_set --skill-dir scientific-brainstormer
  → proposal_good_peer_feedback.md: PASSED Stage 1 + ReAct
  → proposal_bad_infeasible_instruments.md: FAILED Stage 1
  → proposal_bad_correlation_causation.md: FAILED Stage 1
✓ merge_patches.py --skill-dir scientific-brainstormer --batch-size 4
  → produces valid patch, no duplicates, no unbalanced markdown
✓ All CI lints pass
✓ No CJK characters in modified files
```
