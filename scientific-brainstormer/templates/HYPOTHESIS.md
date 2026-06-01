# Scientific Hypothesis Template

Fill out this schema for every candidate hypothesis generated during Phase 2.

---

### 1. The Phenomenon / Observation
*What real-world observation, dataset anomaly, or theoretical gap does this address?*

### 2. Proposed Mechanism (The Core Hypothesis)
*State the hypothesis in a single, precise conditional statement: "If [Independent Variable/Mechanism], then [Dependent Variable/Observation] because [Underlying Principle]."*

### 3. Falsifiability Criteria
*What specific, measurable experimental result would prove this hypothesis completely false?*

### 4. Required Inputs and Tools
*What instruments, datasets, simulation software, or physical materials are necessary to test this?*

### 5. Loveliness Score (Lipton, 2004)
Score the hypothesis on Lipton's four explanatory virtues. Each dimension
takes a single letter — **W** (weak), **M** (moderate), or **S** (strong).
A hypothesis with three or four W's is *below threshold* and should be
revisited before it advances to Phase 3.

* **Scope** — does it explain more phenomena than competing explanations?
* **Mechanism** — is there a plausible, traceable causal chain?
* **Unification** — does it connect to other phenomena or domains?
* **Simplicity** — Occam's edge: is it the simplest explanation that fits?

Format: `Loveliness: (scope=X, mechanism=Y, unification=Z, simplicity=W)` with each X/Y/Z/W in {W, M, S}.

### 6. Inference Mode
Declare the cognitive mode used to generate this hypothesis. Pick one:

* **abduction** — inferring the best explanation of an observed pattern (Peirce / Douven)
* **induction** — generalizing from prior literature or replicated observations
* **analogy** — transferring structure from a different domain

The Boden (2004) creativity-types are a parallel vocabulary you may use
in addition to the mode label: **combinational** (≈ analogy),
**exploratory** (≈ induction), **transformational** (≈ abduction).

Format: `Inference Mode: <mode>` (or `Inference Mode: <mode> | Boden type: <type>`).

A diverse Phase 2 candidate set should cover ≥ 2 distinct modes. A
single-mode candidate set is the *under-explored conceptual space*
failure mode documented in `references/failure_modes.md` §4.
