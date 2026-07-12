"""
The tests that matter. If these pass, the core claim in the pitch is true:
a forged official communication is caught with zero model inference.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.detect.text import analyse_text
from app.detect.urls import analyse_url
from app.fusion import Verdict, fuse
from app.grounding import ground_claims
from app.merkle import TransparencyLog, verify_inclusion
from app.registry import SebiRegistry
from app.seal import IssuerRegistry, content_hash, seal_artefact, verify_seal


@pytest.fixture()
def env(tmp_path: Path):
    sk = Ed25519PrivateKey.generate()
    issuers_path = tmp_path / "issuers.json"
    keystore_path = tmp_path / "keystore.json"
    issuers_path.write_text(json.dumps([{
        "did": "did:pramaan:nse",
        "name": "National Stock Exchange of India",
        "sebi_reg_no": "MII-NSE-0001",
        "category": "exchange",
        "public_key_hex": sk.public_key().public_bytes_raw().hex(),
    }]))
    keystore_path.write_text(json.dumps({"did:pramaan:nse": sk.private_bytes_raw().hex()}))

    registry = IssuerRegistry(issuers_path, keystore_path)
    log = TransparencyLog(path=tmp_path / "log.jsonl")
    log.load()
    return registry, log


# --- Merkle transparency log -------------------------------------------------

def test_merkle_inclusion_proof_verifies(env):
    registry, log = env
    for i in range(7):  # odd size — exercises the promoted-node path
        seal_artefact(registry=registry, log=log, issuer_did="did:pramaan:nse",
                      data=f"filing {i}".encode(), artefact_type="circular",
                      title=f"Circular {i}")

    for idx in range(log.size()):
        proof = log.inclusion_proof(idx)
        assert verify_inclusion(
            log.entries[idx].canonical(), idx, log.size(), proof, log.root_hash()
        ), f"inclusion proof failed for entry {idx}"


def test_log_is_append_only_and_idempotent(env):
    registry, log = env
    a = seal_artefact(registry=registry, log=log, issuer_did="did:pramaan:nse",
                      data=b"same bytes", artefact_type="circular", title="X")
    b = seal_artefact(registry=registry, log=log, issuer_did="did:pramaan:nse",
                      data=b"same bytes", artefact_type="circular", title="X")
    assert a.index == b.index
    assert log.size() == 1
    assert not hasattr(log, "delete")


def test_signature_verifies_and_tampering_breaks_it(env):
    registry, log = env
    entry = seal_artefact(registry=registry, log=log, issuer_did="did:pramaan:nse",
                          data=b"genuine circular", artefact_type="circular",
                          title="NSE/2026/01")
    assert verify_seal(registry, entry) is True

    entry.title = "NSE/2026/01 — AMENDED"   # tamper with the signed payload
    assert verify_seal(registry, entry) is False


# --- THE CORE CLAIM ----------------------------------------------------------

def test_forged_circular_is_caught_without_any_model(env):
    """
    A forged 'SEBI circular' is not in the log. That fact alone convicts it.
    No classifier is consulted. This is the pitch, as a test.
    """
    _, log = env
    forged = b"SEBI CIRCULAR: Priority IPO allotment for select investors."
    assert log.lookup(content_hash(forged)) is None

    assessment = fuse(risks=[], reasons=[], sealed=False, claimed_official=True)
    assert assessment.verdict is Verdict.RED
    assert any(r.code == "NOT_IN_LOG" for r in assessment.reasons)


def test_genuine_sealed_content_short_circuits_to_green(env):
    registry, log = env
    body = b"Members are notified of revised surveillance measures."
    seal_artefact(registry=registry, log=log, issuer_did="did:pramaan:nse",
                  data=body, artefact_type="circular", title="NSE/SURV/2026/041")

    entry = log.lookup(content_hash(body))
    assert entry is not None
    assessment = fuse(risks=[], reasons=[], sealed=True, seal_entry=entry.to_dict())
    assert assessment.verdict is Verdict.GREEN
    assert assessment.trust_score == 100
    assert "no model inference" in assessment.latency_note


# --- Detection ---------------------------------------------------------------

def test_phishing_red_flags_fire():
    risk, signals = analyse_text(
        "SEBI approved! Guaranteed 40% returns. Only 5 seats left. Join my Telegram group now!"
    )
    codes = {s.rule_id for s in signals}
    assert "FALSE_SEBI_ENDORSEMENT" in codes
    assert "GUARANTEED_RETURNS" in codes
    assert "URGENCY_PRESSURE" in codes
    assert "UNREGISTERED_ADVISORY" in codes
    assert risk > 0.9


def test_risk_score_stays_bounded():
    """Noisy-OR, not a sum. Many signals must never exceed 1.0."""
    risk, _ = analyse_text(
        "SEBI approved guaranteed returns! risk-free profit! insider info! "
        "join my premium telegram group! pay to me@ybl! hurry up! only 2 slots left!"
    )
    assert 0.0 <= risk <= 1.0


def test_clean_text_scores_zero():
    risk, signals = analyse_text("The board will meet on Thursday to approve the quarterly results.")
    assert risk == 0.0 and signals == []


def test_typosquat_and_official_domains():
    assert analyse_url("https://sebi.gov.in/circular").risk == 0.0
    assert analyse_url("https://sebi-india-verify.com/claim").risk >= 0.8
    assert analyse_url("https://nseindia.com").risk == 0.0


# --- Registry ----------------------------------------------------------------

def test_fake_registration_number_is_flagged(tmp_path: Path):
    p = tmp_path / "reg.json"
    p.write_text(json.dumps([{"name": "Meridian Capital Advisors",
                              "sebi_reg_no": "INA000000001",
                              "category": "Investment Adviser", "status": "active"}]))
    reg = SebiRegistry(p)

    bad = reg.check_text("I am SEBI registered, reg no INA999999999. DM for calls.")
    assert bad and bad[0].registered is False and bad[0].risk > 0.9

    good = reg.check_text("Meridian Capital Advisors, SEBI Reg. INA000000001")
    assert good and good[0].registered is True and good[0].risk == 0.0


# --- Claim grounding ---------------------------------------------------------

def test_ungrounded_buyback_claim_is_escalated(env):
    registry, log = env
    seal_artefact(registry=registry, log=log, issuer_did="did:pramaan:nse",
                  data=b"real filing", artefact_type="announcement",
                  title="RELIANCE — Intimation of Board Meeting for Q1 results")

    # A claim that IS backed by a sealed filing
    risk, findings = ground_claims("Reliance announces its quarterly results today.", log)
    assert findings and findings[0].grounded is True and risk == 0.0

    # A claim that is NOT — this is the perfect-deepfake case
    risk, findings = ground_claims("Reliance has announced a massive buyback!", log)
    assert findings and findings[0].grounded is False and risk >= 0.9
