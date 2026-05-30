# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Academic Research Skills

A suite of Claude Code skills for rigorous academic research, paper writing, peer review, and pipeline orchestration.

## Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

## Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Skills Overview

| Skill | Purpose | Key Modes |
|-------|---------|-----------|
| `scientific-brainstormer` v1.0.0 | Scientific hypothesis ideation with Trace2Skill self-evolution | brainstorm (4-phase: divergence → synthesis → pruning → operationalization) |
| `deep-research` v2.9.3 | 13-agent research team | full, quick, socratic, review, lit-review, fact-check, systematic-review |
| `academic-paper` v3.1.1 | 12-agent paper writing | full, plan, outline-only, revision, revision-coach, abstract-only, lit-review, format-convert, citation-check, disclosure |
| `academic-abstract` v1.0.0 | Structured abstract generation with 6-component quality gates | abstract-only (Background, Gap, Objective, Method, Key Findings, Implications) |
| `academic-paper-reviewer` v1.9.0 | Multi-perspective paper review (5 reviewers + optional cross-model DA critique) | full, re-review, quick, methodology-focus, guided, calibration |
| `academic-pipeline` v3.6.8 | Full pipeline orchestrator | (coordinates all above) |

Suite version: 3.6.8. See CHANGELOG.md for full version history.

## Codebase Architecture

This is a **skill-plugin repository** — not a traditional application. There is no build step, no server, no package entry point. The repo ships markdown-based agent definitions and JSON Schema contracts validated by a Python lint/test suite.

### Directory layout

```
academic-pipeline/          Orchestrator SKILL.md + references/ (protocol docs, adapter overview)
academic-paper/             Paper-writing SKILL.md + agents/ (12 agent .md files) + references/
academic-abstract/           Abstract-generation SKILL.md + templates/ + references/
academic-paper-reviewer/    Reviewer SKILL.md + agents/ (7 agent .md files) + references/
deep-research/              Research SKILL.md + agents/ (13 agent .md files) + references/
scientific-brainstormer/    Hypothesis ideation SKILL.md + templates/ + references/ + scripts/ (Trace2Skill)
shared/
  agents/                   compliance_agent.md (cross-cutting, mode-aware)
  contracts/                JSON Schema files — sprint contracts, passport schemas, audit schemas
    reviewer/               full.json, methodology_focus.json (Schema 13.1 sprint contracts)
    writer/                 full.json (generator pre-commitment contract)
    evaluator/              full.json (evaluator pre-commitment + scoring contract)
    passport/               literature_corpus_entry, rejection_log, reset_ledger_entry, audit_artifact_entry
    audit/                  audit_jsonl, audit_sidecar, audit_verdict schemas
  references/               Terminological glossaries + hedging-phrase rules + word-count conventions (v3.6.7 operational contracts)
  templates/                codex_audit_multifile_template.md
  sprint_contract.schema.json   Schema 13.1 — reviewer + writer + evaluator contract gate definition
  handoff_schemas.md            Material Passport schema definitions (Schema 9+)
  contracts/README.md           Contract template creation procedure + reserved-mode inventory
scripts/                   All CI lint validators + their test_*.py pairs + reference adapters
  adapters/                folder_scan.py, zotero.py, obsidian.py + tests/
  fixtures/                Test fixtures for lint validators
tests/
  fixtures/v3.6.6-ab/      A/B evidence fixture stub (30 files), manifest-driven
docs/
  ARCHITECTURE.md           Full pipeline architecture (stages × gates × data flow)
  PERFORMANCE.md            Token budget + long-running session guidance
  SETUP.md                  Installation alternatives
  design/                   Spec documents for major features (sprint contracts, consumer integration, etc.)
MODE_REGISTRY.md            Single source of truth — all 25 modes across 4 skills
```

### The contract/schema system

The central architectural pattern: every agent in a review/generation pipeline commits to a **sprint contract** (JSON, validated against `shared/sprint_contract.schema.json`) BEFORE seeing the artifact it will evaluate. This is the **generator-evaluator contract gate** (v3.6.6/v3.6.8):

- **Reviewer contracts** (v3.6.2): paper-content-blind Phase 1 commits a scoring plan → paper-visible Phase 2 scores against it. Templates at `shared/contracts/reviewer/`.
- **Writer contracts** (v3.6.8): paper-blind Phase 4a pre-commitment → paper-visible Phase 4b drafting + self-scoring. Template at `shared/contracts/writer/full.json`.
- **Evaluator contracts** (v3.6.8): paper-blind Phase 6a pre-commitment → paper-visible Phase 6b scoring + decision. Template at `shared/contracts/evaluator/full.json`.

