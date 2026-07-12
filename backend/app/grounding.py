"""
CLAIM-GROUNDING ENGINE — the layer that catches a *perfect* deepfake.

The argument, in one sentence:

    A pixel-level detector asks "was this video generated?" — a question that gets
    harder every six months. Claim-Grounding asks "was this buyback actually
    filed?" — a question that does not get harder at all.

If a piece of content asserts a price-sensitive corporate fact (buyback, dividend,
merger, bonus issue, results, open offer) and there is NO corresponding SEALED
filing in the transparency log, we escalate — regardless of what the deepfake
model said. The lie has no filing behind it.

This is why PRAMAAN survives the next generation of generative models and a
detector-only approach does not.

PROTOTYPE SCOPE: claims are extracted with patterns against a seeded corpus of
sealed filings. Production replaces the extractor with NER + relation extraction
over the live exchange corporate-announcements feed. Say this out loud in the
demo — it is a legitimate prototype simplification, and pretending otherwise is
how you lose a jury.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .merkle import TransparencyLog


# Price-sensitive events. If content claims one of these, it must be backed.
# EXTRACTION patterns are strict — we do not want to raise an ungrounded-claim
# alarm on a passing mention.
CLAIM_PATTERNS: dict[str, re.Pattern[str]] = {
    "buyback": re.compile(r"\bbuy[\s-]?back\b", re.I),
    "dividend": re.compile(r"\bdividend\b", re.I),
    "bonus_issue": re.compile(r"\bbonus\s+(issue|share)", re.I),
    "stock_split": re.compile(r"\b(stock|share)\s+split\b", re.I),
    "merger": re.compile(r"\b(merger|acquisition|amalgamation|takeover)\b", re.I),
    "open_offer": re.compile(r"\bopen\s+offer\b", re.I),
    "results": re.compile(r"\b(quarterly|annual)\s+results?\b", re.I),
    "delisting": re.compile(r"\bdelisting\b", re.I),
}

# MATCHING patterns are permissive. A real filing may be titled "Q1 results" or
# "Intimation of Board Meeting", and we must not call a genuine corporate action
# ungrounded just because the filing's wording differs from the claim's. The
# asymmetry is deliberate: be strict about what counts as a claim, generous about
# what counts as backing it. False "ungrounded" alarms are the expensive error here.
FILING_MATCH_PATTERNS: dict[str, re.Pattern[str]] = {
    "buyback": re.compile(r"\bbuy[\s-]?back\b", re.I),
    "dividend": re.compile(r"\bdividend\b", re.I),
    "bonus_issue": re.compile(r"\bbonus\b", re.I),
    "stock_split": re.compile(r"\bsplit\b", re.I),
    "merger": re.compile(r"\b(merger|acquisition|amalgamation|takeover|scheme\s+of\s+arrangement)\b", re.I),
    "open_offer": re.compile(r"\bopen\s+offer\b", re.I),
    "results": re.compile(r"\b(results?|board\s+meeting)\b", re.I),
    "delisting": re.compile(r"\bdelisting\b", re.I),
}

# Seed universe. Production pulls the full listed-company master from the exchanges.
COMPANY_PATTERNS: dict[str, re.Pattern[str]] = {
    "RELIANCE": re.compile(r"\breliance\b", re.I),
    "TCS": re.compile(r"\b(tcs|tata\s+consultancy)\b", re.I),
    "INFOSYS": re.compile(r"\binfosys\b", re.I),
    "HDFCBANK": re.compile(r"\bhdfc\s*bank\b", re.I),
    "ICICIBANK": re.compile(r"\bicici\s*bank\b", re.I),
}


@dataclass(frozen=True)
class GroundingFinding:
    company: str
    claim: str
    grounded: bool
    risk: float
    detail: str


def extract_claims(text: str) -> list[tuple[str, str]]:
    """Return (company, claim_type) pairs asserted by the content."""
    companies = [c for c, pat in COMPANY_PATTERNS.items() if pat.search(text)]
    claims = [k for k, pat in CLAIM_PATTERNS.items() if pat.search(text)]
    return [(c, k) for c in companies for k in claims]


def ground_claims(text: str, log: TransparencyLog) -> tuple[float, list[GroundingFinding]]:
    """
    For each price-sensitive claim, look for a sealed filing that backs it.

    Absence of a backing filing is the signal. This is the same
    "absence of proof is proof of absence" logic as the seal check, applied one
    level up — at the level of the *claim* rather than the *artefact*.
    """
    pairs = extract_claims(text)
    if not pairs:
        return 0.0, []

    findings: list[GroundingFinding] = []
    for company, claim in pairs:
        backed = any(
            entry.artefact_type in ("announcement", "circular")
            and company.lower() in entry.title.lower()
            and FILING_MATCH_PATTERNS[claim].search(entry.title)
            for entry in log.entries
        )
        if backed:
            findings.append(
                GroundingFinding(
                    company, claim, True, 0.0,
                    f"Claim of a {claim.replace('_', ' ')} by {company} IS backed by a sealed "
                    f"filing in the transparency log.",
                )
            )
        else:
            findings.append(
                GroundingFinding(
                    company, claim, False, 0.90,
                    f"Content asserts a {claim.replace('_', ' ')} by {company}, but NO corresponding "
                    f"sealed filing exists in the transparency log. A price-sensitive corporate action "
                    f"that was never filed did not happen — regardless of how convincing the media is.",
                )
            )

    return max(f.risk for f in findings), findings
