"""Markdown parser for `synthesis_agent` output.

Parses the Markdown format defined in
`deep-research/agents/synthesis_agent.md` "Output Format" into a
structured `SynthesisReport` Python object. The parser is **non-strict**:
missing Toulmin components produce a `ToulminClaim` with the missing
field set to `None` and a `warnings` list carries the diagnostic. The
parser does NOT raise on incomplete output, because real LLM synthesis
output is rarely perfect and a downstream consumer must be able to
process partial outputs (e.g., for re-generation).

**v3.7+ Creative Process Discipline.** When the synthesis output
contains the v3.7+ Toulmin blocks and Loveliness scores, the parser
populates `toulmin_claims` and `loveliness_scores` on each `Theme`.
When the output is pre-v3.7+ (no Toulmin blocks), those lists are
empty. Backward compatible.

**Falsifiability discipline (inherited from
`check_synthesis_toulmin_lipton.py`).** Detection of negation /
weakening is done on a per-line basis against a fixed pattern set, so
the parser behavior is grep-detectable and reproducible.

Use:

    from scripts._synthesis_markdown_parser import parse_synthesis_markdown

    md = open("synthesis_report.md").read()
    report = parse_synthesis_markdown(md)
    for theme in report.themes:
        for claim in theme.toulmin_claims:
            print(claim.claim_id, claim.claim, claim.loveliness_score)
"""

import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

# --- Result types ---------------------------------------------------------

LovelinessMark = Literal["W", "M", "S"]


@dataclass
class LovelinessScore:
    """Lipton's 4-dimension explanatory-virtue score."""

    scope: LovelinessMark
    mechanism: LovelinessMark
    unification: LovelinessMark
    simplicity: LovelinessMark

    def as_tuple(self) -> Tuple[LovelinessMark, LovelinessMark, LovelinessMark, LovelinessMark]:
        return (self.scope, self.mechanism, self.unification, self.simplicity)

    @property
    def weak_count(self) -> int:
        return sum(1 for v in self.as_tuple() if v == "W")

    def is_below_threshold(self) -> bool:
        """Per synthesis_agent.md: 3 or 4 W's is below threshold."""
        return self.weak_count >= 3


@dataclass
class ToulminClaim:
    """Toulmin's 6-component claim structure. Any field may be None
    if the corresponding `**Component**:` line was not present in the
    source block; the `warnings` list on the containing Theme carries
    the diagnostic."""

    claim_id: str
    claim: str
    data: List[str] = field(default_factory=list)
    warrant: Optional[str] = None
    backing: Optional[str] = None
    qualifier: Optional[str] = None
    rebuttal: Optional[str] = None
    loveliness: Optional[LovelinessScore] = None


@dataclass
class RejectedCandidate:
    """An Insight-stage candidate rejected at Evaluation stage."""

    claim_summary: str
    rejection_reason: str
    loveliness: Optional[LovelinessScore] = None


@dataclass
class Theme:
    name: str
    evidence_strength: Optional[str] = None  # "Strong" / "Moderate" / "Emerging"
    sources: Optional[str] = None  # "[X] sources, Levels [range]"
    synthesis_text: str = ""
    toulmin_claims: List[ToulminClaim] = field(default_factory=list)
    loveliness_scores: List[LovelinessScore] = field(default_factory=list)
    rejected_candidates: List[RejectedCandidate] = field(default_factory=list)


@dataclass
class SynthesisReport:
    themes: List[Theme] = field(default_factory=list)
    contradictions: List[dict] = field(default_factory=list)
    knowledge_gaps: List[str] = field(default_factory=list)
    evidence_convergence_map: Optional[str] = None
    theoretical_integration: Optional[str] = None
    synthesis_limitations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_v37_compliant(self) -> bool:
        """True iff at least one theme has Toulmin claims with Loveliness scores."""
        return any(
            t.toulmin_claims and any(c.loveliness is not None for c in t.toulmin_claims)
            for t in self.themes
        )


# --- Internal regexes -----------------------------------------------------

