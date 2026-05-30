# Abstract Quality Guidelines

Reference document for the `academic-abstract` skill. Use during Phase 3 (Quality Verification) to evaluate draft abstracts.

---

## Quality Dimensions

### D1: Structural Completeness (0–100)

| Score | Criterion |
|-------|-----------|
| 90–100 | All 6 components present, clearly demarcated, each 1–3 sentences |
| 70–89 | All 6 components present but one is underdeveloped or ambiguous |
| 50–69 | One component missing or two are severely underdeveloped |
| 30–49 | Two components missing or multiple are confused |
| 0–29 | Three or more components missing; reads as an introduction, not an abstract |

**Most common failure:** Missing Gap statement. If the abstract reads as "We did X and found Y" without establishing WHY X was necessary, score ≤ 69.

### D2: Specificity of Findings (0–100)

| Score | Criterion |
|-------|-----------|
| 90–100 | All key findings include specific metrics (effect sizes, accuracy, p-values, sample sizes) |
| 70–89 | Most findings have metrics; one uses a vague qualifier |
| 50–69 | Findings use vague qualifiers ("significantly," "notably," "markedly") without numbers |
| 30–49 | Findings are described in purely qualitative terms ("we observed interesting patterns") |
| 0–29 | No findings are reported; abstract stops at Method |

### D3: Active Voice and Clarity (0–100)

| Score | Criterion |
|-------|-----------|
| 90–100 | Predominantly active voice; no jargon without definition; readable by adjacent-field researcher |
| 70–89 | Mostly active voice; 1–2 jargon terms without context; readable by same-field researcher |
| 50–69 | Mixed active/passive; multiple undefined jargon terms; readable only by specialists |
| 30–49 | Predominantly passive voice; dense jargon; readability barrier for non-specialists |
| 0–29 | Exclusively passive; reads as a machine translation or keyword dump |

### D4: Implication Scoping (0–100)

| Score | Criterion |
|-------|-----------|
| 90–100 | Implications are tightly scoped to the evidence; every claim is traceable to a finding |
| 70–89 | Implications are mostly scoped; one minor overreach |
| 50–69 | Implications include one clear overclaim (generalizing beyond sample/method) |
| 30–49 | Multiple overclaims; implications read as advocacy rather than evidence-based inference |
| 0–29 | Implications are entirely disconnected from the findings (e.g., policy recommendations from a lab study) |

---

## Failure Modes

### F1: The Overclaiming Trap
**Symptom:** Abstract claims generalizability, policy impact, or theoretical revolution that the paper's evidence cannot support.
**Example:** A pilot study with n=30 claims "This approach should be adopted in all educational systems."
**Remediation:** Implications must explicitly scope claims ("within this sample," "for this domain," "pending replication").

### F2: The Jargon Dump
**Symptom:** Abstract is unreadable by anyone outside the exact subfield. Every sentence contains 2+ undefined technical terms.
**Example:** "We leverage transformer-based self-attention mechanisms with hierarchical residual connections for multi-scale feature extraction in a federated learning paradigm."
**Remediation:** Replace each technical term with its functional equivalent. If the term is essential, define it in the same sentence.

### F3: The Missing Gap
**Symptom:** Abstract jumps from Background to Objective without establishing why the study was necessary.
**Example:** "Machine learning is important for healthcare. This study uses deep learning for medical imaging."
**Remediation:** Every abstract must contain a contrastive gap statement: "However, [specific deficiency in existing work]."

### F4: The Passive Voice Plague
**Symptom:** Every sentence uses passive construction. The abstract reads as a sequence of things that happened to unnamed actors.
**Example:** "The data were analyzed. A model was trained. Results were obtained."
**Remediation:** Rewrite in active voice: "We analyzed the data. We trained a convolutional neural network. We found that..."

### F5: The Metric Vacuum
**Symptom:** Key Findings section contains no numbers, effect sizes, or statistical indicators.
**Example:** "Results showed that the proposed method performed significantly better than baselines."
**Remediation:** Require at least one specific metric per key finding: accuracy improvement, effect size, p-value, or sample characteristic.

### F6: The Word Count Violation
**Symptom:** Abstract exceeds venue word limit by >10% or is >20% below the minimum.
**Example:** A 400-word abstract for a venue with a 250-word limit.
**Remediation:** Enforce word count during drafting. If the abstract is too long, cut Background and Method first; never cut Gap or Key Findings.

---

## Best Practices (from Literature)

### From Auto-Research Literature (Kong et al., 2026)
- **Abstract as a standalone document:** A reader should understand the paper's contribution from the abstract alone, without reading the full text.
- **Four-phase lifecycle integration:** Abstract writing sits in the "Writing" phase, but it must be informed by the "Creation" phase (literature grounding) and validated in the "Validation" phase (peer review).

### From AutoResearchClaw (Liu et al., 2026)
- **Adversarial review for abstracts:** Before finalizing, have a separate agent (Devil's Advocate) challenge every claim in the abstract against the full paper text. If the full paper does not support a claim, the abstract must be revised.
- **Cross-run evolution:** Track which abstract phrasings correlate with acceptance. Over time, reinforce patterns that work and deprecate patterns that fail.

### From Trace2Skill (Ni et al., 2026)
- **Skill improvement via trajectory analysis:** Run the abstract skill on a diverse set of papers. For each abstract that succeeds (acceptance) or fails (rejection), extract a patch. Use hierarchical consolidation to merge patches into the skill guidelines.

---

## Decision Thresholds

| Overall Score | Action |
|---------------|--------|
| ≥ 85 | Accept — abstract is publication-ready |
| 65–84 | Minor revision — 1–2 specific issues to fix |
| 50–64 | Major revision — structural or substantive problems |
| < 50 | Reject — rewrite from source material |

---

## References

- Kong, L., Sun, X., Chow, W., et al. (2026). "AI for Auto-Research: Roadmap & User Guide." arXiv:2605.18661.
- Liu, J., Qiu, S., Li, M., et al. (2026). "AutoResearchClaw: Self-Reinforcing Autonomous Research with Human-AI Collaboration." arXiv:2605.20025.
- Ni, J., Liu, Y., Liu, X., et al. (2026). "Trace2Skill: Distill Trajectory-Local Lessons into Transferrable Agent Skills." arXiv:2603.25158v3.
