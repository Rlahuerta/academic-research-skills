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