Synthesizers consume contracts via a three-step mechanical protocol (build matrix → evaluate with panel-relative quantifiers → resolve precedence by severity). Forbidden-ops lists prevent post-hoc rubric editing.

### The Material Passport (Schema 9+)

Append-only ledger carrying the artifact state across pipeline stages and sessions. Key fields:
- `literature_corpus[]` — optional user-curated literature (v3.6.4 input port, v3.6.5 consumer integration)
- `reset_boundary[]` — context-reset checkpoints for cross-session resume (v3.6.3)
- `compliance_history[]` — append-only audit trail (v3.4)
- `repro_lock` — stochasticity declaration (populated or explicit `null`)

### Audit artifact system (v3.6.7 Step 6)

Cross-model audit pipeline for downstream-agent deliverables:
- **Schemas**: `audit_jsonl`, `audit_sidecar`, `audit_verdict` in `shared/contracts/audit/`
- **Snapshot capture**: `scripts/audit_snapshot.py` — takes a point-in-time snapshot of agent outputs
- **Cross-model dispatch**: `scripts/run_codex_audit.sh` — dispatches to GPT/Gemini via `ARS_CROSS_MODEL`
- **Verdict parsing**: `scripts/parse_audit_verdict.py` — parses cross-model responses into structured findings
- **Consistency check**: `scripts/check_audit_artifact_consistency.py` — enforces cross-artifact invariants across audit lifecycle. Spec: `docs/design/2026-04-30-ars-v3.6.7-step-6-orchestrator-hooks-spec.md`

### Data access levels

Three-tier isolation model (declarative, not runtime-enforced):
- `raw` — `deep-research`: ingests arbitrary user data
- `redacted` — `academic-paper`: operates on sanitized material
- `verified_only` — `academic-paper-reviewer`, `academic-pipeline`: only after upstream integrity gates

CI validates every SKILL.md declares a valid `data_access_level` frontmatter field.

### Shared utility modules

Key Python modules under `scripts/` that are imported by multiple check scripts:

- **`scripts/_skill_lint.py`** — shared YAML frontmatter parser used by `check_data_access_level.py`, `check_task_type.py`, `check_collaboration_depth_rubric.py`, `check_version_consistency.py`, `check_spec_consistency.py`
- **`scripts/_test_helpers.py`** — shared test utilities (temp directory creation, fixture loading)
- **`scripts/_next_verified_at_ms.py`** — helper for computing next verification timestamps (used by audit schema tests)
- **`scripts/adapters/_common.py`** — shared adapter utilities (CSL-JSON field extraction, YAML emission, rejection-log helpers)

**Shared reference files (v3.6.7 operational contracts):**

- **`shared/references/irb_terminology_glossary.md`** — IRB/human-subjects terminology
- **`shared/references/psychometric_terminology_glossary.md`** — instrument-design vocabulary
- **`shared/references/protected_hedging_phrases.md`** — allowed hedging-phrase vocabulary with forbidden-substitution rules
- **`shared/references/word_count_conventions.md`** — per-section word-count contract definitions

These carry operational contracts — agent prompts cite them by path. `check_v3_6_7_pattern_protection.py` enforces protection-clause presence and obligation-phrase shape.

Additional tooling scripts:

- **`scripts/run_codex_audit.sh`** — cross-model audit dispatcher for GPT/Gemini (used with `ARS_CROSS_MODEL`)
- **`scripts/audit_snapshot.py`** / **`scripts/parse_audit_verdict.py`** — audit artifact snapshot and verdict parsing

## Development Commands

### Install dependencies

```bash
pip install -r requirements-dev.txt
```

Dependencies: `pyyaml`, `jsonschema[format]>=4.17`. Tests additionally need `pytest`.

### Running tests and lints

CI checks are defined in `.github/workflows/spec-consistency.yml`. All scripts live in `scripts/`.

**Pattern — check scripts use `PYTHONPATH=scripts`; unittest suites use `PYTHONPATH=.`:**

