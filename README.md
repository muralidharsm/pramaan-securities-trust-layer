# PRAMAAN — The Authenticity Layer for India's Securities Market

> **"If it isn't sealed, it isn't SEBI."**

**SEBI Securities Market TechSprint @ Global Fintech Fest 2026**
**Problem Statement 01 — Investor Protection:** *AI-Driven Detection of Synthetic Media and Phishing Attacks in Securities Markets*
**Team:** `code hunt` (solo) — Murali Dhar SM

---

Generative AI has industrialised securities-market fraud. Deepfaked CEO videos, cloned broker voices, LLM-crafted phishing, and forged regulatory circulars now reach India's retail investors faster than any regulator can respond. The mirror-image failure is worse and almost entirely unaddressed: when a communication genuinely *is* from SEBI, an exchange, or a registered intermediary, **the investor has no way to prove it.**

Every other approach to this problem builds a better fake-detector — a race that is lost by one model generation, permanently. **PRAMAAN takes the other road.**

**PRAMAAN Seal** lets authorised issuers sign communications at source, committing each signature to an append-only Merkle transparency log (RFC 6962). This is what turns *absence of proof into proof of absence*: a "SEBI circular" that is not in the log was never issued — and that verdict takes milliseconds and **zero model inference**.

**PRAMAAN Shield** defends the unsealed long tail: multilingual phishing intent, typosquatted domains, fabricated SEBI registration numbers, and (in progress) face-forgery and voice anti-spoofing models.

Binding the two is the **Claim-Grounding Engine**, which asks the question no pixel detector can: *is this market-moving claim backed by a sealed exchange filing?* A flawless deepfake announcing a fictional buyback still fails — because the buyback was never filed.

---

## Quickstart

### Option A — Streamlit (fastest; this is what's deployed)

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Live demo:** _(paste your Streamlit Cloud URL here after deploying)_

### Option B — FastAPI + web console

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd backend
python bootstrap.py                                     # generates issuer keys, seeds the log
uvicorn app.main:app --reload --port 8000
```

Open **http://127.0.0.1:8000** — the demo console. API docs at **/docs**.

In VS Code: press **F5** and pick *"PRAMAAN: run API + UI"*. Recommended extensions are prompted on first open.

```bash
cd backend && python -m pytest tests/ -v                # 11 tests, all passing
```

Both front-ends call the **same engine** in `backend/app`. There is no duplicated logic — Streamlit imports the modules directly.

---

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (public).
2. Go to **share.streamlit.io** → *New app* → pick the repo.
3. Main file path: `streamlit_app.py` · Python 3.12 → **Deploy**.

Issuer keys and the transparency log are **not** committed (see `.gitignore`) — the app regenerates them on cold start, so a fresh container always boots with a valid, self-consistent log.

---

## The four demo cases

The Investor Verifier ships with one-click samples. They walk the entire argument:

| # | Input | Verdict | Why it matters |
|---|---|---|---|
| 1 | A genuine, sealed NSE circular | 🟢 **GREEN**, score 100 | Resolved by seal check alone. **No model ran.** |
| 2 | A forged "OFFICIAL SEBI CIRCULAR" | 🔴 **RED** | Not in the log ⇒ never issued. **No model ran.** |
| 3 | Finfluencer phishing with a fake reg. number | 🔴 **RED** | Six independent signals, each named in plain language |
| 4 | *"Reliance has announced a massive buyback."* | 🔴 **RED** | **The money shot.** Zero phishing keywords. Caught purely by Claim-Grounding — no filing, no buyback. This is the perfect-deepfake case. |

Case 4 is the one to demo to the jury. It contains nothing a phishing classifier would flag, and no pixels for a deepfake detector to examine. It fails on the *fact*.

---

## What is real, and what is not

Being straight about this is a feature. A SEBI jury will ask, and calibration beats theatre.

| Component | Status |
|---|---|
| Merkle transparency log (RFC 6962), inclusion proofs | ✅ **Real.** Tested, including odd-sized trees. |
| Ed25519 issuer signing & verification | ✅ **Real.** |
| Seal check, tamper detection | ✅ **Real.** |
| Multilingual phishing rule engine (EN/HI/TA) | ✅ **Real.** Encodes SEBI's published red flags. |
| Typosquat / homoglyph URL analysis | ✅ **Real.** |
| SEBI registry cross-reference | ⚠️ **Real logic, synthetic data.** `data/sebi_registry.json` holds fake registration numbers. Replace with a real snapshot of SEBI's public registry before the jury round, and cite the source. |
| Claim-Grounding Engine | ⚠️ **Real logic, seeded corpus.** Pattern extraction over a small filings set. Production: NER + relation extraction over the live exchange announcements feed. |
| Video deepfake detection | ❌ **Not built.** Stubbed; contributes **nothing** to the score rather than inventing one. See `app/detect/media.py` for the training plan. |
| Audio anti-spoofing | ❌ **Not built.** Same. |
| CCA-India Class-3 DSC binding | ❌ **Not built.** Ed25519 stands in. The cryptographic property is identical; production binds the key to a real DSC for evidentiary value under the IT Act, 2000. |

**Priority to 9 August:** train **one** media modality properly and benchmark it. One modality with a reported AUC beats two with hand-waving.

---

## Architecture

```
FLOW A — ISSUANCE ("Seal the Real")
  Issuer (DID + DSC) → Signing SDK → C2PA / JWS → Merkle Transparency Log
                                                   → daily root anchored on
                                                     Hyperledger Fabric
                                                     (SEBI + exchanges + depositories)