# Theme heading: "#### Theme 1: ..." through "#### Theme N: ..."
_THEME_RE = re.compile(r"^#{2,6}\s+Theme\s+(\d+)\s*:\s*(.+?)\s*$", re.MULTILINE)

# Evidence Strength: "**Evidence Strength**: Strong"
_EVIDENCE_STRENGTH_RE = re.compile(
    r"\*\*Evidence Strength\*\*\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE
)

# Sources: "**Sources**: [X] sources, Levels [range]"
_SOURCES_RE = re.compile(
    r"\*\*Sources\*\*\s*:\s*(.+?)(?:\n|$)", re.IGNORECASE
)

# Synthesis: "**Synthesis**: ..." (multi-line until next "**" or ">" or end)
_SYNTHESIS_RE = re.compile(
    r"\*\*Synthesis\*\*\s*:\s*(.+?)(?=\n\s*\*\*|\n\s*>|\n\s*#|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Toulmin block: lines starting with "> **Component** (claim_id): ..." or "> **Component**: ..."
_TOULMIN_LINE_RE = re.compile(
    r"^>\s*\*\*(Claim|Data|Warrant|Backing|Qualifier|Rebuttal|Loveliness)\*\*"
    r"(?:\s*\(([^)]+)\))?\s*:\s*(.*)$"
)

# Loveliness value line: "**Loveliness**: (scope=X, mechanism=Y, unification=Z, simplicity=W)"
# Optionally prefixed with blockquote marker "> ".
_LOVELINESS_RE = re.compile(
    r"^>\s*\*\*Loveliness\*\*\s*:\s*\(\s*"
    r"scope\s*=\s*([WMS])"
    r"\s*,\s*mechanism\s*=\s*([WMS])"
    r"\s*,\s*unification\s*=\s*([WMS])"
    r"\s*,\s*simplicity\s*=\s*([WMS])"
    r"\s*\)\s*$",
    re.IGNORECASE,
)
# Helper-friendly form without the blockquote prefix. Used by the
# public `parse_loveliness_score` helper so callers can pass either the
# raw "> " line from a blockquote or a bare "**Loveliness**" line.
_LOVELINESS_HELPER_RE = re.compile(
    r"\*\*Loveliness\*\*\s*:\s*\(\s*"
    r"scope\s*=\s*([WMS])"
    r"\s*,\s*mechanism\s*=\s*([WMS])"
    r"\s*,\s*unification\s*=\s*([WMS])"
    r"\s*,\s*simplicity\s*=\s*([WMS])"
    r"\s*\)\s*$",
    re.IGNORECASE,
)

# Sections
_CONTRADICTIONS_RE = re.compile(
    r"^###\s+Contradictions\s*&\s*Resolutions\s*$(.*?)(?=^###\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_KNOWLEDGE_GAPS_RE = re.compile(
    r"^###\s+Knowledge\s+Gaps\s*$(.*?)(?=^###\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_EVIDENCE_CONVERGENCE_RE = re.compile(
    r"^###\s+Evidence\s+Convergence\s+Map\s*$(.*?)(?=^###\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_THEORETICAL_RE = re.compile(
    r"^###\s+Theoretical\s+Integration\s*$(.*?)(?=^###\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_LIMITATIONS_RE = re.compile(
    r"^###\s+Synthesis\s+Limitations\s*$(.*?)(?=^###\s|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Rejected candidate: a bullet that looks like
#   - [rejected at score (scope=W, mechanism=W, unification=M, simplicity=M)]: <text>
_REJECTED_RE = re.compile(
    r"^-\s*\[rejected(?:\s+at\s+score\s+\([^)]+\))?\]\s*:\s*(.+?)(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)

# Knowledge gap list items: "1. ..." or "- ..."
_KGAP_ITEM_RE = re.compile(r"^\s*(?:\d+\.|-)\s+(.+?)$", re.MULTILINE)


# --- Public API -----------------------------------------------------------


def parse_synthesis_markdown(md: str) -> SynthesisReport:
    """Parse a synthesis-agent Markdown output into a SynthesisReport."""
    report = SynthesisReport()
    report.themes = _parse_themes(md, report)
    report.contradictions = _parse_contradictions(md, report)
    report.knowledge_gaps = _parse_knowledge_gaps(md, report)
    report.evidence_convergence_map = _parse_section(md, _EVIDENCE_CONVERGENCE_RE, report)
    report.theoretical_integration = _parse_section(md, _THEORETICAL_RE, report)
    report.synthesis_limitations = _parse_limitations(md, report)
    return report


def parse_loveliness_score(line: str) -> Optional[LovelinessScore]:
    """Parse a single Loveliness line. Returns None on mismatch.

    Accepts both the on-the-wire form
    `> **Loveliness**: (scope=X, mechanism=Y, unification=Z, simplicity=W)`
    and the bare `**Loveliness**: (...)` form. Whitespace and quote
    prefixes are tolerated.
    """
    m = _LOVELINESS_RE.match(line.strip()) or _LOVELINESS_HELPER_RE.search(line)
    if not m:
        return None
    scope, mechanism, unification, simplicity = m.groups()
    return LovelinessScore(
        scope=scope.upper(),
        mechanism=mechanism.upper(),
        unification=unification.upper(),
        simplicity=simplicity.upper(),
    )


# --- Internals ------------------------------------------------------------


def _parse_themes(md: str, report: SynthesisReport) -> List[Theme]:
    themes: List[Theme] = []
    matches = list(_THEME_RE.finditer(md))
    if not matches:
        report.warnings.append("no themes found (no `#### Theme N: ...` headings)")
        return themes

    for i, m in enumerate(matches):
        theme_num = m.group(1)
        theme_name = m.group(2).strip()
        # Theme body: from end of this heading to start of next heading
        # (any level) or end of file.
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        body = md[body_start:body_end]

        theme = Theme(name=f"Theme {theme_num}: {theme_name}")
        es = _EVIDENCE_STRENGTH_RE.search(body)
        if es:
            theme.evidence_strength = es.group(1).strip()
        else:
            report.warnings.append(
                f"theme {theme_num}: missing **Evidence Strength** line"
            )
        sr = _SOURCES_RE.search(body)
        if sr:
            theme.sources = sr.group(1).strip()
        else:
            report.warnings.append(
                f"theme {theme_num}: missing **Sources** line"
            )
        sx = _SYNTHESIS_RE.search(body)
        if sx:
            theme.synthesis_text = sx.group(1).strip()
        else:
            report.warnings.append(
                f"theme {theme_num}: missing **Synthesis** line"
            )

        # Toulmin blocks: a sequence of "> **Component**: ..." lines
        toulmin_blocks = _extract_toulmin_blocks(body, report, theme_num)
        theme.toulmin_claims = [tb["claim"] for tb in toulmin_blocks]
        theme.loveliness_scores = [
            tb["claim"].loveliness
            for tb in toulmin_blocks
            if tb["claim"].loveliness is not None
        ]
        # Rejected candidates: bullets with the rejected marker
        for rm in _REJECTED_RE.finditer(body):
            text = rm.group(1).strip()
            theme.rejected_candidates.append(
                RejectedCandidate(claim_summary=text, rejection_reason="")
            )
        themes.append(theme)
    return themes


def _extract_toulmin_blocks(
    body: str, report: SynthesisReport, theme_num: str
) -> List[dict]:
    """Find all Toulmin blocks (claim_id, claim, data, warrant, backing,
    qualifier, rebuttal, loveliness) in the theme body.

    A Toulmin block is a sequence of `> ` blockquote lines that starts
    with a `> **Claim** (...)` line and ends when we hit a non-blockquote
    line OR a new `> ` line whose stripped form does NOT look like a
    component continuation. Continuation lines (e.g., a multi-line Claim
    whose subsequent lines don't begin with `**Component**:`) are
    appended to the *most recent* component's value as a space-joined
    line.
    """
    blocks: List[dict] = []
    current: Optional[dict] = None
    # Name of the component currently being assembled (e.g., "claim",
    # "warrant"). Continuation lines append to this component.
    active_component: Optional[str] = None

    def _flush():
        nonlocal current
        if current is not None:
            blocks.append(current)
            current = None

    for line in body.splitlines():
        # Outside a blockquote: any non-empty line ends the current block.
        if not line.lstrip().startswith(">"):
            if line.strip():
                _flush()
                active_component = None
            else:
                # Blank line — keep the block open (parser tolerates
                # blank lines between components).
                continue
            continue

        # Inside a blockquote.
        m = _TOULMIN_LINE_RE.match(line)
        if m:
            component, claim_id, value = m.group(1), m.group(2), m.group(3).strip()
            if component == "Claim":
                _flush()
                cid = claim_id or f"Theme{theme_num}.C{len(blocks) + 1}"
                current = {
                    "claim_id": cid,
                    "claim": ToulminClaim(claim_id=cid, claim=value),
                }
                active_component = "claim"
            elif current is None:
                report.warnings.append(
                    f"theme {theme_num}: stray **Component** line outside a Claim block"
                )
                active_component = None
                continue
            elif component == "Loveliness":
                score = parse_loveliness_score(line)
                if score is None:
                    report.warnings.append(
                        f"theme {theme_num}: malformed Loveliness line: {line!r}"
                    )
                else:
                    current["claim"].loveliness = score
                active_component = None
            elif component == "Data":
                current["claim"].data = [
                    v.strip() for v in value.split(";") if v.strip()
                ]
                active_component = None
            else:
                setattr(current["claim"], component.lower(), value)
                active_component = component.lower()
        else:
            # Continuation line: blockquote text that doesn't start a new
            # component. Append to the active component if any; otherwise
            # ignore.
            if current is not None and active_component is not None:
                # Strip the leading "> " or "> " plus whitespace.
                cont = re.sub(r"^>\s?", "", line).strip()
                if not cont:
                    continue
                if active_component == "claim":
                    existing = current["claim"].claim or ""
                    current["claim"].claim = (existing + " " + cont).strip()
                elif active_component == "data":
                    # Continuation of the data list: append as a new item.
                    current["claim"].data.append(cont)
                else:
                    existing = getattr(current["claim"], active_component) or ""
                    setattr(
                        current["claim"],
                        active_component,
                        (existing + " " + cont).strip(),
                    )
            # else: stray blockquote with no current claim — ignore silently.
    _flush()

    # Verify each block has all 6 components and a Loveliness score.
    for b in blocks:
        c: ToulminClaim = b["claim"]
        missing = [
            f
            for f in ("warrant", "backing", "qualifier", "rebuttal")
            if getattr(c, f) is None
        ]
        if missing:
            report.warnings.append(
                f"{c.claim_id}: missing Toulmin components: {missing}"
            )
        if c.loveliness is None:
            report.warnings.append(f"{c.claim_id}: missing Loveliness score")
    return blocks


def _parse_contradictions(md: str, report: SynthesisReport) -> List[dict]:
    m = _CONTRADICTIONS_RE.search(md)
    if not m:
        report.warnings.append("no `### Contradictions & Resolutions` section")
        return []
    body = m.group(1).strip()
    # The body is a Markdown table; we return the raw lines for now and
    # let downstream consumers parse the table. The parser does not
    # try to split table cells because the field could contain pipes
    # in cited text.
    return [{"raw": body}]


def _parse_knowledge_gaps(md: str, report: SynthesisReport) -> List[str]:
    m = _KNOWLEDGE_GAPS_RE.search(md)
    if not m:
        report.warnings.append("no `### Knowledge Gaps` section")
        return []
    body = m.group(1)
    return [match.group(1).strip() for match in _KGAP_ITEM_RE.finditer(body)]


def _parse_section(
    md: str, regex: re.Pattern, report: SynthesisReport
) -> Optional[str]:
    m = regex.search(md)
    if not m:
        return None
    return m.group(1).strip()


def _parse_limitations(md: str, report: SynthesisReport) -> List[str]:
    raw = _parse_section(md, _LIMITATIONS_RE, report)
    if not raw:
        return []
    return [match.group(1).strip() for match in _KGAP_ITEM_RE.finditer(raw)]
