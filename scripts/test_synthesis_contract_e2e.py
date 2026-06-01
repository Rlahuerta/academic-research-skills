"""Synthetic integration test for the v3.7+ prompt-contract e2e chain.

This is the closest we can get to an end-to-end test without calling
an LLM. It exercises the full pipeline:

    1. Build a `SynthesisReport` programmatically (3 themes, each with
       2 valid Toulmin claims and 2 Loveliness scores).
    2. Serialize it to Markdown in the canonical form expected by the
       synthesis-agent Output Format.
    3. Parse the Markdown with `_synthesis_markdown_parser.parse_synthesis_markdown`.
    4. Validate the parsed report with
       `check_synthesis_output_structure` as a subprocess.
    5. Assert: themes, claims, Loveliness scores, knowledge gaps all
       round-trip without loss AND the validator passes.

This proves:
    (a) the Markdown format the prompt demands is parseable,
    (b) the parser tolerates the format (no false positives),
    (c) the validator accepts the parsed structure (the contract is
        satisfiable end-to-end),
    (d) the round-trip is lossless on the structural fields.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Reuse the parser as a real import (not importlib) so the test reflects
# how downstream consumers would use it.
sys.path.insert(0, str(SCRIPTS_DIR))
import _synthesis_markdown_parser as parser_mod  # noqa: E402

CHECK_SCRIPT = SCRIPTS_DIR / "check_synthesis_output_structure.py"


def _build_report() -> parser_mod.SynthesisReport:
    """Build a small but representative `SynthesisReport`."""
    report = parser_mod.SynthesisReport()

    # Theme 1: latency-as-mechanism
    t1 = parser_mod.Theme(
        name="Theme 1: Feedback latency as active mechanism",
        evidence_strength="Strong",
        sources="5 sources, Levels I-III",
        synthesis_text=(
            "Three converging evidence streams establish feedback "
            "latency, not volume, as the key variable."
        ),
    )
    t1.toulmin_claims.append(
        parser_mod.ToulminClaim(
            claim_id="Theme 1.C1",
            claim=(
                "Feedback latency, not volume, is the primary mechanism "
                "by which AI-assisted assessment improves learning."
            ),
            data=[
                "Author1 (2023, Level I) — finding",
                "Author2 (2024, Level II) — finding",
            ],
            warrant=(
                "Converging evidence across two operationalizations of "
                "latency establishes the mechanism."
            ),
            backing="Hattie's (2009) feedback framework (theoretical).",
            qualifier=(
                "In higher-education STEM, 2020-2024, within the "
                "methodological constraints of the included studies."
            ),
            rebuttal=(
                "Author3 (2022) for the population-B counterexample; "
                "the effect reverses in low-quality AI systems."
            ),
            loveliness=parser_mod.LovelinessScore(
                scope="M", mechanism="S", unification="W", simplicity="M"
            ),
        )
    )
    t1.toulmin_claims.append(
        parser_mod.ToulminClaim(
            claim_id="Theme 1.C2",
            claim=(
                "The latency effect is bounded by an upper threshold "
                "of about 24 hours."
            ),
            data=["Author2 (2024, Level II); Author4 (2024, Level I)"],
            warrant="Dose-response curve from two converging RCTs.",
            backing="Hattie & Timperley (2007) feedback timing model.",
            qualifier="In higher-education STEM contexts.",
            rebuttal=(
                "Author5 (2023) reports a higher threshold in "
                "professional-development contexts."
            ),
            loveliness=parser_mod.LovelinessScore(
                scope="S", mechanism="M", unification="M", simplicity="S"
            ),
        )
    )
    report.themes.append(t1)

    # Theme 2: transfer to non-STEM
    t2 = parser_mod.Theme(
        name="Theme 2: Transfer to non-STEM domains",
        evidence_strength="Moderate",
        sources="3 sources, Levels II-IV",
        synthesis_text=(
            "Effect generalizes to non-STEM but with smaller effect "
            "sizes; one contradicted study shows the effect is weaker."
        ),
    )
    t2.toulmin_claims.append(
        parser_mod.ToulminClaim(
            claim_id="Theme 2.C1",
            claim=(
                "The latency effect generalizes to non-STEM domains "
                "but with smaller effect sizes."
            ),
            data=[
                "Author2 (2024, Level II)",
                "Author6 (2023, Level III)",
                "Author7 (2024, Level IV)",
            ],
            warrant="Effect-size meta-analysis across domains.",
            backing="Bloom (1985) mastery-learning framework.",
            qualifier="In higher-education non-STEM, 2018-2024.",
            rebuttal=(
                "Author9 (2024) shows the effect reverses in "
                "language-learning contexts."
            ),
            loveliness=parser_mod.LovelinessScore(
                scope="S", mechanism="M", unification="M", simplicity="S"
            ),
        )
    )
    t2.toulmin_claims.append(
        parser_mod.ToulminClaim(
            claim_id="Theme 2.C2",
            claim=(
                "Transfer effect is mediated by instructional design "
                "fidelity, not by domain per se."
            ),
            data=["Author7 (2024, Level IV); Author8 (2023, Level III)"],
            warrant="Mediation analysis across two operationalizations.",
            backing="Kraft & Hill (2020) instructional-fidelity model.",
            qualifier="In adult-learner populations, blended delivery.",
            rebuttal=(
                "Author6 (2023) finds no mediation in fully-online "
                "delivery; population is the boundary."
            ),
            loveliness=parser_mod.LovelinessScore(
                scope="M", mechanism="M", unification="M", simplicity="M"
            ),
        )
    )
    report.themes.append(t2)

    # Theme 3: equity implications
    t3 = parser_mod.Theme(
        name="Theme 3: Equity and access",
        evidence_strength="Emerging",
        sources="2 sources, Levels III-IV",
        synthesis_text=(
            "Two studies surface equity concerns: latency-driven "
            "feedback advantages students with reliable home internet."
        ),
    )
    t3.toulmin_claims.append(
        parser_mod.ToulminClaim(
            claim_id="Theme 3.C1",
            claim=(
                "Latency-driven feedback advantages students with "
                "reliable home internet access."
            ),
            data=["Author10 (2023, Level III); Author11 (2024, Level IV)"],
            warrant=(
                "Two independent studies document a digital-divide "
                "moderation effect on the latency benefit."
            ),
            backing="Warschauer (2004) digital-divide framework.",
            qualifier=(
                "In K-12 and undergraduate populations with "
                "self-reported home-internet access."
            ),
            rebuttal=(
                "Author12 (2024) finds no moderation when schools "
                "provide on-campus study spaces."
            ),
            loveliness=parser_mod.LovelinessScore(
                scope="M", mechanism="M", unification="M", simplicity="S"
            ),
        )
    )
    t3.toulmin_claims.append(
        parser_mod.ToulminClaim(
            claim_id="Theme 3.C2",
            claim=(
                "Equity effects are bounded by school-level device "
                "provisioning; effects shrink in 1:1 device schools."
            ),
            data=["Author10 (2023, Level III); Author13 (2024, Level IV)"],
            warrant="Comparative analysis across 1:1 vs shared-device schools.",
            backing="Penuel (2006) technology-resources framework.",
            qualifier="In U.S. public K-12 schools, 2018-2024.",
            rebuttal=(
                "Author14 (2024) finds the effect holds in 1:1 schools "
                "if teacher training is low — training is the boundary."
            ),
            loveliness=parser_mod.LovelinessScore(
                scope="S", mechanism="M", unification="M", simplicity="M"
            ),
        )
    )
    report.themes.append(t3)

    # Knowledge gaps and contradictions — downstream consumers rely on
    # these.
    report.knowledge_gaps = [
        "No longitudinal studies (>1 year) in Taiwan context",
        "Limited data on AI assessment in laboratory courses",
        "Equity effects under-studied in non-U.S. populations",
    ]
    report.contradictions = [
        {
            "raw": (
                "| Author2: latency drives effect | Author3: quality "
                "drives effect | Reconciled: quality modulates latency "
                "in low-quality AI systems. |"
            )
        }
    ]
    report.evidence_convergence_map = (
        "Strong:      [==========] Theme 1 (7 sources, Levels I-III)\n"
        "Moderate:    [======    ] Theme 2 (4 sources, Levels III-V)\n"
        "Emerging:    [====      ] Theme 3 (2 sources, Levels III-IV)"
    )
    report.theoretical_integration = (
        "Findings connect to Hattie's (2009) feedback framework, "
        "Bloom's (1985) mastery-learning model, Warschauer's (2004) "
        "digital-divide framework, and the more recent ICALM (2023) "
        "AI-pedagogy framework."
    )
    report.synthesis_limitations = [
        "Pre-2018 literature is under-represented",
        "Most studies are US-based; generalizability beyond US is uncertain",
        "Few studies report effect sizes by equity subgroups",
    ]
    return report


def _render_report(report: parser_mod.SynthesisReport) -> str:
    """Render a SynthesisReport to the canonical Markdown form.

    The renderer is intentionally minimal: it produces the format the
    parser consumes, not full Markdown fidelity. The same renderer is
    used in `test__synthesis_markdown_parser.TestRoundTrip` and is
    mirrored here for the integration test."""
    out = ["# Synthesis Report\n", "## Key Themes\n"]
    for theme in report.themes:
        out.append(f"#### {theme.name}")
        if theme.evidence_strength:
            out.append(f"**Evidence Strength**: {theme.evidence_strength}")
        if theme.sources:
            out.append(f"**Sources**: {theme.sources}")
        if theme.synthesis_text:
            out.append(f"**Synthesis**: {theme.synthesis_text}")
        for claim in theme.toulmin_claims:
            out.append("")
            out.append(f"> **Claim** ({claim.claim_id}): {claim.claim}")
            if claim.data:
                out.append(f"> **Data**: {'; '.join(claim.data)}")
            if claim.warrant:
                out.append(f"> **Warrant**: {claim.warrant}")
            if claim.backing:
                out.append(f"> **Backing**: {claim.backing}")
            if claim.qualifier:
                out.append(f"> **Qualifier**: {claim.qualifier}")
            if claim.rebuttal:
                out.append(f"> **Rebuttal**: {claim.rebuttal}")
            if claim.loveliness:
                s = claim.loveliness
                out.append(
                    f"> **Loveliness**: "
                    f"(scope={s.scope}, mechanism={s.mechanism}, "
                    f"unification={s.unification}, simplicity={s.simplicity})"
                )
        out.append("")
    if report.contradictions:
        out.append("### Contradictions & Resolutions")
        for c in report.contradictions:
            out.append(c.get("raw", ""))
        out.append("")
    if report.knowledge_gaps:
        out.append("### Knowledge Gaps")
        for i, g in enumerate(report.knowledge_gaps, 1):
            out.append(f"{i}. {g}")
        out.append("")
    if report.evidence_convergence_map:
        out.append("### Evidence Convergence Map")
        out.append(report.evidence_convergence_map)
        out.append("")
    if report.theoretical_integration:
        out.append("### Theoretical Integration")
        out.append(report.theoretical_integration)
        out.append("")
    if report.synthesis_limitations:
        out.append("### Synthesis Limitations")
        for lim in report.synthesis_limitations:
            out.append(f"- {lim}")
        out.append("")
    return "\n".join(out)


class TestEndToEndRoundTrip(unittest.TestCase):
    def test_full_pipeline_stub_serialize_parse_validate(self):
        # 1. Build
        original = _build_report()
        # 2. Serialize
        rendered = _render_report(original)
        # 3. Parse
        re_parsed = parser_mod.parse_synthesis_markdown(rendered)

        # 4a. Round-trip structural assertions
        self.assertEqual(
            len(re_parsed.themes), len(original.themes),
            f"theme count changed: {len(re_parsed.themes)} vs "
            f"{len(original.themes)}"
        )
        for orig_theme, new_theme in zip(original.themes, re_parsed.themes):
            self.assertEqual(orig_theme.name, new_theme.name)
            self.assertEqual(
                len(new_theme.toulmin_claims),
                len(orig_theme.toulmin_claims),
                f"claim count changed in {new_theme.name}",
            )
            for orig_claim, new_claim in zip(
                orig_theme.toulmin_claims, new_theme.toulmin_claims
            ):
                self.assertEqual(orig_claim.claim_id, new_claim.claim_id)
                self.assertEqual(orig_claim.claim, new_claim.claim)
                self.assertEqual(orig_claim.warrant, new_claim.warrant)
                self.assertEqual(orig_claim.backing, new_claim.backing)
                self.assertEqual(orig_claim.qualifier, new_claim.qualifier)
                self.assertEqual(orig_claim.rebuttal, new_claim.rebuttal)
                self.assertEqual(
                    orig_claim.loveliness.as_tuple()
                    if orig_claim.loveliness else None,
                    new_claim.loveliness.as_tuple()
                    if new_claim.loveliness else None,
                )
        self.assertEqual(
            re_parsed.knowledge_gaps, original.knowledge_gaps,
            "knowledge gaps lost in round-trip"
        )
        self.assertEqual(
            len(re_parsed.contradictions), len(original.contradictions),
        )
        # No missing-component warnings (the synthesized report is clean)
        missing = [w for w in re_parsed.warnings if "missing" in w]
        self.assertEqual(
            missing, [],
            f"unexpected missing-component warnings: {missing}"
        )

        # 4b. Validate via the CLI subprocess — proves the contract is
        # satisfiable end-to-end.
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "round_trip_report.md"
            out_path.write_text(rendered, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(out_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Validator should pass the round-tripped report; got "
                f"exit {result.returncode}.\nstdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
            self.assertIn("[OK]", result.stdout)
            # 3 themes, 6 claims, all pass
            self.assertIn("3 theme(s)", result.stdout)
            self.assertIn("6 Toulmin claim(s)", result.stdout)


class TestContractIsV37Compliant(unittest.TestCase):
    """Light assertions that the contract is v3.7+ compliant (no
    pre-v3.7+ output and no warnings). This is a regression test
    against accidentally emitting backward-compat content."""

    def test_round_tripped_report_is_v37_compliant(self):
        report = parser_mod.SynthesisReport()
        # Single theme with a single claim with all components and a
        # Loveliness score above threshold.
        t = parser_mod.Theme(
            name="Theme 1: X",
            evidence_strength="Strong",
            sources="1 source",
            synthesis_text="y",
        )
        t.toulmin_claims.append(
            parser_mod.ToulminClaim(
                claim_id="Theme 1.C1",
                claim="C",
                data=["S1"],
                warrant="W",
                backing="B",
                qualifier="Q",
                rebuttal="R",
                loveliness=parser_mod.LovelinessScore(
                    scope="M", mechanism="M", unification="M", simplicity="M"
                ),
            )
        )
        report.themes.append(t)
        report.knowledge_gaps = ["gap1"]
        rendered = _render_report(report)
        re_parsed = parser_mod.parse_synthesis_markdown(rendered)
        self.assertTrue(
            re_parsed.is_v37_compliant,
            "minimal valid v3.7+ report should be is_v37_compliant=True"
        )
        # The v3.7+ compliance check is the contract assertion; the
        # presence of unrelated parser warnings (e.g., a missing
        # Contradictions section) is not a contract violation and is
        # tested elsewhere. Filter to just the "missing Toulmin
        # component" warnings that would indicate a real v3.7+
        # regression.
        contract_warnings = [
            w for w in re_parsed.warnings
            if "missing Toulmin" in w or "missing Loveliness" in w
        ]
        self.assertEqual(
            contract_warnings, [],
            f"unexpected v3.7+ contract warnings: {contract_warnings}"
        )


class TestValidatorAcceptsRoundTrip(unittest.TestCase):
    """A round-tripped report should pass the validator. The
    integration test in TestEndToEndRoundTrip covers the same
    assertion, but this class isolates the validator step from the
    parser step so a parser regression is distinguishable from a
    validator regression."""

    def test_round_tripped_report_passes_validator(self):
        report = _build_report()
        rendered = _render_report(report)
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "report.md"
            out_path.write_text(rendered, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(out_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[OK]", result.stdout)


if __name__ == "__main__":
    unittest.main()