FLOW B — VERIFICATION ("Surface the Fake")
  Ingest (WhatsApp / API / extension)
    → SEAL CHECK ──── sealed & valid ──→ 🟢 GREEN   (~50 ms, no inference)
                 ──── hash mismatch ───→ 🔴 TAMPERED
                 ──── claims official,
                      no seal ─────────→ 🔴 NOT IN LOG  (no inference)
                 ──── unsealed ────────↓
    → MULTIMODAL FAN-OUT  (video · audio · text · URL · registry)
    → CLAIM-GROUNDING     ("backed by a sealed filing?")   ★
    → FUSION              (Trust Score 0–100 + plain-language reasons)
    → VERDICT             (< 3 s, investor's own language)
    → SEBI CONSOLE        (campaign graph, WORM evidence pack)
```

The seal check runs **first** and short-circuits. That ordering is the product, not an optimisation — most fraud is disposed of before a single model is loaded.

---

## Layout

```
backend/
  app/
    merkle.py      RFC 6962 append-only log, inclusion proofs   ← the core
    seal.py        Ed25519 issuer signing & verification
    registry.py    SEBI registered-intermediary lookup
    grounding.py   Claim-Grounding Engine                        ← the moat
    fusion.py      Trust Score + explainability
    detect/
      text.py      Multilingual phishing rule engine
      urls.py      Typosquat / homoglyph analysis
      media.py     Video + audio stubs (honest, and documented)
    main.py        FastAPI surface
  bootstrap.py     Generate keys, seed registry, seal demo artefacts
  tests/           11 tests. `test_forged_circular_is_caught_without_any_model`
                   is the pitch, expressed as an assertion.
streamlit_app.py   Streamlit console (deployed) — imports the same engine
frontend/
  index.html       Zero-build demo console: verifier, issuer, log
```

---

## Design decisions worth defending

**The rule engine is not a stopgap.** It works today with zero training data, and every verdict names the rule that fired — which is exactly what a regulator needs and what a fine-tuned classifier will not give you for free. MuRIL layers *on top*; the rules are the floor.

**Risk combines with a noisy-OR, not a sum.** Three weak signals should raise suspicion without ever out-weighing one decisive signal, and the score must stay bounded. Summing weights is how these engines end up reporting 340% risk.

**The log has no `delete()` and no `update()`.** Not an oversight.

**Stubs return `available: False`, not a plausible number.** A detector that invents scores is worse than no detector.

---

## Roadmap

- **9 Aug 2026** — solution video. Seal + log + WhatsApp bot + one trained media modality + real SEBI registry snapshot.
- **17–21 Aug 2026** — jury demo. Live: a deepfake caught, and a forged circular killed by the seal check with zero inference.
- **9–11 Sep 2026** — final pitch, GFF, Jio World Centre. Benchmarks: AUC/EER per modality, FPR at operating threshold, p95 latency.

## Licence

MIT — see [LICENSE](LICENSE).
