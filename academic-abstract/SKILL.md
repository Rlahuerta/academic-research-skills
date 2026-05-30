---
name: academic-abstract
description: "Academic abstract generation and refinement skill. Produces structured 6-component abstracts (Background, Gap, Objective, Method, Key Findings, Implications) with quality gates. Can generate from a completed paper, from research notes, or refine an existing draft. Triggers: write abstract, abstract only, generate abstract, refine abstract, paper abstract, conference abstract."
metadata:
  version: "1.0.0"
  last_updated: "2026-05-29"
  status: active
  data_access_level: redacted
  task_type: open-ended
  related_skills:
    - academic-paper
    - deep-research
    - academic-paper-reviewer
    - academic-pipeline
---

# Academic Abstract Skill

This skill coordinates the generation, refinement, and quality verification of academic paper abstracts. It leverages the multi-agent orchestration and integrity gates of the **Academic Research Skills (ARS)** suite to ensure abstracts are academically rigorous, factual, and structurally complete.

## Trigger Keywords

**English**: "write abstract", "abstract only", "generate abstract", "refine abstract", "paper abstract", "conference abstract", "create abstract", "help me write an abstract", "abstract for my paper", "draft abstract"

## Mode Selection

This skill has a single mode. It is typically invoked:
- **As a downstream step** after `academic-paper` has produced a complete paper draft — the abstract is synthesized from the full text
- **As a standalone request** when the user has research notes or a preliminary draft and needs a structured abstract
- **As a refinement tool** when the user has an existing abstract that needs quality improvement

### Pipeline Position

```
academic-paper (full/plan/outline-only) or deep-research (full)
  → academic-abstract (abstract generation / refinement)
    → academic-paper-reviewer (quick quality check — optional)
```

The abstract skill can also be invoked mid-pipeline when the user explicitly requests abstract help during a paper-writing session.

---

## 1. Core Workflow

### Phase 1: Input Assessment
- **Action:** Determine what source material the user has provided (complete paper, research notes, existing abstract draft, or bare research question).
- **Instruction:** If the user provides a complete paper, extract the abstract components directly from the text. If only notes or a research question are provided, use `deep-research` to ground the Background and Gap before drafting.

### Phase 2: Structured Drafting
- **Action:** Draft the abstract using `templates/ABSTRACT.md`.
- **Instruction:** Force all six components to be present. Do not skip the Gap statement — it is the most commonly omitted and most critical component for reader engagement.

### Phase 3: Quality Verification
- **Action:** Run the abstract through the quality checklist in `references/abstract_quality_guidelines.md`.
- **Instruction:** Check for overclaiming, jargon overload, missing metrics, and passive voice. Flag any component that scores below threshold.

### Phase 4: Peer Review (Optional)
- **Action:** If the user requests high-stakes output (conference submission, journal submission), route the draft to `academic-paper-reviewer` in `quick` mode for a focused quality assessment.
- **Instruction:** The reviewer checks for alignment between the abstract's claims and the actual paper content (if available). The Devil's Advocate agent evaluates for overclaiming or logical gaps between Objective and Implications.

---

## 2. CRITICAL WARNINGS

### CRITICAL WARNING: The Overclaiming Trap
Never write implications that exceed what the Method and Key Findings actually support. If the paper is a pilot study with n=30, the abstract must not claim "This approach generalizes to all populations." Implications must be scoped to the evidence presented.

### CRITICAL WARNING: The Jargon Dump
An abstract is not a vocabulary showcase. If a technical term is not essential for understanding the contribution, remove it. The abstract must be readable by a researcher in an adjacent subfield, not just by a specialist in the exact niche.

### CRITICAL WARNING: The Missing Gap
An abstract without an explicit gap statement ("However, current models fail to...") reads as incremental or solution-in-search-of-a-problem. Every abstract must contain a clear, specific gap that justifies the study's existence.

---

## 3. Structural Guidelines

The final abstract must contain all six components, clearly demarcated:

1. **Background:** Establish the domain significance in 1–2 sentences. Cite 1–2 foundational works if the abstract format permits.
2. **Gap:** Point out a concrete research deficiency. Use a contrastive transition ("However," "Despite advances in," "While existing work has").
3. **Objective:** State the paper's precise contribution in active voice. Begin with "This study," "We propose," or "Here we demonstrate."
4. **Method:** Describe the research design or framework in 1–2 sentences. Include sample size, dataset, or experimental paradigm if relevant.
5. **Key Findings:** Lay out the primary results. Use specific metrics (effect sizes, accuracy improvements, statistical significance) rather than vague qualifiers ("significantly," "notably").
6. **Implications:** Suggest how these findings influence the broader field or practical applications. Scope claims to what the evidence supports.

### Word Count Conventions

- **APA 7.0 / Social Sciences**: 150–250 words
- **IEEE / Engineering**: 150–200 words
- **Nature / Science**: 150–200 words (strict)
- **Conference abstracts (e.g., CHI, NeurIPS)**: 250–300 words
- **Dissertation abstract**: 350–500 words

When the user does not specify a venue, default to **APA 7.0 conventions** (150–250 words, structured abstract with explicit headings if required by the venue).

---

## 4. Post-Operation Integrity Checklist

Before finalizing and exporting the abstract, verify the following gates:

- [ ] **Socratic Alignment:** Was the abstract generated from verified source material (complete paper, research notes with citations, or grounded literature review)?
- [ ] **Structural Completion:** Are all six components (Background, Gap, Objective, Method, Key Findings, Implications) present and identifiable?
- [ ] **Reference Provenance:** Have all cited works in the Background been verified against the paper's reference list or academic databases?
- [ ] **Peer-Review Gate (optional):** If high-stakes, has the abstract been checked by `academic-paper-reviewer` for overclaims or rhetorical weaknesses?
- [ ] **Format Alignment:** Does the abstract match the target venue style and remain within the appropriate word limit?

---

## 5. Self-Evolution and Patch Proposals (Trace2Skill)

This skill is designed to improve automatically. When an abstract trajectory is complete:

1. **If the abstract succeeds** (passes quality verification, receives positive user feedback, or is accepted by a venue): The Success Analyst proposes additions to reinforce effective phrasing patterns.
2. **If the abstract fails** (rejected by venue, flagged for overclaiming, or scores poorly on quality rubric): The Error Analyst diagnoses the failure and proposes a targeted patch to the guidelines above.

### Automation Scripts

- **`scripts/evaluate_abstracts.py`** — Stage 1/2: Parses candidate abstracts, runs structural heuristic checks (6-component completeness, word count, passive voice detection), and triggers LLM-based critique to generate structured patch suggestions. Outputs `success_traces.json` (T⁺) and `failure_traces.json` (T⁻).
- **`scripts/merge_patches.py`** — Stage 3: Applies Trace2Skill's three guardrails, constructs a hierarchical merge tree, and reconciles independent patch proposals into conflict-free skill updates.

---

## Known Limitations

- **Trace2Skill self-evolution requires external LLM API access** (via `litellm`). Without it, the evaluation and merge steps fall back to heuristic-only operation.
- **No automated trigger from the ARS pipeline yet.** The abstract skill must be invoked explicitly by the user or routed manually from `academic-paper`.
- **Venue-specific formatting** (e.g., IEEE two-column abstracts, structured abstracts with bold headings) requires manual configuration — no automatic venue detection.
