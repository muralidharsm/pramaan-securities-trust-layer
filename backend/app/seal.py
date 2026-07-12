"""
PRAMAAN Seal — issuer identity and signing.

PROTOTYPE NOTE (be honest about this in the pitch):
We use Ed25519 keys generated locally to stand in for CCA-India Class-3 Digital
Signature Certificates. The cryptographic property demonstrated is identical —
an issuer holds a private key, signs at source, and anyone can verify against the
published public key. Production binds that key to a real DSC issued under the
IT Act, 2000 (s.3 / s.5), which is what gives the signature evidentiary value in
an Indian court. That is a procurement problem, not an engineering one.

Private keys never leave the issuer in production. Here they live in a dev
keystore so the demo can seal on your behalf.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .merkle import LogEntry, TransparencyLog


@dataclass(frozen=True)
class Issuer:
    did: str
    name: str
    sebi_reg_no: str
    category: str            # regulator | exchange | depository | listed_company | intermediary
    public_key_hex: str

    def public_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key_hex))


class IssuerRegistry:
    """
    The Registry of Authorised Financial Issuers (RAFI).

    Production bootstraps this from SEBI's public intermediary registration
    database and the exchanges' listed-company master. Here it is a JSON file.
    """

    def __init__(self, issuers_path: Path, keystore_path: Path) -> None:
        self.issuers_path = issuers_path
        self.keystore_path = keystore_path
        self._issuers: dict[str, Issuer] = {}
        self._private_keys: dict[str, Ed25519PrivateKey] = {}
        self.load()

    def load(self) -> None:
        if not self.issuers_path.exists():
            return
        raw = json.loads(self.issuers_path.read_text(encoding="utf-8"))
        self._issuers = {i["did"]: Issuer(**i) for i in raw}

        if self.keystore_path.exists():
            ks = json.loads(self.keystore_path.read_text(encoding="utf-8"))
            self._private_keys = {
                did: Ed25519PrivateKey.from_private_bytes(bytes.fromhex(sk))
                for did, sk in ks.items()
            }

    def all(self) -> list[Issuer]:
        return list(self._issuers.values())

    def get(self, did: str) -> Issuer | None:
        return self._issuers.get(did)

    def private_key(self, did: str) -> Ed25519PrivateKey | None:
        return self._private_keys.get(did)


def content_hash(data: bytes) -> str:
    """The single identifier a sealed artefact is known by."""
    return hashlib.sha256(data).hexdigest()


def seal_artefact(
    *,
    registry: IssuerRegistry,
    log: TransparencyLog,
    issuer_did: str,
    data: bytes,
    artefact_type: str,
    title: str,
) -> LogEntry:
    """Sign an artefact at source and append it to the transparency log."""
    issuer = registry.get(issuer_did)
    if issuer is None:
        raise ValueError(f"unknown issuer: {issuer_did}")
    sk = registry.private_key(issuer_did)
    if sk is None:
        raise ValueError(f"no signing key held for issuer: {issuer_did}")

    entry = LogEntry(
        index=-1,  # assigned on append
        content_hash=content_hash(data),
        issuer_did=issuer.did,
        issuer_name=issuer.name,
        sebi_reg_no=issuer.sebi_reg_no,
        artefact_type=artefact_type,
        title=title,
        signature="",
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    entry.signature = sk.sign(entry.canonical()).hex()
    return log.append(entry)


def verify_seal(registry: IssuerRegistry, entry: LogEntry) -> bool:
    """Does the issuer's published public key actually vouch for this entry?"""
    issuer = registry.get(entry.issuer_did)
    if issuer is None:
        return False
    try:
        issuer.public_key().verify(bytes.fromhex(entry.signature), entry.canonical())
        return True
    except (InvalidSignature, ValueError):
        return False
