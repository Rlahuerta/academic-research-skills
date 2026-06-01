"""Unit tests for `scripts/_synthesis_markdown_parser.py`.

Patterned after `test__synthesis_markdown_parser.py` is *not* an
existing test (this is the first one) — but follows the in-process
unittest pattern used in `test_check_synthesis_toulmin_lipton.py` for
the helper-function tests.

Covers:
- Positive: a canonical v3.7+ synthesis output is fully parsed.
- Negative: missing Toulmin components produce warnings, not crashes.
- Backward compat: a pre-v3.7+ synthesis output is parsed with empty
  `toulmin_claims` and `loveliness_scores` lists.
- Loveliness: malformed Loveliness lines are reported.
- Round-trip: a `SynthesisReport` built by the test can be serialized
  back to a Markdown form (a stub renderer) and re-parsed without
  information loss.

The parser is **non-strict** by design — incomplete outputs are
recoverable, with diagnostics in `report.warnings`. The tests assert
both the recovered structure AND the warnings.
"""

from __future__ import annotations

import re
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PARSER = REPO_ROOT / "scripts" / "_synthesis_markdown_parser.py"

# A canonical v3.7+ synthesis output fixture. Mirrors the format
# described in `deep-research/agents/synthesis_agent.md` "Output Format".
V37_FIXTURE = textwrap.dedent("""\
    # Synthesis Report

    ## Literature Matrix
    [matrix table — omitted for brevity]

    ## Key Themes

    #### Theme 1: Immediacy of feedback as the active mechanism
    **Evidence Strength**: Strong
    **Sources**: 5 sources, Levels I-III
    **Synthesis**: Three converging evidence streams establish that
    feedback latency, not feedback volume, is the key variable. The
    boundary condition identified by the contradicted study suggests a
    population-level moderation effect.

    > **Claim** (Theme 1.C1): Feedback latency, not volume, is the
    > primary mechanism by which AI-assisted assessment improves
    > learning outcomes.
    > **Data**: Author1 (2023, Level I) — finding; Author2 (2024, Level II) — finding; Author4 (2024, Level I) — finding
    > **Warrant**: Converging evidence across three independent
    > operationalizations of latency establishes mechanism Y.
    > **Backing**: Hattie's (2009) feedback framework (theoretical).
    > **Qualifier**: In populations X, Y, Z within the methodological
    > constraints of the included studies.
    > **Rebuttal**: Author3 (2022) for the population-B counterexample;
    > this reverses the claim when Z is the moderating variable.
    > **Loveliness**: (scope=M, mechanism=S, unification=W, simplicity=M)

    > **Claim** (Theme 1.C2): The latency effect is bounded by an
    > upper threshold of about 24 hours.
    > **Data**: Author2 (2024, Level II) — finding; Author4 (2024, Level I) — finding
    > **Warrant**: Dose-response curve from two converging RCTs.
    > **Backing**: Hattie & Timperley (2007) feedback timing model.
    > **Qualifier**: In higher-education STEM contexts.
    > **Rebuttal**: Author5 (2023) reports a higher threshold in
    > professional-development contexts.
    > **Loveliness**: (scope=S, mechanism=M, unification=M, simplicity=S)

    #### Theme 2: Transfer to non-STEM domains
    **Evidence Strength**: Moderate
    **Sources**: 3 sources, Levels II-IV
    **Synthesis**: Two studies [S02, S04] and one meta-analysis [S07]
    support transfer; one contradicted study [S09] shows the effect
    is weaker in non-STEM contexts.

    > **Claim** (Theme 2.C1): The latency effect generalizes to
    > non-STEM domains but with smaller effect sizes.
    > **Data**: Author2 (2024, Level II); Author6 (2023, Level III); Author7 (2024, Level IV)
    > **Warrant**: Effect-size meta-analysis across domains.
    > **Backing**: Bloom (1985) mastery-learning framework.
    > **Qualifier**: In higher-education non-STEM, 2018-2024.
    > **Rebuttal**: Author9 (2024) shows the effect reverses in
    > language-learning contexts.
    > **Loveliness**: (scope=S, mechanism=M, unification=M, simplicity=S)

    ### Contradictions & Resolutions

    | Claim A | Claim B | Resolution |
    |---------|---------|-----------|
    | Author2: latency drives effect | Author3: quality drives effect | Reconciled: quality modulates latency; in low-quality AI systems, latency does not compensate. |

    ### Knowledge Gaps
    1. No longitudinal studies (>1 year) in Taiwan context
    2. Limited data on AI assessment in laboratory courses

    ### Evidence Convergence Map
    Strong:      [==========] Theme 1 (7 sources, Levels I-III)
    Moderate:    [======    ] Theme 2 (4 sources, Levels III-V)
    Gap:         [          ] Theme 3 (0 sources)

    ### Theoretical Integration
    Findings connect to Hattie's (2009) feedback framework, Bloom's
    (1985) mastery-learning model, and the more recent ICALM
    (2023) AI-pedagogy framework.

    ### Synthesis Limitations
    - Pre-2018 literature is under-represented
    - Most studies are US-based; generalizability beyond US is uncertain
    """)


