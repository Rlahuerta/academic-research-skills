# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Academic Research Skills

A suite of Claude Code skills for rigorous academic research, paper writing, peer review, and pipeline orchestration.

## Skills Overview

| Skill | Purpose | Key Modes |
|-------|---------|-----------|
| `deep-research` v2.9.3 | 13-agent research team | full, quick, socratic, review, lit-review, fact-check, systematic-review |
| `academic-paper` v3.1.1 | 12-agent paper writing | full, plan, outline-only, revision, revision-coach, abstract-only, lit-review, format-convert, citation-check, disclosure |
| `academic-paper-reviewer` v1.9.0 | Multi-perspective paper review (5 reviewers + optional cross-model DA critique) | full, re-review, quick, methodology-focus, guided, calibration |
| `academic-pipeline` v3.6.8 | Full pipeline orchestrator | (coordinates all above) |

Suite version: 3.6.8. See CHANGELOG.md for full version history.

## Codebase Architecture

This is a **skill-plugin repository** — not a traditional application. There is no build step, no server, no package entry point. The repo ships markdown-based agent definitions and JSON Schema contracts validated by a Python lint/test suite.

### Directory layout

```
academic-pipeline/          Orchestrator SKILL.md + references/ (protocol docs, adapter overview)
academic-paper/             Paper-writing SKILL.md + agents/ (12 agent .md files) + references/
academic-paper-reviewer/    Reviewer SKILL.md + agents/ (7 agent .md files) + references/
deep-research/              Research SKILL.md + agents/ (13 agent .md files) + references/
shared/
  agents/                   compliance_agent.md (cross-cutting, mode-aware)
  contracts/                JSON Schema files — sprint contracts, passport schemas, audit schemas
    reviewer/               full.json, methodology_focus.json (Schema 13.1 sprint contracts)
    writer/                 full.json (generator pre-commitment contract)
    evaluator/              full.json (evaluator pre-commitment + scoring contract)
    passport/               literature_corpus_entry, rejection_log, reset_ledger_entry, audit_artifact_entry
    audit/                  audit_jsonl, audit_sidecar, audit_verdict schemas
  references/               Terminological glossaries + hedging-phrase rules + word-count conventions
  templates/                codex_audit_multifile_template.md
  sprint_contract.schema.json   Schema 13.1 — reviewer + writer + evaluator contract gate definition
  handoff_schemas.md            Material Passport schema definitions (Schema 9+)
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

### Data access levels

Three-tier isolation model (declarative, not runtime-enforced):
- `raw` — `deep-research`: ingests arbitrary user data
- `redacted` — `academic-paper`: operates on sanitized material
- `verified_only` — `academic-paper-reviewer`, `academic-pipeline`: only after upstream integrity gates

CI validates every SKILL.md declares a valid `data_access_level` frontmatter field.

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
PYTHONPATH=scripts python3 scripts/check_spec_consistency.py
PYTHONPATH=scripts python3 scripts/check_data_access_level.py
PYTHONPATH=scripts python3 scripts/check_task_type.py
PYTHONPATH=scripts python3 scripts/check_collaboration_depth_rubric.py
PYTHONPATH=scripts python3 scripts/check_version_consistency.py

# Lint + unittest pairs (check script then its test suite)
PYTHONPATH=. python3 -m unittest scripts.test_check_compliance_report scripts.test_validate_compliance_fixtures -v
PYTHONPATH=. python3 -m unittest scripts.test_check_collaboration_depth_rubric -v
PYTHONPATH=. python3 -m unittest scripts.test_check_version_consistency -v
PYTHONPATH=. python3 -m unittest scripts.test_check_sprint_contract -v
PYTHONPATH=. python3 -m unittest scripts.test_check_passport_reset_contract -v
PYTHONPATH=. python3 -m unittest scripts.test_check_v3_6_7_pattern_protection -v
PYTHONPATH=. python3 -m unittest scripts.test_audit_schemas scripts.test__next_verified_at_ms -v

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

# Single sprint contract template
python3 scripts/check_sprint_contract.py shared/contracts/reviewer/full.json --ars-version v3.6.8
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ARS_PASSPORT_RESET` | Opt-in: promote every FULL checkpoint to a context-reset boundary (v3.6.3) | OFF |
| `ARS_SOCRATIC_READING_PROBE` | Opt-in: Socratic mentor asks reading-check questions when user cites a paper (v3.5.1) | OFF |
| `ARS_CROSS_MODEL` | Enable cross-model verification via GPT or Gemini for integrity checks + DA critique (v3.0) | unset |
| `PYTHONPATH` | Must include `.` or `scripts` depending on the test module (see commands above) | — |

## Routing Rules

1. **academic-pipeline vs individual skills**: academic-pipeline = full pipeline orchestrator. If the user only needs a single function (just research, just write, just review), trigger the corresponding skill directly.
2. **deep-research vs academic-paper**: Complementary. deep-research = upstream research engine, academic-paper = downstream publication engine. Recommended flow: deep-research → academic-paper.
3. **deep-research socratic vs full**: socratic = guided Socratic dialogue to clarify research questions. full = direct production. When the user's research question is unclear, suggest socratic mode.
4. **academic-paper plan vs full**: plan = chapter-by-chapter guided planning via Socratic dialogue. full = direct paper production. When the user wants to think through their paper structure, suggest plan mode.
5. **academic-paper-reviewer guided vs full**: guided = Socratic review engaging the author in dialogue. full = standard multi-perspective review report. When the user wants to learn from the review, suggest guided mode.

## Key Rules

- All claims must have citations
- Evidence hierarchy respected (meta-analyses > RCTs > cohort > case reports > expert opinion)
- Contradictions disclosed with evidence quality comparison
- AI disclosure in all reports
- Default output language matches user input (Traditional Chinese or English)

## Full Academic Pipeline

```
deep-research (socratic/full)
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

### deep-research → academic-paper
Materials: RQ Brief, Methodology Blueprint, Annotated Bibliography, Synthesis Report, INSIGHT Collection

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
- **Version consistency** is CI-enforced: CLAUDE.md, SKILL.md files, and CHANGELOG.md must agree on the suite version.

## Version Info
- **Suite version**: 3.6.8 (per CHANGELOG.md)
- **Last Updated**: 2026-05-21
- **Author**: Cheng-I Wu
- **License**: CC-BY-NC 4.0
