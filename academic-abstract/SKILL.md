This skill coordinates the generation, citation verification, and peer review of research article abstracts. It leverages the multi-agent orchestration and integrity gates of the **Academic Research Skills (ARS)** suite to ensure abstracts are academically rigorous, factual, and structurally complete.

---

## 1. Prerequisites and Environment Setup

To enable full multi-agent parallelization (such as spawning the `synthesis_agent` or `research_architect_agent`), ensure the following environment settings are configured in your Claude Code CLI before initiating the workflow:

```bash
# Enable parallel subagents for multi-agent synthesis and review stages
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

---

## 2. Integrated ARS Workflow

The generation of an abstract follows the standard 10-stage ARS pipeline, mapping specific commands to abstract components:

```
                     ┌────────────────────────┐
                     │  /ars-plan (Socratic)  │ ───► Refine Objective & Gap
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │  /ars-lit-review       │ ───► Build Background & Gap
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │  synthesis_agent       │ ───► Draft initial Abstract
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │  academic-paper-       │ ───► Devil's Advocate &
                     │  reviewer              │      0-100 Quality Check
                     └────────────────────────┘
```

### Stage 1: Conceptual Alignment (`/ars-plan`)
Before drafting, execute `/ars-plan` to engage the Socratic tutor agent. Rather than immediately writing the abstract, use this guided dialogue to explicitly clarify:
1. The **core research question** (the Objective).
2. The **disciplinary gap** being targeted (the Gap).

### Stage 2: Literature Grounding (`/ars-lit`)
Run `/ars-lit` or `/ars-lit-review` to extract established themes and identify relevant papers. 
* Use the **synthesis_agent** to summarize previous work. This ensures that your abstract's **Background** is contextualized within the actual literature.
* Validate that any citations referenced in your background are verified against academic databases (such as Semantic Scholar) to prevent hallucinated references.

### Stage 3: Draft Synthesis (`synthesis_agent`)
Utilize the `synthesis_agent` and `report_compiler_agent` to construct the draft. The agent must package the extracted manuscript data into a single, cohesive paragraph containing the six essential abstract components:
* **Background:** Broader research landscape and motivation.
* **Gap:** Explicit limitation or unresolved question in existing work (e.g., *"However, current models fail to..."*).
* **Objective:** Action-oriented goal of the study.
* **Method:** Methodology, data generation, and analytical framework used.
* **Key Findings:** Organized summary of primary discoveries (e.g., *"First, ... Second, ... Third, ..."*).
* **Implications:** Practical value or systemic recommendations resulting from the work.

### Stage 4: Citation Integrity Check (`/ars-citation-check`)
Ensure all facts, statistics, or methodology references mentioned in the draft abstract correspond to verified facts in the paper's codebase and reference directory. Run `/ars-citation-check` (or `/verify-citations`) to catch any misattributions.

### Stage 5: Peer Review and Revision (`academic-paper-reviewer`)
Submit the draft abstract to the `academic-paper-reviewer` skill (which runs an Editor-in-Chief agent, dynamic reviewers, and a **Devil's Advocate** agent). 
* The Devil's Advocate agent will evaluate the abstract for overclaiming, lack of clarity, or logical gaps between the stated **Objective** and the final **Implications**.
* Ensure the abstract scores highly on the 0–100 quality rubrics before finalizing.

---

## 3. Structural Guidelines for the Abstract

The agent must structure the final output to address each logical section clearly:

1. **Background:** Establish the domain significance clearly.
2. **Gap:** Point out a concrete research deficiency.
3. **Objective:** State the paper's precise contribution.
4. **Method:** Describe the research design or framework concisely.
5. **Key Findings:** Lay out the primary data points or conceptual results.
6. **Implications:** Suggest how these findings influence the broader field or practical applications.

---

## 4. Post-Operation Integrity Checklist

Before finalizing and exporting the abstract (using bilingual outputs, LaTeX, or Markdown as configured by the ARS writing module), verify the following gates:

- [ ] **Socratic Alignment:** Was the abstract generated from a structurally verified paper outline initialized by `/ars-plan`?
- [ ] **Structural Completion:** Are all six components (Background, Gap, Objective, Method, Key Findings, Implications) present?
- [ ] **Reference Provenance:** Have all cited works passed the Stage 2.5 integrity checks and Semantic Scholar verification?
- [ ] **Peer-Review Gate:** Has the abstract been analyzed by the Devil's Advocate for potential overclaims or rhetorical weaknesses?
- [ ] **Format Alignment:** Does the abstract match the target venue style (e.g., APA 7, IEEE, Chicago) and remain within the appropriate word limit?