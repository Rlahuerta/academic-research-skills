# Scientific Brainstorming Pitfalls & Failure Modes

Refer to this document during Phase 3 (Critical Pruning) to flag and discard fragile ideas.

---

### 1. The Infinite Budget / Sci-Fi Instrument Fallacy
* **Definition:** Designing an experiment that relies on technology that does not exist or is highly cost-prohibitive (e.g., "build a space-based gravitational wave detector to test this specific material").
* **SOP Remediation:** Enforce the "Current State-of-the-Art" constraint. The experiment must be executable under standard university laboratory configurations or available cloud compute APIs.

### 2. Correlation-Causation Leap
* **Definition:** Assuming that because variable A and variable B correlate in existing literature, a mechanism must exist where A causes B.
* **SOP Remediation:** Force the agent to explicitly write down the intermediate biochemical, physical, or logical steps connecting A to B.

### 3. The "Tool in Search of a Problem" Trap
* **Definition:** Over-indexing on a specific trendy tool (e.g., "Let's apply LLMs to X") without verifying if the tool actually fits the underlying mathematics or physics of the domain.
* **SOP Remediation:** Verify whether simpler classical baselines (e.g., linear regression, basic statistical modeling) solve the problem equally well or better.

### 4. The Under-Explored Conceptual Space Trap (Boden, 2004)
* **Definition:** A candidate set in which every hypothesis is the *same* type of creative move — typically all *combinational* (apply known method X to domain Y). The agent never reaches *exploratory* ideation (push known method into a new region of its parameter space) or *transformational* ideation (change the rules of the space itself). This is the most common failure of LLM ideation: minor parameter tweaks dressed as novelty.
* **SOP Remediation:** A Phase 2 candidate set of ≥ 2 hypotheses must cover **≥ 2 distinct inference modes** (abduction / induction / analogy) or Boden types (combinational / exploratory / transformational). A single-mode candidate set is a heuristic *failure* even if every individual hypothesis is well-formed — the brainstormer has not yet earned the right to converge on a recommendation.
* **Example of a failing set:** "Apply transformer attention to fluid dynamics" + "Apply transformer attention to protein folding" + "Apply transformer attention to materials discovery" — all combinational, all on the same axis.
* **Example of a passing set:** "Apply transformer attention to fluid dynamics" (analogy / combinational) + "Use low-Reynolds-number scaling laws to predict turbulence onset without simulation" (abduction / transformational) + "The information-theoretic bound on fluid-flow prediction may be lower than previously estimated, because the system is approximately low-dimensional" (abduction / transformational).
