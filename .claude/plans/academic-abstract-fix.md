# Plan: Fix and Integrate `academic-abstract/` Skill

## 1. Problem Statement

The `academic-abstract/SKILL.md` is broken in 7 ways:

| Issue | Severity | Detail |
|-------|----------|--------|
| **No YAML frontmatter** | Blocking | CI lint `check_data_access_level.py` and `check_task_type.py` fail on this file |
| **Fake commands** | Blocking | References `/ars-plan`, `/ars-lit-review`, `/ars-citation-check` — these do not exist in the ARS codebase |
| **No directory structure** | High | Bare markdown file with no `references/`, `templates/`, or `scripts/` — not a proper ARS skill |
| **Wrong pipeline integration** | High | Claims a "10-stage ARS pipeline" for abstract generation that doesn't match actual ARS architecture |
| **Chinese text** | Medium | Mentions "bilingual abstracts (zh-TW + EN)" — violates English-only policy |
| **No version/metadata** | Medium | No `version`, `data_access_level`, `task_type`, `related_skills` |
| **No CLAUDE.md integration** | Medium | Not referenced in routing rules, Skills Overview, or MODE_REGISTRY.md |

## 2. Literature Context (from `revbib/`)

Four papers inform the redesign:

1. **Trace2Skill (2603.25158v3)** — Skill formalization $S = (M, \mathcal{R})$, multi-agent patch proposal, hierarchical consolidation. Already used for `scientific-brainstormer`. Reinforces the need for structured templates + references + scripts.
2. **AI for Auto-Research (2026-05-18)** — Four-phase research lifecycle (Creation → Writing → Validation → Dissemination). Writing phase includes structured abstract generation with specific quality gates. Useful for positioning abstract writing within the research pipeline.
3. **AutoResearchClaw (2026-05-19)** — Multi-agent research with structured debate, PIVOT/REFINE loops, cross-run evolution. Their "Phase 3: Writing" has "Outline → Draft → Peer Review → Revision" with a quality gate. Good for understanding how abstract writing benefits from adversarial review.
4. **AI co-mathematician (2026-05-13)** — Stateful multi-agent workbench, tracking failed hypotheses, iterative exploration. Less directly relevant but reinforces the agentic workflow pattern.

## 3. Approach

**Option A: Fix `academic-abstract/` as a standalone skill** (chosen)
- Rewrite SKILL.md with proper frontmatter, trigger keywords, mode selection
- Create `templates/ABSTRACT.md` with the structured 6-component abstract format
- Create `references/abstract_quality_guidelines.md` with failure modes and best practices drawn from revbib literature
- Wire into ARS pipeline as a downstream skill from `academic-paper` (abstract is typically extracted/refined from a completed paper)
- Remove all Chinese text
- Add to CLAUDE.md Skills Overview, routing rules, MODE_REGISTRY.md

**Option B: Merge into `academic-paper/` as a mode** (rejected)
- The `academic-paper` skill already has an `abstract-only` mode. The current `academic-abstract/` is redundant but poorly integrated. However, keeping it separate allows it to evolve independently (per Trace2Skill principles) and serve users who only need abstract help.

## 4. Implementation Steps

### Step 1: Rewrite `academic-abstract/SKILL.md`
- Add YAML frontmatter: `name: academic-abstract`, `version: 1.0.0`, `data_access_level: redacted`, `task_type: open-ended`, `related_skills: [academic-paper, deep-research, academic-pipeline]`
- Define trigger keywords (English only)
- Define single mode: abstract-only (structured 6-component abstract generation)
- Reference actual ARS skills: `academic-paper abstract-only` mode, `deep-research` for literature grounding, `academic-paper-reviewer` for Devil's Advocate quality check
- Remove all `/ars-*` fake commands
- Keep the 6-component structure (Background, Gap, Objective, Method, Key Findings, Implications) — this is valid and used in ARS
- Add handoff materials section

### Step 2: Create `templates/ABSTRACT.md`
- Structured template with all 6 components
- Include word-count guidance per discipline
- Include examples of good vs bad abstract snippets

### Step 3: Create `references/abstract_quality_guidelines.md`
- Draw from revbib literature on abstract writing quality
- Include failure modes: overclaiming, jargon overload, missing gap statement, unfalsifiable implications
- Include best practices: active voice, specific metrics, explicit gap framing

### Step 4: Wire into ARS
- Add to CLAUDE.md Skills Overview table
- Add to directory layout
- Add routing rule: "academic-abstract vs academic-paper abstract-only"
- Add handoff protocol: `academic-paper → academic-abstract` (Materials: Complete paper text → Structured abstract)
- Update MODE_REGISTRY.md (26 → 27 modes)

### Step 5: Verify
- Run `check_data_access_level.py` — should pass (was failing on this file)
- Run `check_task_type.py` — should pass (was failing on this file)
- Run `check_version_consistency.py` — should pass
- Run `check_spec_consistency.py` — should pass
- Confirm no CJK characters in any new/modified files

## 5. Verification Criteria

```
✓ check_data_access_level.py passes with 0 violations
✓ check_task_type.py passes with 0 violations
✓ check_version_consistency.py passes
✓ check_spec_consistency.py passes (no dead links, frontmatter valid)
✓ No Chinese/CJK characters in academic-abstract/ files
✓ SKILL.md has valid YAML frontmatter with all required fields
✓ CLAUDE.md references academic-abstract in Skills Overview, routing, handoff
✓ MODE_REGISTRY.md updated (27 modes total)
```
