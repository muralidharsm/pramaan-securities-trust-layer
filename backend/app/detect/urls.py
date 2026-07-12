"""
PRAMAAN Shield — URL channel.

Catches the impersonation domain before the investor clicks it. Three checks:

  1. Punycode / mixed-script — the Cyrillic-'e'-in-'sebi' class of attack.
  2. Typosquat distance — edit distance against the known-good domain list.
  3. Lookalike composition — 'sebi-india-verify.com' style domains that embed a
     trusted brand as a *label* rather than as the registrable domain.

Check 3 is the one that catches most real Indian securities-fraud domains, and
it is pure string logic — no model, no lookup, no latency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlparse


# The domains fraudsters impersonate. Extend from the SEBI intermediary registry.
PROTECTED_DOMAINS: dict[str, str] = {
    "sebi.gov.in": "Securities and Exchange Board of India",
    "nseindia.com": "National Stock Exchange of India",
    "bseindia.com": "BSE Limited",
    "nsdl.co.in": "National Securities Depository Limited",
    "cdslindia.com": "Central Depository Services (India) Limited",
    "scores.sebi.gov.in": "SEBI SCORES grievance portal",
}

PROTECTED_BRANDS = ("sebi", "nse", "bse", "nsdl", "cdsl", "scores")

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Characters that are visually confusable with ASCII in common fonts.
CONFUSABLES = set("асԁеһіјӏорԛѕтухуѵаеоху")  # Cyrillic lookalikes


@dataclass(frozen=True)
class UrlFinding:
    url: str
    domain: str
    risk: float
    reason: str


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text)


def _registrable(host: str) -> str:
    host = host.lower().lstrip("www.")
    return host


def analyse_url(url: str) -> UrlFinding:
    host = _registrable(urlparse(url).netloc or url)

    if host in PROTECTED_DOMAINS:
        return UrlFinding(url, host, 0.0, f"Known official domain of {PROTECTED_DOMAINS[host]}.")

    # 1. Punycode / mixed script
    if host.startswith("xn--") or any(ch in CONFUSABLES for ch in host):
        return UrlFinding(
            url, host, 0.95,
            "Domain uses non-ASCII or visually confusable characters — a homoglyph attack "
            "designed to look like an official domain in the address bar.",
        )

    # 2. Brand embedded as a label but not the registrable domain
    for brand in PROTECTED_BRANDS:
        if brand in host:
            base = host.split(".")[0]
            if base not in {d.split(".")[0] for d in PROTECTED_DOMAINS}:
                return UrlFinding(
                    url, host, 0.88,
                    f"Domain embeds the protected brand '{brand.upper()}' but is not an official "
                    f"domain. Official communications are only issued from: "
                    f"{', '.join(sorted(PROTECTED_DOMAINS))}.",
                )

    # 3. Typosquat distance
    for good in PROTECTED_DOMAINS:
        ratio = SequenceMatcher(None, host, good).ratio()
        if 0.80 <= ratio < 1.0:
            return UrlFinding(
                url, host, 0.85,
                f"Domain is a near-miss for the official domain '{good}' "
                f"({ratio:.0%} similar) — consistent with typosquatting.",
            )

    return UrlFinding(url, host, 0.15, "Unrecognised domain. Not an official securities-market domain.")


def analyse_urls_in(text: str) -> tuple[float, list[UrlFinding]]:
    findings = [analyse_url(u) for u in extract_urls(text)]
    if not findings:
        return 0.0, []
    return max(f.risk for f in findings), findings
