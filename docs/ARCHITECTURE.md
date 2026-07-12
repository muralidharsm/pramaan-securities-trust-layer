# Architecture notes

## Why the seal check runs first

Ordering is the product. The seal check is O(1), deterministic, and disposes of
two entire fraud classes — forged official communications and tampered genuine
ones — without loading a model.

Only what survives it reaches the multimodal fan-out. That is what makes the
system cheap to run at national scale, and what makes it robust to the next
generation of generative models: **the seal is generator-agnostic.** It does not
care how good the fake gets. It only cares whether the real thing was signed.

## Why absence of proof is proof of absence

This inversion is the whole thesis, so state it precisely:

Once *every* authorised issuer seals at source, the set of genuine official
communications is exactly the set of entries in the transparency log. A
communication claiming official origin that is **not** in the log is therefore
not merely unverified — it is *provably not genuine*. No inference. No
probability. A lookup.

The property depends on issuer adoption, which is why the regulator, not a
private vendor, must be the convener. That is the ask on the final slide.

## Threat model

| Adversary capability | Defence |
|---|---|
| Forges an official circular | Seal check — not in the log |
| Modifies a genuine sealed circular | Hash mismatch against log entry |
| Deepfakes a CEO announcing a corporate action | **Claim-Grounding** — no sealed filing backs it |
| Deepfakes a CEO saying something non-factual | Media models (in progress) + provenance absence |
| Impersonates a registered adviser | SEBI registry cross-reference |
| Registers `sebi-india-verify.com` | Typosquat / brand-embedding analysis |
| Compromises an issuer's signing key | Key revocation via status list; log is append-only so the damage is bounded and auditable |
| Compromises the log operator (us) | Multi-party anchoring — SEBI, exchanges and depositories co-sign the daily root. A rewritten history fails to reconcile. |

The last row is the one a security-literate juror will probe. Have the answer ready.

## Known limitations (say these out loud)

1. **Cold start.** The seal is worthless until issuers adopt it. The regulator solves this; a startup cannot.
2. **rPPG is fragile under compression.** WhatsApp re-encodes video hard. Measure before you claim.
3. **The registry snapshot goes stale.** Needs a scheduled ingest, not a one-off scrape.
4. **Claim extraction is pattern-based in the prototype.** Production needs NER + relation extraction.