```bash
# Lint-only scripts (no tests)
PYTHONPATH=scripts python3 scripts/check_spec_consistency.py        # frontmatter + README dead-link validation
PYTHONPATH=scripts python3 scripts/check_data_access_level.py
PYTHONPATH=scripts python3 scripts/check_task_type.py
PYTHONPATH=scripts python3 scripts/check_collaboration_depth_rubric.py
PYTHONPATH=scripts python3 scripts/check_version_consistency.py
PYTHONPATH=scripts python3 scripts/check_benchmark_report.py
PYTHONPATH=scripts python3 scripts/check_repro_lock.py
PYTHONPATH=scripts python3 scripts/check_prisma_trAIce_freshness.py
PYTHONPATH=scripts python3 scripts/check_compliance_report.py

# Lint + unittest pairs (check script then its test suite)
PYTHONPATH=. python3 -m unittest scripts.test_check_compliance_report scripts.test_validate_compliance_fixtures -v
PYTHONPATH=. python3 -m unittest scripts.test_check_collaboration_depth_rubric -v
PYTHONPATH=. python3 -m unittest scripts.test_check_version_consistency -v
PYTHONPATH=. python3 -m unittest scripts.test_check_sprint_contract -v
PYTHONPATH=. python3 -m unittest scripts.test_check_passport_reset_contract -v
PYTHONPATH=. python3 -m unittest scripts.test_check_v3_6_7_pattern_protection -v
PYTHONPATH=. python3 -m unittest scripts.test_audit_schemas scripts.test__next_verified_at_ms -v
PYTHONPATH=. python3 -m unittest scripts.test_check_data_access_level -v
PYTHONPATH=. python3 -m unittest scripts.test_check_task_type -v
PYTHONPATH=. python3 -m unittest scripts.test_check_benchmark_report -v
PYTHONPATH=. python3 -m unittest scripts.test_check_repro_lock -v
PYTHONPATH=. python3 -m unittest scripts.test_check_prisma_trAIce_freshness -v
PYTHONPATH=. python3 -m unittest scripts.test_reading_probe_lint -v
PYTHONPATH=. python3 -m unittest scripts.test_reading_probe_lint -v

# Standalone validators (no paired unittest)
python3 scripts/check_v3_6_6_ab_manifest.py
python3 scripts/check_literature_corpus_schema.py
python3 scripts/check_corpus_consumer_protocol.py
python3 scripts/sync_adapter_docs.py --check
python3 scripts/check_passport_reset_contract.py --root .
python3 scripts/check_v3_6_7_pattern_protection.py

# Sprint contract validation (run against each template)
for f in shared/contracts/reviewer/*.json shared/contracts/writer/*.json shared/contracts/evaluator/*.json; do
  python3 scripts/check_sprint_contract.py "$f" --ars-version v$(grep -m1 -oE '[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
done

# Adapter tests (pytest) + audit artifact consistency test (pytest)
pip install pytest
PYTHONPATH=. pytest scripts/adapters/tests/ -v
PYTHONPATH=. pytest scripts/test_check_audit_artifact_consistency.py -v
```

**Running a single test or check:**

```bash
# Single unittest module
PYTHONPATH=. python3 -m unittest scripts.test_check_sprint_contract -v

# Single test method
PYTHONPATH=. python3 -m unittest scripts.test_check_sprint_contract.TestCheckSprintContract.test_positive_reviewer_full -v

# Single sprint contract template
python3 scripts/check_sprint_contract.py shared/contracts/reviewer/full.json --ars-version v3.6.8

# Single pytest test
PYTHONPATH=. pytest scripts/adapters/tests/test_folder_scan.py::test_specific_case -v
```

## CI Workflows

Three GitHub Actions workflows live in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `spec-consistency.yml` | Every push + PR | Runs all lint validators, unittest suites, sprint contract validation, and manifest/v3.6.7 checks |
| `pytest.yml` | PR/push to adapter-related paths only | Runs `pytest scripts/adapters/tests/` (path-filtered to avoid running on unrelated changes) |
| `freshness-check.yml` | Weekly cron (Mon 09:00 UTC) + push to PRISMA-trAIce files | Warns on upstream PRISMA-trAIce drift (non-blocking; exits 0 unless parse error) |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ARS_PASSPORT_RESET` | Opt-in: promote every FULL checkpoint to a context-reset boundary (v3.6.3) | OFF |
| `ARS_SOCRATIC_READING_PROBE` | Opt-in: Socratic mentor asks reading-check questions when user cites a paper (v3.5.1) | OFF |
| `ARS_CROSS_MODEL` | Enable cross-model verification via GPT or Gemini for integrity checks + DA critique (v3.0) | unset |
| `PYTHONPATH` | Must include `.` or `scripts` depending on the test module (see commands above) | — |

## Routing Rules

1. **academic-pipeline vs individual skills**: academic-pipeline = full pipeline orchestrator. If the user only needs a single function (just research, just write, just review), trigger the corresponding skill directly.
2. **scientific-brainstormer vs deep-research**: scientific-brainstormer = hypothesis ideation and novelty generation. deep-research = literature-grounded investigation. When the user needs to generate novel research ideas or experimental designs before knowing what to research, use scientific-brainstormer first, then feed the surviving hypothesis into deep-research for literature grounding.
3. **deep-research vs academic-paper**: Complementary. deep-research = upstream research engine, academic-paper = downstream publication engine. Recommended flow: deep-research → academic-paper.
4. **deep-research socratic vs full**: socratic = guided Socratic dialogue to clarify research questions. full = direct production. When the user's research question is unclear, suggest socratic mode.
5. **academic-paper plan vs full**: plan = chapter-by-chapter guided planning via Socratic dialogue. full = direct paper production. When the user wants to think through their paper structure, suggest plan mode.
6. **academic-abstract vs academic-paper abstract-only**: academic-abstract = dedicated abstract generation with quality gates and 6-component structure. academic-paper abstract-only = abstract generation as part of the full paper-writing pipeline. When the user only needs an abstract (not a full paper), use academic-abstract directly. When the user is already in a paper-writing session, use academic-paper's built-in abstract-only mode.
7. **academic-paper-reviewer guided vs full**: guided = Socratic review engaging the author in dialogue. full = standard multi-perspective review report. When the user wants to learn from the review, suggest guided mode.

## Key Rules

- All claims must have citations
- Evidence hierarchy respected (meta-analyses > RCTs > cohort > case reports > expert opinion)
- Contradictions disclosed with evidence quality comparison
- AI disclosure in all reports
- Default output language matches user input (Traditional Chinese or English)

## Full Academic Pipeline

```
scientific-brainstormer (optional pre-research ideation)
  → deep-research (socratic/full)
    → academic-paper (plan/full)
      → integrity check (Stage 2.5)
        → academic-paper-reviewer (full/guided)
          → academic-paper (revision)
            → academic-paper-reviewer (re-review, max 2 loops)
              → final integrity check (Stage 4.5)
                → academic-paper (format-convert → final output)
                  → Process Summary + AI Self-Reflection Report
