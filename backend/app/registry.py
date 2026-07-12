"""
SEBI registered-intermediary lookup.

This is the highest value-per-line-of-code component in the entire system. It is
a dictionary lookup. It has no ML, no latency and no failure mode — and it
answers the single most useful question a defrauded retail investor can ask:

    "Is this person actually registered with SEBI?"

DATA WARNING
------------
`data/sebi_registry.json` contains SYNTHETIC entries with clearly-fake
registration numbers, for demo purposes only. Do NOT ship real registration
numbers you have not verified, and do NOT present synthetic data as real to the
jury. Before the prototype round, replace this with a scraped/ingested snapshot
of SEBI's public intermediary database and cite the source and retrieval date.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


# SEBI registration numbers follow recognisable prefixes by intermediary type,
# e.g. INA (investment advisers), INH (research analysts), INZ (stockbrokers).
REG_NO_RE = re.compile(r"\b(IN[AHZPDB])\s?(\d{9})\b", re.IGNORECASE)


@dataclass(frozen=True)
class Intermediary:
    name: str
    sebi_reg_no: str
    category: str
    status: str  # active | suspended | expired


@dataclass(frozen=True)
class RegistryFinding:
    claimed: str
    registered: bool
    risk: float
    detail: str
    match: Intermediary | None = None


class SebiRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._by_reg: dict[str, Intermediary] = {}
        self._by_name: dict[str, Intermediary] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for row in raw:
            item = Intermediary(**row)
            self._by_reg[item.sebi_reg_no.upper().replace(" ", "")] = item
            self._by_name[item.name.lower()] = item

    def by_reg_no(self, reg_no: str) -> Intermediary | None:
        return self._by_reg.get(reg_no.upper().replace(" ", ""))

    def check_text(self, text: str) -> list[RegistryFinding]:
        """Pull any claimed SEBI registration number out of the content and check it."""
        findings: list[RegistryFinding] = []
        for m in REG_NO_RE.finditer(text):
            claimed = (m.group(1) + m.group(2)).upper()
            hit = self.by_reg_no(claimed)
            if hit is None:
                findings.append(
                    RegistryFinding(
                        claimed=claimed,
                        registered=False,
                        risk=0.92,
                        detail=(
                            f"Registration number {claimed} does NOT appear in SEBI's "
                            f"registered-intermediary registry. A fabricated registration "
                            f"number is a strong indicator of an unregistered advisor."
                        ),
                    )
                )
            elif hit.status != "active":
                findings.append(
                    RegistryFinding(
                        claimed=claimed,
                        registered=True,
                        risk=0.75,
                        detail=f"{hit.name} ({claimed}) is registered but the registration is {hit.status.upper()}.",
                        match=hit,
                    )
                )
            else:
                findings.append(
                    RegistryFinding(
                        claimed=claimed,
                        registered=True,
                        risk=0.0,
                        detail=f"{hit.name} is an active SEBI-registered {hit.category} ({claimed}).",
                        match=hit,
                    )
                )
        return findings