# A pre-v3.7+ fixture (no Toulmin blocks, no Loveliness scores).
PRE_V37_FIXTURE = textwrap.dedent("""\
    # Synthesis Report

    ## Key Themes

    #### Theme 1: Feedback latency
    **Evidence Strength**: Strong
    **Sources**: 5 sources, Levels I-III
    **Synthesis**: Three converging studies establish feedback latency
    as the key variable. The contradicted study [S09] shows a
    moderation effect.

    #### Theme 2: Transfer
    **Evidence Strength**: Moderate
    **Sources**: 3 sources
    **Synthesis**: Two studies support transfer; one contradicted.

    ### Knowledge Gaps
    1. No longitudinal studies
    2. Limited data on laboratory courses
    """)


def _import_parser():
    """Load the parser module without registering it as `scripts.*`."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_synthesis_markdown_parser", PARSER
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestV37Canonical(unittest.TestCase):
    def test_canonical_v37_output_is_fully_parsed(self):
        mod = _import_parser()
        report = mod.parse_synthesis_markdown(V37_FIXTURE)
        # 2 themes
        self.assertEqual(len(report.themes), 2)
        # 3 Toulmin claims total (Theme 1 has 2, Theme 2 has 1)
        all_claims = [c for t in report.themes for c in t.toulmin_claims]
        self.assertEqual(len(all_claims), 3)
        # Each claim has all 6 components and a Loveliness score
        for c in all_claims:
            self.assertIsNotNone(c.claim)
            self.assertIsNotNone(c.warrant)
            self.assertIsNotNone(c.backing)
            self.assertIsNotNone(c.qualifier)
            self.assertIsNotNone(c.rebuttal)
            self.assertGreaterEqual(len(c.data), 1)
            self.assertIsNotNone(c.loveliness)
        # Loveliness 4-tuples are in {W, M, S}
        for c in all_claims:
            for v in c.loveliness.as_tuple():
                self.assertIn(v, ("W", "M", "S"))
        # is_v37_compliant
        self.assertTrue(report.is_v37_compliant)
        # Knowledge gaps: 2
        self.assertEqual(len(report.knowledge_gaps), 2)
        # Contradictions: 1 raw entry
        self.assertEqual(len(report.contradictions), 1)
        # No missing-component warnings
        missing_warnings = [w for w in report.warnings if "missing" in w]
        self.assertEqual(
            missing_warnings, [],
            f"unexpected missing-component warnings: {missing_warnings}"
        )

    def test_evidence_strength_and_sources(self):
        mod = _import_parser()
        report = mod.parse_synthesis_markdown(V37_FIXTURE)
        t1 = report.themes[0]
        self.assertEqual(t1.evidence_strength, "Strong")
        self.assertIn("5 sources", t1.sources)
        self.assertIn("Levels I-III", t1.sources)

    def test_loveliness_scores_match_per_claim(self):
        mod = _import_parser()
        report = mod.parse_synthesis_markdown(V37_FIXTURE)
        # Theme 1.C1: (M, S, W, M) — 1 weak, 3 non-weak → above threshold
        c1 = report.themes[0].toulmin_claims[0]
        self.assertEqual(c1.loveliness.as_tuple(), ("M", "S", "W", "M"))
        self.assertFalse(c1.loveliness.is_below_threshold())
        # Theme 1.C2: (S, M, M, S) — 0 weak → above threshold
        c2 = report.themes[0].toulmin_claims[1]
        self.assertEqual(c2.loveliness.as_tuple(), ("S", "M", "M", "S"))


class TestBackwardCompatibility(unittest.TestCase):
    def test_pre_v37_output_parses_with_empty_claim_lists(self):
        mod = _import_parser()
        report = mod.parse_synthesis_markdown(PRE_V37_FIXTURE)
        self.assertEqual(len(report.themes), 2)
        for t in report.themes:
            self.assertEqual(t.toulmin_claims, [])
            self.assertEqual(t.loveliness_scores, [])
        self.assertFalse(report.is_v37_compliant)
        # Still extracts the simple fields
        self.assertEqual(report.themes[0].evidence_strength, "Strong")
        self.assertEqual(len(report.knowledge_gaps), 2)


class TestNegativeCases(unittest.TestCase):
    def test_missing_qualifier_produces_warning(self):
        mod = _import_parser()
        # Take the canonical fixture and remove the Qualifier line from
        # Theme 1.C1.
        modified = V37_FIXTURE.replace(
            "> **Qualifier**: In populations X, Y, Z within the methodological\n"
            "> constraints of the included studies.\n",
            "",
        )
        report = mod.parse_synthesis_markdown(modified)
        c1 = report.themes[0].toulmin_claims[0]
        self.assertIsNone(c1.qualifier)
        self.assertTrue(
            any("qualifier" in w.lower() for w in report.warnings),
            f"expected qualifier warning; got: {report.warnings}"
        )

    def test_missing_rebuttal_produces_warning(self):
        mod = _import_parser()
        modified = V37_FIXTURE.replace(
            "> **Rebuttal**: Author3 (2022) for the population-B counterexample;\n"
            "> this reverses the claim when Z is the moderating variable.\n",
            "",
        )
        report = mod.parse_synthesis_markdown(modified)
        c1 = report.themes[0].toulmin_claims[0]
        self.assertIsNone(c1.rebuttal)
        self.assertTrue(
            any("rebuttal" in w.lower() for w in report.warnings),
        )

    def test_below_threshold_loveliness_detected(self):
        mod = _import_parser()
        # Theme 1.C1: change Loveliness to (W, W, W, S) — 3 W's, below
        # threshold.
        modified = re.sub(
            r"> \*\*Loveliness\*\*: \(scope=M, mechanism=S, unification=W, simplicity=M\)",
            "> **Loveliness**: (scope=W, mechanism=W, unification=W, simplicity=S)",
            V37_FIXTURE,
        )
        report = mod.parse_synthesis_markdown(modified)
        c1 = report.themes[0].toulmin_claims[0]
        self.assertEqual(c1.loveliness.as_tuple(), ("W", "W", "W", "S"))
        self.assertTrue(c1.loveliness.is_below_threshold())

    def test_malformed_loveliness_reported(self):
        mod = _import_parser()
        modified = V37_FIXTURE.replace(
            "> **Loveliness**: (scope=M, mechanism=S, unification=W, simplicity=M)",
            "> **Loveliness**: (scope=Z, mechanism=S, unification=W, simplicity=M)",
        )
        report = mod.parse_synthesis_markdown(modified)
        self.assertTrue(
            any("malformed loveliness" in w.lower() for w in report.warnings),
            f"expected malformed-Loveliness warning; got: {report.warnings}"
        )

    def test_no_themes_produces_warning(self):
        mod = _import_parser()
        report = mod.parse_synthesis_markdown("# A document with no themes\n")
        self.assertEqual(report.themes, [])
        self.assertTrue(
            any("no themes" in w for w in report.warnings)
        )

    def test_no_knowledge_gaps_section_produces_warning(self):
        mod = _import_parser()
        # A minimal but theme-bearing doc with no KGaps section.
        report = mod.parse_synthesis_markdown(
            "#### Theme 1: Foo\n**Evidence Strength**: Weak\n"
            "**Sources**: 1\n**Synthesis**: text\n"
        )
        self.assertEqual(report.knowledge_gaps, [])
        self.assertTrue(
            any("knowledge gaps" in w.lower() for w in report.warnings)
        )


class TestLovelinessHelper(unittest.TestCase):
    def test_parse_loveliness_score_valid(self):
        mod = _import_parser()
        score = mod.parse_loveliness_score(
            "**Loveliness**: (scope=M, mechanism=S, unification=W, simplicity=M)"
        )
        self.assertIsNotNone(score)
        self.assertEqual(score.as_tuple(), ("M", "S", "W", "M"))

    def test_parse_loveliness_score_with_quote_prefix(self):
        mod = _import_parser()
        # The actual on-the-wire form includes the leading "> " from the
        # blockquote. The parser strips it.
        score = mod.parse_loveliness_score(
            "> **Loveliness**: (scope=S, mechanism=M, unification=M, simplicity=S)"
        )
        self.assertIsNotNone(score)
        self.assertEqual(score.as_tuple(), ("S", "M", "M", "S"))

    def test_parse_loveliness_score_invalid_returns_none(self):
        mod = _import_parser()
        self.assertIsNone(
            mod.parse_loveliness_score("**Loveliness**: (scope=Z, ...)")
        )
        self.assertIsNone(mod.parse_loveliness_score("not a loveliness line"))


class TestRoundTrip(unittest.TestCase):
    """Build a SynthesisReport, render it back to Markdown with a stub
    renderer, and re-parse. The round-trip must be lossless on the
    structural fields (theme names, claim IDs, Toulmin component text,
    Loveliness 4-tuples)."""

    def test_round_trip_preserves_themes_and_claims(self):
        mod = _import_parser()
        # Parse the canonical fixture
        report = mod.parse_synthesis_markdown(V37_FIXTURE)
        # Render back with a minimal stub renderer (a few lines that
        # exercise the format the parser consumes).
        rendered = self._stub_render(report)
        # Re-parse
        re_parsed = mod.parse_synthesis_markdown(rendered)
        # Same number of themes, same claim IDs, same Loveliness tuples
        self.assertEqual(
            len(re_parsed.themes), len(report.themes),
            "theme count changed across round-trip"
        )
        for orig, new in zip(report.themes, re_parsed.themes):
            self.assertEqual(orig.name, new.name)
            self.assertEqual(len(orig.toulmin_claims), len(new.toulmin_claims))
            for oc, nc in zip(orig.toulmin_claims, new.toulmin_claims):
                self.assertEqual(oc.claim_id, nc.claim_id)
                self.assertEqual(oc.claim, nc.claim)
                self.assertEqual(
                    oc.loveliness.as_tuple() if oc.loveliness else None,
                    nc.loveliness.as_tuple() if nc.loveliness else None,
                )
                self.assertEqual(oc.warrant, nc.warrant)
                self.assertEqual(oc.backing, nc.backing)
                self.assertEqual(oc.qualifier, nc.qualifier)
                self.assertEqual(oc.rebuttal, nc.rebuttal)

    @staticmethod
    def _stub_render(report) -> str:
        """Render a SynthesisReport to the canonical Markdown form. The
        renderer is intentionally minimal: it exercises the format the
        parser consumes, not full Markdown fidelity."""
        out = ["# Synthesis Report\n", "## Key Themes\n"]
        for i, theme in enumerate(report.themes, 1):
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
                    out.append(
                        f"> **Data**: {'; '.join(claim.data)}"
                    )
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
        if report.knowledge_gaps:
            out.append("### Knowledge Gaps")
            for i, g in enumerate(report.knowledge_gaps, 1):
                out.append(f"{i}. {g}")
            out.append("")
        return "\n".join(out)


if __name__ == "__main__":
    unittest.main()
