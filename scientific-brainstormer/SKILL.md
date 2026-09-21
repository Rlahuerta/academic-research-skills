---
name: scientific-brainstormer
description: "Scientific hypothesis brainstorming and ideation skill. 4-phase workflow (contextual divergence → hypothesis synthesis → critical pruning → operationalization) with self-evolution via Trace2Skill trajectory analysis. v1.1 adds Lipton loveliness scoring to Phase 3 (R1.2), inference-mode labeling to Phase 2 (R1.4), and Boden-type diversity check (R1.8). Triggers: brainstorm hypotheses, generate research ideas, scientific ideation, design experiment, novel research direction."
metadata:
  version: "1.1.0"
  last_updated: "2026-06-01"
  status: active
  data_access_level: raw
  task_type: open-ended
  related_skills:
    - deep-research
    - academic-paper
    - academic-pipeline
---

# Scientific Brainstormer Skill

This skill guides the agent to systematically explore, formulate, and prune novel scientific hypotheses. It is structured to evolve continuously by analyzing its own output trajectories via the **Trace2Skill** paradigm (arXiv:2603.25158v3).

## Trigger Keywords

**English**: "brainstorm hypotheses", "generate research ideas", "scientific ideation", "novel research direction", "design an experiment", "hypothesis generation", "research brainstorming", "help me think of experiments", "what should I research"

## Mode Selection

This skill has a single mode. It is typically invoked as a **pre-research step** before `deep-research` or `academic-paper`, or as a **standalone ideation tool**. When the user's request involves generating novel scientific hypotheses or experimental designs, invoke this skill directly.

### Pipeline Position

```
scientific-brainstormer (ideation)
  → deep-research (literature grounding, feasibility assessment)
    → academic-paper (formal write-up)
```

The brainstormer can also be invoked mid-pipeline when `synthesis_agent` identifies a knowledge gap that requires novel hypothesis formulation.

---

## 1. Core Workflow

To brainstorm and design a scientific proposal, execute the following four phases:

### Phase 1: Contextual Divergence
* **Action:** Retrieve domain literature surrounding the target topic. Identify contrasting theories, unexplained anomalies, or unresolved debates.
* **Instruction:** Do not limit search queries to the main keywords. Look at adjacent fields (e.g., applying a machine learning architecture to fluid dynamics) to identify transdisciplinary analogies.

### Phase 2: Hypothesis Synthesis
* **Action:** Draft 3–5 candidate hypotheses using `templates/HYPOTHESIS.md`.
* **Instruction:** Force each hypothesis to be physically falsifiable, logically sound, and structurally distinct.
* **R1.4 — Inference mode label:** Every candidate must declare its inference mode (Section 6 of the template: one of `abduction`, `induction`, `analogy`). A single-mode candidate set is a Phase 2 failure — the brainstormer must generate at least 2 distinct modes across the candidates, otherwise the *under-explored conceptual space* trap (failure_modes.md §4) has already been triggered.
* **R1.8 — Boden-type diversity:** The candidate set should span the three Boden creativity types — *combinational* (≈ analogy), *exploratory* (≈ induction), *transformational* (≈ abduction). A combinational-only set is the dominant LLM-ideation failure mode; the agent should deliberately attempt at least one exploratory or transformational candidate per brainstorm.

### Phase 3: Critical Convergent Pruning
* **Action:** Subject each candidate hypothesis to rigorous counter-argumentation.
* **Instruction:** Assume the role of a hostile peer reviewer. Attempt to invalidate the hypothesis using the common pitfalls documented in `references/failure_modes.md`. Eliminate ideas that are physically implausible, untestable, or redundant.
* **R1.2 — Lipton loveliness scoring:** During pruning, score each surviving candidate on Lipton's four explanatory virtues (Section 5 of the template): `scope`, `mechanism`, `unification`, `simplicity` — each as W / M / S. A Loveliness score of three or four W's is **below threshold** and the candidate is pruned regardless of heuristic pass/fail. The trade-off with novelty (per IdeaBench, Guo et al. 2024) is: a candidate that scores high on novelty but low on feasibility (mechanism = W) is *flagged for revision* rather than auto-pruned. Pruning applies only to candidates below threshold on **both** novelty and feasibility.

### Phase 4: Operationalization
* **Action:** Convert the surviving hypothesis into a structured proposal using `templates/RESEARCH_PROPOSAL.md`.
* **Instruction:** Explicitly outline the required instruments, control groups, and statistical tests.

---

## 2. CRITICAL WARNINGS


### Rule from Failed Evaluation
- LLM call failed: litellm.InternalServerError: InternalServerError: OpenAIException - Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.

### CRITICAL WARNING: The Feasibility Fallacy
Never propose hypotheses that rely on uninvented tools, infinite compute budgets, or inaccessible datasets. Every proposed concept must include an "Operationalization" section detailing how it can be tested with current technology.

### CRITICAL WARNING: Incrementalism and Redundancy
Avoid proposing ideas that are minor parameter tweaks of existing, well-established studies. If the idea simply applies a standard model to a slightly different dataset without conceptual novelty, discard it.

---

## 3. Self-Evolution and Patch Proposals (Trace2Skill)

This skill is designed to improve automatically. When a brainstorming trajectory is complete:

1. **If the brainstorm succeeds** (i.e., passes external validation or detailed critique): The `Success Analyst` agent proposes additions to reinforce effective search patterns.
2. **If the brainstorm fails** (e.g., gets flagged for logical leaps, duplication, or infeasibility): The `Error Analyst` agent performs a ReAct loop to diagnose the failure, proposing a targeted patch to the guidelines above.

### Automation Scripts

- **`scripts/evaluate_ideas.py`** — Stage 1/2: Parses candidate proposals, runs structural heuristic checks, and triggers LLM-based critique (Devil's Advocate) to generate structured patch suggestions. Outputs `success_traces.json` (T⁺) and `failure_traces.json` (T⁻).
- **`scripts/merge_patches.py`** — Stage 3: Applies Trace2Skill's three guardrails, constructs a hierarchical merge tree, and reconciles independent patch proposals into conflict-free skill updates.

### Usage

```bash
# Stage 1 & 2: Evaluate proposals
python scientific-brainstormer/scripts/evaluate_ideas.py \
    --proposals-dir output/proposals \
    --skill-dir scientific-brainstormer

# Stage 3: Consolidate and apply patches
python scientific-brainstormer/scripts/merge_patches.py \
    --skill-dir scientific-brainstormer \
    --batch-size 4
```

## Known Limitations

- **Trace2Skill self-evolution requires external LLM API access** (via `litellm`). Without it, the evaluation and merge steps fall back to heuristic-only operation.
- **No automated trigger from the ARS pipeline yet.** The brainstormer must be invoked explicitly by the user or routed manually.