```

## Handoff Protocol

### scientific-brainstormer → deep-research
Materials: Surviving hypothesis (from Phase 3 pruning), Research Proposal draft (from Phase 4 operationalization), Failure trace log (if any hypotheses were eliminated and why)

### deep-research → academic-paper
Materials: RQ Brief, Methodology Blueprint, Annotated Bibliography, Synthesis Report, INSIGHT Collection

### academic-paper → academic-abstract
Materials: Complete paper text (all sections), target venue word-count limit, venue style guide (if known). The abstract skill extracts Background, Gap, Objective, Method, Key Findings, and Implications directly from the paper text.

### academic-abstract → academic-paper-reviewer
Materials: Structured abstract draft + source paper text (for alignment verification). The reviewer checks for overclaiming, missing gap statements, and word-count compliance.

### academic-paper → academic-paper-reviewer
Materials: Complete paper text. field_analyst_agent auto-detects domain and configures reviewers.

### academic-paper-reviewer → academic-paper (revision)
Materials: Editorial Decision Letter, Revision Roadmap, Per-reviewer detailed comments

## Key Architectural Constraints

- **Sprint contracts are mandatory** for `full` and `methodology_focus` reviewer modes, and for `writer_full`/`evaluator_full` modes (see `shared/sprint_contract.schema.json`, validated by `scripts/check_sprint_contract.py`).
- **Every check_*.py script has a paired test_check_*.py module** — when modifying a lint rule, update both.
- **When adding a new skill**, read `shared/ground_truth_isolation_pattern.md` first. New SKILL.md files must declare `data_access_level` and `task_type` in frontmatter.
- **Material Passport** fields need corresponding JSON Schema files in `shared/contracts/passport/`.
- **Adapter tests** use pytest; all other tests use unittest. Both run in CI via separate workflows.
- **Version consistency** is CI-enforced via `scripts/check_version_consistency.py` with three invariants:
  1. Every skill version in the CLAUDE.md Skills Overview table must match its `SKILL.md` `metadata.version` frontmatter.
  2. CLAUDE.md "Suite version: X.Y.Z" must match the most recent `## [X.Y.Z]` entry in CHANGELOG.md.
  3. `academic-pipeline` version in the table must equal the suite version (pipeline = orchestrator, tracks suite release).
- **Mode Registry** (`MODE_REGISTRY.md`) is the authoritative source of truth — 25 modes across 4 skills. When adding/modifying modes, update MODE_REGISTRY.md first, then propagate to SKILL.md and CLAUDE.md.
- **Corpus consumer manifest** (`scripts/corpus_consumer_manifest.json`) registers every agent that consumes `literature_corpus[]`. When wiring a new consumer agent, update the manifest — `check_corpus_consumer_protocol.py` derives its validation targets from it.

## Version Info
- **Suite version**: 3.6.8 (per CHANGELOG.md)
- **Last Updated**: 2026-05-21
- **Author**: Cheng-I Wu
- **License**: CC-BY-NC 4.0
