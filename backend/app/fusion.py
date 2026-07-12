"""
Fusion — turns a pile of signals into one explainable verdict.

Design rule, and it is not negotiable: NO VERDICT WITHOUT A REASON. A regulator
cannot act on a number, and a retail investor will not trust one. Every response
from this module carries the list of signals that produced it, in plain language.

Production swaps the noisy-OR below for a calibrated gradient-boosted meta-model
with SHAP attributions. The *interface* stays identical — reasons in, reasons
out — which is the whole point of building it this way now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    GREEN = "GREEN"    # cryptographically verified
    AMBER = "AMBER"    # unverified — no seal, no strong fraud signal
    RED = "RED"        # high risk


@dataclass
class Reason:
    code: str
    severity: str      # info | warning | critical
    message: str


@dataclass
class Assessment:
    verdict: Verdict
    trust_score: int               # 0-100. Higher = more trustworthy.
    headline: str
    reasons: list[Reason] = field(default_factory=list)
    sealed: bool = False
    seal_entry: dict | None = None
    latency_note: str = ""


def _score_from_risk(risk: float) -> int:
    return int(round((1.0 - max(0.0, min(1.0, risk))) * 100))


def fuse(
    *,
    risks: list[float],
    reasons: list[Reason],
    sealed: bool,
    seal_entry: dict | None = None,
    tampered: bool = False,
    claimed_official: bool = False,
) -> Assessment:
    # 1. Sealed and valid — terminate. No inference ran. This is the fast path.
    if sealed and not tampered:
        return Assessment(
            verdict=Verdict.GREEN,
            trust_score=100,
            headline="Verified. This communication is cryptographically sealed and present in the PRAMAAN transparency log.",
            reasons=reasons,
            sealed=True,
            seal_entry=seal_entry,
            latency_note="Resolved by seal check alone — no model inference required.",
        )

    # 2. Sealed but the bytes don't match — the highest-confidence verdict we have.
    if tampered:
        return Assessment(
            verdict=Verdict.RED,
            trust_score=0,
            headline="TAMPERED. This is a modified version of a genuine sealed communication.",
            reasons=reasons,
            sealed=False,
            latency_note="Resolved by hash mismatch against the transparency log.",
        )

    # 3. Claims to be official, carries no seal. Absence of proof is proof of absence.
    if claimed_official:
        reasons.insert(
            0,
            Reason(
                code="NOT_IN_LOG",
                severity="critical",
                message=(
                    "This content presents itself as an official communication, but it does not "
                    "appear in the PRAMAAN transparency log. Genuine communications from SEBI, the "
                    "exchanges, depositories and registered intermediaries are sealed at source. "
                    "It was never issued."
                ),
            ),
        )
        risks.append(0.93)

    # 4. Everything else: combine remaining signals with a bounded noisy-OR.
    inverse = 1.0
    for r in risks:
        inverse *= (1.0 - max(0.0, min(1.0, r)))
    risk = 1.0 - inverse
    score = _score_from_risk(risk)

    if risk >= 0.70:
        verdict = Verdict.RED
        headline = "High risk. Multiple fraud indicators detected. Do not act on this message."
    elif risk >= 0.30:
        verdict = Verdict.AMBER
        headline = "Unverified. This content carries no cryptographic seal and shows some risk indicators. Proceed with caution."
    else:
        verdict = Verdict.AMBER
        headline = "Unverified. No fraud indicators found, but this content is not sealed — its origin cannot be proven."

    return Assessment(
        verdict=verdict,
        trust_score=score,
        headline=headline,
        reasons=reasons,
        sealed=False,
        latency_note="Full multimodal analysis path.",
    )
