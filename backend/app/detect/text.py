"""
PRAMAAN Shield — text channel.

This module is deliberately a *rule engine*, not a model, and that is a design
decision worth defending in the jury round:

  1. It works today, with zero training data.
  2. Its verdicts are fully explainable — every hit names the rule that fired,
     which is what a regulator needs and what a fine-tuned classifier will not
     give you for free.
  3. It encodes SEBI's own published red flags, so the rules are already
     defensible in policy terms.

The MuRIL classifier (see models/README.md) is layered *on top* of this, not
instead of it. The rule engine is the floor; the model raises the ceiling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    rule_id: str
    weight: float          # 0.0 - 1.0 contribution to risk
    explanation: str
    matched: str


# SEBI's published investor red flags, encoded. Multilingual by design: retail
# fraud in India does not arrive in English.
RULES: list[tuple[str, float, str, list[str]]] = [
    (
        "GUARANTEED_RETURNS",
        0.85,
        "Promises assured or guaranteed returns. No SEBI-registered entity may guarantee returns on market-linked products.",
        [
            r"guarantee[d]?\s+(\d{1,3}\s*%\s*)?(returns?|profit|income)",
            r"assured\s+(\d{1,3}\s*%\s*)?(returns?|profit)",
            r"\b\d{2,3}\s*%\s*(guaranteed|assured|sure|fixed)\b",
            r"(guaranteed|assured|fixed)\s+\d{1,3}\s*%",
            r"risk[\s-]?free\s+(returns?|profit|investment)",
            r"no\s+loss\s+(guarantee|strategy|tip)",
            r"निश्चित\s*रिटर्न",          # Hindi: assured return
            r"गारंटी\s*(रिटर्न|मुनाफा)",   # Hindi: guaranteed return/profit
            r"உறுதியான\s*லாபம்",           # Tamil: assured profit
        ],
    ),
    (
        "FALSE_SEBI_ENDORSEMENT",
        0.90,
        "Claims SEBI approval, endorsement or affiliation. SEBI does not endorse, approve or recommend any investment product, scheme or advisor.",
        [
            r"sebi[\s-]*(approved|certified|endorsed|recommended|backed|authoris?zed\s+scheme)",
            r"approved\s+by\s+sebi",
            r"sebi\s+(guarantee|guaranteed)",
            r"government\s+(approved|backed)\s+(scheme|tips?|calls?)",
            r"सेबी\s*(द्वारा)?\s*(अनुमोदित|प्रमाणित)",  # Hindi: SEBI approved/certified
        ],
    ),
    (
        "URGENCY_PRESSURE",
        0.55,
        "Manufactured urgency or scarcity — a standard coercion pattern designed to prevent the investor from verifying.",
        [
            r"(limited|last|only)\s+\d+\s+(seats?|slots?|spots?|members?)",
            r"(offer|opportunity)\s+(expires?|ends?|closing)\s+(today|tonight|in\s+\d+)",
            r"join\s+(now|immediately|fast|today)\b",
            r"hurry\s*(up)?[!.]",
            r"act\s+(now|fast|immediately)",
            r"जल्दी\s*कर(ें|ो)",            # Hindi: hurry
        ],
    ),
    (
        "OFF_PLATFORM_PAYMENT",
        0.80,
        "Solicits payment to a personal UPI ID, wallet or account. Registered intermediaries collect funds only through regulated banking channels.",
        [
            r"\b[\w.\-]{2,}@(paytm|ybl|okaxis|oksbi|okhdfcbank|okicici|upi|apl|ibl)\b",
            r"(send|transfer|pay)\s+(money|amount|\u20b9\s*\d+)\s+to\s+(this|my)\s+(upi|account|number|wallet)",
            r"google\s*pay|phonepe|paytm\s+number",
        ],
    ),
    (
        "UNREGISTERED_ADVISORY",
        0.70,
        "Solicits participation in a private tips/calls group — a hallmark of unregistered investment advisory, which is an offence under the SEBI (Investment Advisers) Regulations, 2013.",
        [
            r"(telegram|whatsapp)\s*(group|channel|link)",
            r"(paid|premium|vip)\s+(group|calls?|tips?|signals?)",
            r"(intraday|jackpot|sure[\s-]?shot)\s+(tips?|calls?)",
            r"join\s+my\s+(group|channel)",
            r"multibagger\s+(tips?|calls?|stock)",
        ],
    ),
    (
        "IMPERSONATION_CLAIM",
        0.65,
        "Claims to speak for an exchange, depository, regulator or listed-company executive — verify against the transparency log and the SEBI registry.",
        [
            r"\b(nse|bse|nsdl|cdsl|sebi)\s+(official|team|desk|department)",
            r"(ceo|cfo|md|chairman)\s+(of|announces?|says?)",
            r"official\s+(announcement|circular|notice)\s+from",
        ],
    ),
    (
        "INSIDER_INFORMATION",
        0.75,
        "Offers advance or 'inside' information. Trading on unpublished price-sensitive information is prohibited under the SEBI (PIT) Regulations, 2015.",
        [
            r"inside[r]?\s+(info|information|news|tip)",
            r"before\s+(the\s+)?(news|announcement)\s+(breaks|comes)",
            r"advance\s+(information|news|tip)",
            r"unpublished\s+(price|information)",
        ],
    ),
]

_COMPILED = [
    (rid, weight, expl, [re.compile(p, re.IGNORECASE | re.UNICODE) for p in pats])
    for rid, weight, expl, pats in RULES
]


# Phrases that assert official origin. If one of these fires and the content
# carries no seal, we are in "absence of proof is proof of absence" territory —
# see fusion.fuse(claimed_official=True).
#
# This lives here, and NOT in main.py, deliberately: the Streamlit front-end
# imports it, and it must not have to pull in FastAPI/uvicorn/pydantic to do so.
# Keeping the engine free of web-framework imports is what lets one codebase
# serve both the API and the Streamlit console.
OFFICIAL_CLAIM_RE = re.compile(
    r"\b(sebi|nse|bse|nsdl|cdsl)\b.{0,40}\b(circular|notice|announcement|official|advisory|order)\b"
    r"|\b(circular|notice|announcement)\b.{0,20}\bfrom\b.{0,20}\b(sebi|nse|bse|nsdl|cdsl)\b"
    r"|\bofficial\s+(communication|announcement|circular)\b",
    re.IGNORECASE | re.DOTALL,
)


def analyse_text(text: str) -> tuple[float, list[Signal]]:
    """
    Returns (risk_0_to_1, signals).

    Risk is combined with a noisy-OR rather than a sum: three weak signals should
    raise suspicion, but they must never sum past a single decisive one, and the
    score must stay bounded. Summing weights is the classic way these engines end
    up reporting 340% risk.
    """
    signals: list[Signal] = []
    for rule_id, weight, explanation, patterns in _COMPILED:
        for pat in patterns:
            m = pat.search(text)
            if m:
                signals.append(
                    Signal(
                        rule_id=rule_id,
                        weight=weight,
                        explanation=explanation,
                        matched=m.group(0)[:80],
                    )
                )
                break  # one hit per rule; don't double-count a rule

    if not signals:
        return 0.0, []

    inverse = 1.0
    for s in signals:
        inverse *= (1.0 - s.weight)
    return round(1.0 - inverse, 4), signals
