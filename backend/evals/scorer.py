import dataclasses
import re

# LLM prose renders dates and negative signs with typographic dash/minus characters
# (observed: U+2011 NON-BREAKING HYPHEN), not ASCII '-' - without normalizing these,
# negative z-scores lose their sign and dates like "2026‑08‑01" get mis-split into
# stray positive numbers (2026, 8, 1), both of which cause false "ungrounded" flags.
DASH_CHARS = "‐‑‒–—−"
MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
ISO_DATE_PATTERN = re.compile(rf"\d{{4}}[\-{DASH_CHARS}]\d{{2}}[\-{DASH_CHARS}]\d{{2}}")
PROSE_DATE_PATTERN = re.compile(rf"(?:{MONTH_NAMES})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s*(?:\d{{4}})?")
NUMBER_PATTERN = re.compile(rf"[\-{DASH_CHARS}]?\d[\d,]*\.?\d*")


def score_tool_calls(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return not actual
    return set(expected).issubset(set(actual))


def extract_numbers(text: str) -> set[float]:
    text_without_dates = ISO_DATE_PATTERN.sub(" ", text)
    text_without_dates = PROSE_DATE_PATTERN.sub(" ", text_without_dates)
    numbers = set()
    for match in NUMBER_PATTERN.findall(text_without_dates):
        cleaned = match.replace(",", "")
        for dash in DASH_CHARS:
            cleaned = cleaned.replace(dash, "-")
        try:
            numbers.add(float(cleaned))
        except ValueError:
            continue
    return numbers


@dataclasses.dataclass
class GroundingResult:
    is_grounded: bool
    ungrounded_numbers: list[float]


def check_grounding(reply: str, evidence: str, tolerance: float = 0.5) -> GroundingResult:
    """Heuristic, rule-based grounding check: every number stated in the reply must appear
    (within tolerance) somewhere in the evidence text (system prompt + tool results + the
    original question) - matched either on exact sign (e.g. "-2.21") or magnitude only
    (e.g. "2.2 SD below baseline" for a -2.21 z-score, a common phrasing this model uses).

    Known limitations, deliberately not chased further given this is a rule-based checker,
    not an LLM judge: incidental numbers (list markers, a bare year, a duration mentioned in
    the question) can still be flagged as false positives; and a number the model correctly
    *derives* by doing arithmetic on real retrieved data (e.g. summing a tool's raw daily
    series) will be flagged too, since it doesn't literally appear anywhere in the evidence -
    that's a different, more interesting gap (can't yet tell "computed correctly" from
    "fabricated") than true hallucination, and is worth a human glance at the flagged report
    rather than blind trust in the aggregate score either way.
    """
    reply_numbers = extract_numbers(reply)
    evidence_numbers = extract_numbers(evidence)

    def _is_grounded(n: float) -> bool:
        return any(abs(n - e) <= tolerance or abs(abs(n) - abs(e)) <= tolerance for e in evidence_numbers)

    ungrounded = sorted(n for n in reply_numbers if not _is_grounded(n))
    return GroundingResult(is_grounded=len(ungrounded) == 0, ungrounded_numbers=ungrounded)
