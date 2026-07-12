"""
Bootstrap the demo: generate issuer keypairs, seed the SEBI registry, and seal a
few genuine artefacts so the transparency log is not empty on first run.

    python bootstrap.py

Idempotent-ish: it overwrites issuers/keystore/registry and rebuilds the log.
Delete data/transparency_log.jsonl first if you want a clean tree.
"""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.merkle import TransparencyLog
from app.seal import IssuerRegistry, seal_artefact

DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(parents=True, exist_ok=True)


# --- Issuers (Registry of Authorised Financial Issuers) ----------------------
# NOTE: reg numbers below are SYNTHETIC placeholders for the demo.
ISSUERS = [
    {"did": "did:pramaan:sebi", "name": "Securities and Exchange Board of India",
     "sebi_reg_no": "REGULATOR", "category": "regulator"},
    {"did": "did:pramaan:nse", "name": "National Stock Exchange of India",
     "sebi_reg_no": "MII-NSE-0001", "category": "exchange"},
    {"did": "did:pramaan:bse", "name": "BSE Limited",
     "sebi_reg_no": "MII-BSE-0001", "category": "exchange"},
    {"did": "did:pramaan:reliance", "name": "Reliance Industries Limited",
     "sebi_reg_no": "LISTED-RELIANCE", "category": "listed_company"},
]

# --- SEBI registered intermediaries (SYNTHETIC — replace before the jury round)
REGISTRY = [
    {"name": "Meridian Capital Advisors", "sebi_reg_no": "INA000000001",
     "category": "Investment Adviser", "status": "active"},
    {"name": "Sundaram Research Partners", "sebi_reg_no": "INH000000002",
     "category": "Research Analyst", "status": "active"},
    {"name": "Coastal Securities Pvt Ltd", "sebi_reg_no": "INZ000000003",
     "category": "Stock Broker", "status": "active"},
    {"name": "Lapsed Advisory Services", "sebi_reg_no": "INA000000009",
     "category": "Investment Adviser", "status": "expired"},
]

# --- Genuine artefacts, sealed at source ------------------------------------
GENUINE = [
    ("did:pramaan:reliance", "announcement",
     "RELIANCE INDUSTRIES LIMITED — Intimation of Board Meeting for Q1 FY27 Results",
     "Reliance Industries Limited hereby informs the Exchange that a meeting of the Board of "
     "Directors is scheduled to consider and approve the unaudited financial results for the "
     "quarter ended 30 June 2026."),
    ("did:pramaan:nse", "circular",
     "NSE/SURV/2026/041 — Revised Surveillance Measures for SME Segment",
     "Members are hereby notified of revised surveillance measures applicable to securities in "
     "the SME segment with effect from the settlement cycle commencing 20 July 2026."),
    ("did:pramaan:sebi", "circular",
     "SEBI/HO/MIRSD/2026/18 — Caution against Unregistered Investment Advisers",
     "Investors are cautioned against dealing with unregistered entities offering assured "
     "returns. SEBI does not approve, endorse or recommend any investment product or advisor."),
]


def main() -> None:
    issuers_path = DATA / "issuers.json"
    keystore_path = DATA / "keystore.dev.json"

    pub, priv = [], {}
    for spec in ISSUERS:
        sk = Ed25519PrivateKey.generate()
        pk_bytes = sk.public_key().public_bytes_raw()
        pub.append({**spec, "public_key_hex": pk_bytes.hex()})
        priv[spec["did"]] = sk.private_bytes_raw().hex()

    issuers_path.write_text(json.dumps(pub, indent=2), encoding="utf-8")
    keystore_path.write_text(json.dumps(priv, indent=2), encoding="utf-8")
    (DATA / "sebi_registry.json").write_text(json.dumps(REGISTRY, indent=2), encoding="utf-8")

    log = TransparencyLog(path=DATA / "transparency_log.jsonl")
    log.load()
    registry = IssuerRegistry(issuers_path, keystore_path)

    for did, kind, title, body in GENUINE:
        entry = seal_artefact(
            registry=registry, log=log, issuer_did=did,
            data=body.encode("utf-8"), artefact_type=kind, title=title,
        )
        print(f"  sealed #{entry.index}  {title[:60]}")

    print(f"\nIssuers:    {len(pub)}")
    print(f"Registry:   {len(REGISTRY)} intermediaries")
    print(f"Log size:   {log.size()}")
    print(f"Root hash:  {log.root_hash()}")
    print("\nRun:  uvicorn app.main:app --reload  →  http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
