"""
PRAMAAN — API surface.

The verification pipeline, in the order the pitch describes it:

    B1 Ingest -> B2 Seal check -> B3 Multimodal fan-out -> B4 Claim-grounding
       -> B5 Fusion + explanation -> B6 Verdict

The seal check runs FIRST and short-circuits. That ordering is the product, not
an optimisation: most fraud is disposed of before a single model is loaded.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .detect import text as text_detect
from .detect import urls as url_detect
from .fusion import Reason, fuse
from .grounding import ground_claims
from .merkle import TransparencyLog, verify_inclusion
from .registry import SebiRegistry
from .seal import IssuerRegistry, content_hash, seal_artefact, verify_seal

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
FRONTEND = BASE.parent / "frontend"

app = FastAPI(
    title="PRAMAAN",
    description="The Authenticity Layer for India's Securities Market. "
                "SEBI Securities Market TechSprint @ GFF 2026 — Problem Statement 01.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only. Lock this down before any pilot.
    allow_methods=["*"],
    allow_headers=["*"],
)

log = TransparencyLog(path=DATA / "transparency_log.jsonl")
log.load()
issuers = IssuerRegistry(DATA / "issuers.json", DATA / "keystore.dev.json")
sebi_registry = SebiRegistry(DATA / "sebi_registry.json")


# Phrases that assert official origin. If one of these fires and there is no
# seal, we are in "absence of proof is proof of absence" territory.
OFFICIAL_CLAIM_RE = re.compile(
    r"\b(sebi|nse|bse|nsdl|cdsl)\b.{0,40}\b(circular|notice|announcement|official|advisory|order)\b"
    r"|\b(circular|notice|announcement)\b.{0,20}\bfrom\b.{0,20}\b(sebi|nse|bse|nsdl|cdsl)\b"
    r"|\bofficial\s+(communication|announcement|circular)\b",
    re.IGNORECASE | re.DOTALL,
)


# ---------------------------------------------------------------- schemas ----

class SealRequest(BaseModel):
    issuer_did: str = Field(..., examples=["did:pramaan:nse"])
    content: str = Field(..., description="The artefact body. Hashed, then sealed.")
    artefact_type: str = Field("announcement", examples=["circular", "announcement"])
    title: str


class VerifyRequest(BaseModel):
    content: str = Field(..., description="Forwarded message, circular text, caption, or URL.")


# ------------------------------------------------------------------ seal -----

@app.post("/api/v1/seal", tags=["PRAMAAN Seal"])
def seal(req: SealRequest):
    """Issuer-side. Sign an artefact at source and commit it to the transparency log."""
    try:
        entry = seal_artefact(
            registry=issuers,
            log=log,
            issuer_did=req.issuer_did,
            data=req.content.encode("utf-8"),
            artefact_type=req.artefact_type,
            title=req.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "sealed": True,
        "entry": entry.to_dict(),
        "signature_valid": verify_seal(issuers, entry),
        "signed_tree_head": log.signed_tree_head(),
    }


@app.get("/api/v1/log/sth", tags=["PRAMAAN Seal"])
def signed_tree_head():
    """The current Signed Tree Head. In production this is co-signed and anchored daily."""
    return log.signed_tree_head()


@app.get("/api/v1/log/entries", tags=["PRAMAAN Seal"])
def entries(limit: int = 50):
    return {
        "tree_size": log.size(),
        "root_hash": log.root_hash(),
        "entries": [e.to_dict() for e in reversed(log.entries[-limit:])],
    }


@app.get("/api/v1/log/proof/{index}", tags=["PRAMAAN Seal"])
def inclusion_proof(index: int):
    """Merkle audit path. Anyone can recompute the root from this — no trust in us required."""
    try:
        proof = log.inclusion_proof(index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail="no such log entry") from exc

    entry = log.entries[index]
    return {
        "index": index,
        "tree_size": log.size(),
        "root_hash": log.root_hash(),
        "audit_path": proof,
        "verified_locally": verify_inclusion(
            entry.canonical(), index, log.size(), proof, log.root_hash()
        ),
    }


@app.get("/api/v1/issuers", tags=["PRAMAAN Seal"])
def list_issuers():
    return [
        {"did": i.did, "name": i.name, "sebi_reg_no": i.sebi_reg_no, "category": i.category}
        for i in issuers.all()
    ]


# ---------------------------------------------------------------- verify -----

@app.post("/api/v1/verify", tags=["PRAMAAN Shield"])
def verify(req: VerifyRequest):
    """
    The investor-facing endpoint. This is what the WhatsApp bot calls.

    Everything here is real and running. The video/audio models are not yet
    trained (see app/detect/media.py) and therefore contribute nothing — by
    design, rather than by fabricating a score.
    """
    body = req.content
    reasons: list[Reason] = []
    risks: list[float] = []

    # -- B2. SEAL CHECK. First, fastest, most decisive. ------------------------
    digest = content_hash(body.encode("utf-8"))
    entry = log.lookup(digest)

    if entry is not None:
        valid = verify_seal(issuers, entry)
        if valid:
            reasons.append(Reason(
                code="SEALED",
                severity="info",
                message=(
                    f"Sealed by {entry.issuer_name} (SEBI Reg. {entry.sebi_reg_no}) on "
                    f"{entry.timestamp}. Present in the transparency log at index {entry.index}."
                ),
            ))
            return fuse(
                risks=[], reasons=reasons, sealed=True, seal_entry=entry.to_dict()
            ).__dict__
        reasons.append(Reason(
            code="BAD_SIGNATURE",
            severity="critical",
            message="A log entry exists for this content, but the issuer's signature does not verify.",
        ))
        return fuse(risks=[], reasons=reasons, sealed=False, tampered=True).__dict__

    # -- Does it *claim* to be official while carrying no seal? ---------------
    claimed_official = bool(OFFICIAL_CLAIM_RE.search(body))

    # -- B3. Multimodal fan-out (text + URL live; media stubbed) --------------
    text_risk, text_signals = text_detect.analyse_text(body)
    for s in text_signals:
        reasons.append(Reason(
            code=s.rule_id,
            severity="critical" if s.weight >= 0.75 else "warning",
            message=f"{s.explanation}  [matched: \u201c{s.matched}\u201d]",
        ))
    if text_risk:
        risks.append(text_risk)

    url_risk, url_findings = url_detect.analyse_urls_in(body)
    for f in url_findings:
        if f.risk >= 0.5:
            reasons.append(Reason(code="SUSPICIOUS_URL", severity="critical", message=f"{f.domain}: {f.reason}"))
        elif f.risk == 0.0:
            reasons.append(Reason(code="OFFICIAL_DOMAIN", severity="info", message=f"{f.domain}: {f.reason}"))
    if url_risk:
        risks.append(url_risk)

    # -- Registry cross-reference: is the claimed advisor even registered? ----
    for f in sebi_registry.check_text(body):
        reasons.append(Reason(
            code="SEBI_REGISTRY",
            severity="critical" if f.risk >= 0.75 else "info",
            message=f.detail,
        ))
        if f.risk:
            risks.append(f.risk)

    # -- B4. CLAIM-GROUNDING --------------------------------------------------
    ground_risk, ground_findings = ground_claims(body, log)
    for f in ground_findings:
        reasons.append(Reason(
            code="CLAIM_GROUNDING",
            severity="critical" if not f.grounded else "info",
            message=f.detail,
        ))
    if ground_risk:
        risks.append(ground_risk)

    # -- B5/B6. Fusion + verdict ---------------------------------------------
    return fuse(
        risks=risks,
        reasons=reasons,
        sealed=False,
        claimed_official=claimed_official,
    ).__dict__


@app.get("/api/v1/health", tags=["ops"])
def health():
    return {
        "status": "ok",
        "log_size": log.size(),
        "root_hash": log.root_hash(),
        "issuers": len(issuers.all()),
    }


# ---------------------------------------------------------------- frontend ---

if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")
