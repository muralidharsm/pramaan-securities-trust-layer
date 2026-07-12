"""
RFC 6962 style append-only Merkle transparency log.

This is the heart of PRAMAAN Seal. It is what lets us say, with a proof rather
than a probability:

    "This 'SEBI circular' is not in the log, therefore it was never issued."

Leaf hash  = SHA256(0x00 || entry_bytes)
Node hash  = SHA256(0x01 || left || right)

The 0x00 / 0x01 domain-separation prefixes are what stop an attacker from
presenting an internal node as if it were a leaf (the classic second-preimage
attack on naive Merkle trees). Do not remove them.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(entry: bytes) -> bytes:
    return _sha256(LEAF_PREFIX + entry)


def node_hash(left: bytes, right: bytes) -> bytes:
    return _sha256(NODE_PREFIX + left + right)


def _root(hashes: list[bytes]) -> bytes:
    """Merkle root of a list of leaf hashes. Empty tree -> SHA256 of nothing."""
    if not hashes:
        return _sha256(b"")
    level = list(hashes)
    while len(level) > 1:
        nxt: list[bytes] = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(node_hash(level[i], level[i + 1]))
        if len(level) % 2 == 1:  # odd node is promoted, not duplicated
            nxt.append(level[-1])
        level = nxt
    return level[0]


@dataclass
class LogEntry:
    index: int
    content_hash: str      # SHA-256 hex of the sealed artefact itself
    issuer_did: str
    issuer_name: str
    sebi_reg_no: str
    artefact_type: str     # circular | announcement | video | press_release | advisory
    title: str
    signature: str         # Ed25519 signature over the canonical entry, hex
    timestamp: str         # ISO-8601 UTC

    def canonical(self) -> bytes:
        """Deterministic serialisation. Signature is excluded — it signs this."""
        payload = {
            "content_hash": self.content_hash,
            "issuer_did": self.issuer_did,
            "sebi_reg_no": self.sebi_reg_no,
            "artefact_type": self.artefact_type,
            "title": self.title,
            "timestamp": self.timestamp,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "content_hash": self.content_hash,
            "issuer_did": self.issuer_did,
            "issuer_name": self.issuer_name,
            "sebi_reg_no": self.sebi_reg_no,
            "artefact_type": self.artefact_type,
            "title": self.title,
            "signature": self.signature,
            "timestamp": self.timestamp,
        }


@dataclass
class TransparencyLog:
    """
    Append-only. There is deliberately no delete() and no update().

    In production the daily root hash is co-signed and anchored to a permissioned
    Hyperledger Fabric consortium (SEBI + exchanges + depositories) so that no
    single operator — including us — can rewrite history. Here we persist to a
    JSONL file, which is enough to demonstrate the property.
    """

    path: Path
    entries: list[LogEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # content_hash -> index, so a lookup is O(1) instead of a scan
    _index_by_hash: dict[str, int] = field(default_factory=dict, repr=False)

    def load(self) -> None:
        self.entries.clear()
        self._index_by_hash.clear()
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = LogEntry(**json.loads(line))
                self.entries.append(entry)
                self._index_by_hash[entry.content_hash] = entry.index

    def append(self, entry: LogEntry) -> LogEntry:
        with self._lock:
            if entry.content_hash in self._index_by_hash:
                # Idempotent: sealing the same bytes twice is not an error.
                return self.entries[self._index_by_hash[entry.content_hash]]
            entry.index = len(self.entries)
            self.entries.append(entry)
            self._index_by_hash[entry.content_hash] = entry.index
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.to_dict(), separators=(",", ":")) + "\n")
            return entry

    # -- reads ---------------------------------------------------------------

    def size(self) -> int:
        return len(self.entries)

    def leaf_hashes(self) -> list[bytes]:
        return [leaf_hash(e.canonical()) for e in self.entries]

    def root_hash(self) -> str:
        return _root(self.leaf_hashes()).hex()

    def lookup(self, content_hash: str) -> LogEntry | None:
        idx = self._index_by_hash.get(content_hash.lower())
        return self.entries[idx] if idx is not None else None

    def inclusion_proof(self, index: int) -> list[str]:
        """
        Audit path proving entry `index` is committed under the current root.

        The subtlety: when a level has an odd number of nodes, the last node is
        *promoted* to the next level rather than duplicated. A promoted node has
        no sibling at that level, so no proof element is emitted — and the
        verifier must simulate the same level sizes to stay in step. Getting this
        wrong is the single most common Merkle bug; the odd-size test guards it.
        """
        if not 0 <= index < len(self.entries):
            raise IndexError("no such entry")

        level = self.leaf_hashes()
        fn = index
        proof: list[bytes] = []

        while len(level) > 1:
            if fn % 2 == 1:
                proof.append(level[fn - 1])           # sibling on the left
            elif fn + 1 < len(level):
                proof.append(level[fn + 1])           # sibling on the right
            # else: fn is even and last -> promoted, no sibling, no proof element

            nxt: list[bytes] = []
            for j in range(0, len(level) - 1, 2):
                nxt.append(node_hash(level[j], level[j + 1]))
            if len(level) % 2 == 1:
                nxt.append(level[-1])

            fn //= 2
            level = nxt

        return [h.hex() for h in proof]

    def signed_tree_head(self) -> dict[str, Any]:
        return {
            "tree_size": self.size(),
            "root_hash": self.root_hash(),
            "log_id": "pramaan-securities-log-v1",
        }


def verify_inclusion(
    entry_canonical: bytes, index: int, tree_size: int, proof: list[str], root_hash: str
) -> bool:
    """
    Recompute the root from a leaf + audit path. Fully client-side: an investor
    (or a court) can verify a seal without trusting the log operator at all.

    The verifier reconstructs the level sizes from `tree_size` alone, so it knows
    exactly where a promoted node had no sibling and consumes no proof element there.
    """
    if not 0 <= index < tree_size:
        return False

    h = leaf_hash(entry_canonical)
    fn = index
    size = tree_size
    consumed = 0

    while size > 1:
        if fn % 2 == 1:
            if consumed >= len(proof):
                return False
            h = node_hash(bytes.fromhex(proof[consumed]), h)
            consumed += 1
        elif fn + 1 < size:
            if consumed >= len(proof):
                return False
            h = node_hash(h, bytes.fromhex(proof[consumed]))
            consumed += 1
        # else: promoted node, carried up untouched

        fn //= 2
        size = (size + 1) // 2

    return consumed == len(proof) and h.hex() == root_hash
