"""
PRAMAAN — Streamlit console.

This is a *view* over the engine in `backend/app`, not a reimplementation. The
Merkle log, the Ed25519 seal, the rule engine and the Claim-Grounding Engine are
imported and called directly — no HTTP hop, no duplicated logic. If the tests in
backend/tests pass, what you see here is what is being tested.

Deploy: https://share.streamlit.io  →  point it at this file.
Run locally:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from app.detect import text as text_detect          # noqa: E402
from app.detect import urls as url_detect           # noqa: E402
from app.detect.text import OFFICIAL_CLAIM_RE       # noqa: E402
from app.fusion import Reason, Verdict, fuse        # noqa: E402
from app.grounding import ground_claims             # noqa: E402
from app.merkle import TransparencyLog, verify_inclusion  # noqa: E402
from app.registry import SebiRegistry               # noqa: E402
from app.seal import IssuerRegistry, content_hash, seal_artefact, verify_seal  # noqa: E402

DATA = ROOT / "backend" / "data"

st.set_page_config(
    page_title="PRAMAAN — Authenticity Layer for India's Securities Market",
    page_icon="🛡️",
    layout="wide",
)


# --------------------------------------------------------------- bootstrap ---
@st.cache_resource
def boot():
    """
    Streamlit Cloud gives us an ephemeral filesystem, so we generate issuer keys
    and seed the log on cold start. Cached, so it happens once per container.
    """
    if not (DATA / "issuers.json").exists() or not (DATA / "keystore.dev.json").exists():
        sys.path.insert(0, str(ROOT / "backend"))
        import bootstrap as bs
        bs.main()

    log = TransparencyLog(path=DATA / "transparency_log.jsonl")
    log.load()
    issuers = IssuerRegistry(DATA / "issuers.json", DATA / "keystore.dev.json")
    registry = SebiRegistry(DATA / "sebi_registry.json")

    if log.size() == 0:  # log was gitignored; re-seal the genuine artefacts
        import bootstrap as bs
        for did, kind, title, body in bs.GENUINE:
            seal_artefact(registry=issuers, log=log, issuer_did=did,
                          data=body.encode(), artefact_type=kind, title=title)
    return log, issuers, registry


log, issuers, sebi_registry = boot()


# ----------------------------------------------------------------- verify ----
def verify(body: str) -> tuple[object, float]:
    t0 = time.perf_counter()
    reasons: list[Reason] = []
    risks: list[float] = []

    # B2. SEAL CHECK — first, fastest, most decisive.
    entry = log.lookup(content_hash(body.encode("utf-8")))
    if entry is not None:
        if verify_seal(issuers, entry):
            reasons.append(Reason("SEALED", "info",
                f"Sealed by {entry.issuer_name} (SEBI Reg. {entry.sebi_reg_no}) on "
                f"{entry.timestamp}. Present in the transparency log at index {entry.index}."))
            a = fuse(risks=[], reasons=reasons, sealed=True, seal_entry=entry.to_dict())
            return a, (time.perf_counter() - t0) * 1000
        reasons.append(Reason("BAD_SIGNATURE", "critical",
            "A log entry exists for this content, but the issuer's signature does not verify."))
        a = fuse(risks=[], reasons=reasons, sealed=False, tampered=True)
        return a, (time.perf_counter() - t0) * 1000

    claimed_official = bool(OFFICIAL_CLAIM_RE.search(body))

    # B3. Fan-out
    tr, signals = text_detect.analyse_text(body)
    for s in signals:
        reasons.append(Reason(s.rule_id, "critical" if s.weight >= 0.75 else "warning",
                              f"{s.explanation}  [matched: \u201c{s.matched}\u201d]"))
    if tr:
        risks.append(tr)

    ur, findings = url_detect.analyse_urls_in(body)
    for f in findings:
        if f.risk >= 0.5:
            reasons.append(Reason("SUSPICIOUS_URL", "critical", f"{f.domain}: {f.reason}"))
        elif f.risk == 0.0:
            reasons.append(Reason("OFFICIAL_DOMAIN", "info", f"{f.domain}: {f.reason}"))
    if ur:
        risks.append(ur)

    for f in sebi_registry.check_text(body):
        reasons.append(Reason("SEBI_REGISTRY", "critical" if f.risk >= 0.75 else "info", f.detail))
        if f.risk:
            risks.append(f.risk)

    # B4. CLAIM-GROUNDING
    gr, gfindings = ground_claims(body, log)
    for f in gfindings:
        reasons.append(Reason("CLAIM_GROUNDING", "critical" if not f.grounded else "info", f.detail))
    if gr:
        risks.append(gr)

    a = fuse(risks=risks, reasons=reasons, sealed=False, claimed_official=claimed_official)
    return a, (time.perf_counter() - t0) * 1000


# ------------------------------------------------------------------- UI ------
st.markdown("""
<style>
  .big-verdict{padding:22px 26px;border-radius:14px;margin:14px 0}
  .v-GREEN{background:#0d3328;border:2px solid #00A870}
  .v-RED{background:#3d1418;border:2px solid #D6353B}
  .v-AMBER{background:#3d3214;border:2px solid #E9B949}
  .v-title{font-size:30px;font-weight:800;margin:0}
  .v-sub{font-size:15px;opacity:.9;margin-top:6px}
  .rcode{font-family:ui-monospace,monospace;font-size:11px;font-weight:700;
         padding:2px 7px;border-radius:4px;margin-right:8px}
  .critical{background:#5c1d22;color:#ff9095}
  .warning{background:#5c4a1d;color:#ffd76e}
  .info{background:#12503c;color:#5fe3ae}
  .hash{font-family:ui-monospace,monospace;font-size:11px;color:#00A870;word-break:break-all}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🛡️ PRAMAAN")
    st.caption("The Authenticity Layer for India's Securities Market")
    st.markdown("> ### *“If it isn't sealed, it isn't SEBI.”*")
    st.divider()
    st.markdown(
        "**SEBI Securities Market TechSprint @ GFF 2026**\n\n"
        "**Problem Statement 01 — Investor Protection**\n\n"
        "*AI-Driven Detection of Synthetic Media and Phishing Attacks in Securities Markets*"
    )
    st.divider()
    st.markdown("**Team `code hunt`** · Murali Dhar SM · Solo")
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Log size", log.size())
    c2.metric("Issuers", len(issuers.all()))
    st.caption(f"Root hash\n\n`{log.root_hash()[:32]}…`")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🔍 Investor Verifier", "🖋️ Issuer Console", "📜 Transparency Log", "ℹ️ What's Real"]
)

SAMPLES = {
    "① Genuine sealed circular":
        "Members are hereby notified of revised surveillance measures applicable to securities "
        "in the SME segment with effect from the settlement cycle commencing 20 July 2026.",
    "② Forged SEBI circular":
        "OFFICIAL SEBI CIRCULAR: Priority IPO allotment approved for select investors. "
        "Visit https://sebi-india-verify.com to claim your allotment.",
    "③ Finfluencer phishing":
        "SEBI approved! Guaranteed 40% returns. I am SEBI registered, reg no INA999999999. "
        "Only 5 seats left! Join my Telegram group now. Pay to rahul@ybl",
    "④ Perfect deepfake — ungrounded claim":
        "Reliance has announced a massive buyback at a 30% premium.",
}

# ---------------------------------------------------------------- TAB 1 ------
with tab1:
    st.subheader("Forward a suspicious message")
    st.caption(
        "The seal check runs **first** and short-circuits. Most fraud is settled "
        "before a single model loads."
    )

    cols = st.columns(4)
    for i, (label, text) in enumerate(SAMPLES.items()):
        if cols[i].button(label, use_container_width=True):
            st.session_state["content"] = text

    body = st.text_area(
        "Message, circular, caption or link",
        value=st.session_state.get("content", ""),
        height=130,
        placeholder="Paste the suspicious message here...",
    )

    if st.button("Verify", type="primary") or body:
        if body.strip():
            a, ms = verify(body)
            glyph = {"GREEN": "✓", "RED": "✕", "AMBER": "!"}[a.verdict.value]

            st.markdown(
                f"""<div class="big-verdict v-{a.verdict.value}">
                    <p class="v-title">{glyph} &nbsp;{a.verdict.value} &nbsp;·&nbsp; Trust Score {a.trust_score}/100</p>
                    <p class="v-sub">{a.headline}</p>
                </div>""",
                unsafe_allow_html=True,
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("Verdict", a.verdict.value)
            m2.metric("Trust Score", f"{a.trust_score}/100")
            m3.metric("Latency", f"{ms:.1f} ms")

            if a.sealed and a.seal_entry:
                st.success(
                    f"**Cryptographically verified.** Sealed by {a.seal_entry['issuer_name']} "
                    f"(SEBI Reg. {a.seal_entry['sebi_reg_no']}), log index #{a.seal_entry['index']}."
                )

            st.markdown("##### Why")
            for r in a.reasons:
                st.markdown(
                    f'<div style="padding:9px 0;border-top:1px solid #2a3a55">'
                    f'<span class="rcode {r.severity}">{r.code}</span>{r.message}</div>',
                    unsafe_allow_html=True,
                )

            st.caption(f"⚙️ {a.latency_note}")

            if a.verdict is Verdict.RED and any(r.code == "NOT_IN_LOG" for r in a.reasons):
                st.info(
                    "**This is the argument.** No model ran. The content claims official origin, "
                    "it is not in the transparency log, and genuine communications are sealed at "
                    "source — therefore it was never issued. *Absence of proof is proof of absence.*"
                )
            if any(r.code == "CLAIM_GROUNDING" and r.severity == "critical" for r in a.reasons):
                st.info(
                    "**This is the moat.** This message contains no phishing keywords and no "
                    "pixels to analyse. It was caught because the corporate action it announces "
                    "has no sealed filing behind it. A *flawless* deepfake still fails here."
                )

# ---------------------------------------------------------------- TAB 2 ------
with tab2:
    st.subheader("Seal an artefact at source")
    st.caption("Issuer-side. Sign, then commit the hash to the append-only transparency log.")

    opts = {f"{i.name} ({i.category})": i.did for i in issuers.all()}
    c1, c2 = st.columns(2)
    issuer_label = c1.selectbox("Issuer", list(opts))
    atype = c2.selectbox("Artefact type",
                         ["circular", "announcement", "press_release", "advisory"])
    title = st.text_input("Title", placeholder="NSE/SURV/2026/042 — ...")
    content = st.text_area("Body", height=110,
                           placeholder="The full text of the communication...")

    if st.button("Seal & commit to log", type="primary"):
        if title and content:
            entry = seal_artefact(
                registry=issuers, log=log, issuer_did=opts[issuer_label],
                data=content.encode("utf-8"), artefact_type=atype, title=title,
            )
            st.success(f"Sealed. Committed to the transparency log at index #{entry.index}.")
            st.markdown(f'**Content hash**<br><span class="hash">{entry.content_hash}</span>',
                        unsafe_allow_html=True)
            st.markdown(f'**Ed25519 signature**<br><span class="hash">{entry.signature}</span>',
                        unsafe_allow_html=True)
            st.markdown(f'**New Merkle root**<br><span class="hash">{log.root_hash()}</span>',
                        unsafe_allow_html=True)
            st.info("Now paste that exact body into the **Investor Verifier** — it will resolve "
                    "GREEN by seal check alone, with zero model inference.")
        else:
            st.warning("Title and body are both required.")

# ---------------------------------------------------------------- TAB 3 ------
with tab3:
    st.subheader("Merkle transparency log")
    c1, c2 = st.columns(2)
    c1.metric("Tree size", log.size())
    c2.metric("Log ID", "pramaan-securities-log-v1")
    st.markdown(f'**Signed tree head — root hash**<br><span class="hash">{log.root_hash()}</span>',
                unsafe_allow_html=True)

    if log.size():
        st.dataframe(
            [
                {
                    "#": e.index,
                    "Issuer": e.issuer_name,
                    "SEBI Reg.": e.sebi_reg_no,
                    "Type": e.artefact_type,
                    "Title": e.title,
                    "Content hash": e.content_hash[:20] + "…",
                    "Sealed at": e.timestamp,
                }
                for e in reversed(log.entries)
            ],
            use_container_width=True, hide_index=True,
        )

        st.markdown("##### Inclusion proof")
        st.caption(
            "Anyone can recompute the root from an audit path. Verification requires **no trust "
            "in the log operator** — including us."
        )
        idx = st.number_input("Entry index", 0, max(0, log.size() - 1), 0)
        if st.button("Generate Merkle audit path"):
            proof = log.inclusion_proof(int(idx))
            ok = verify_inclusion(
                log.entries[int(idx)].canonical(), int(idx), log.size(), proof, log.root_hash()
            )
            st.json({
                "index": int(idx),
                "tree_size": log.size(),
                "root_hash": log.root_hash(),
                "audit_path": proof,
                "verified_locally": ok,
            })
            st.success("Recomputed root matches. Inclusion proven." if ok else "Proof FAILED.")

    st.caption(
        "Append-only by construction — there is no delete and no update endpoint. In production "
        "the daily root is co-signed and anchored to a permissioned Hyperledger Fabric consortium "
        "(SEBI + exchanges + depositories), so no single operator can rewrite history."
    )

# ---------------------------------------------------------------- TAB 4 ------
with tab4:
    st.subheader("What is real, and what is not")
    st.caption("Calibration beats theatre. A SEBI jury will ask — so this table is in the product.")
    st.table([
        {"Component": "Merkle transparency log (RFC 6962) + inclusion proofs", "Status": "✅ Real, tested"},
        {"Component": "Ed25519 issuer signing & verification", "Status": "✅ Real, tested"},
        {"Component": "Seal check & tamper detection", "Status": "✅ Real, tested"},
        {"Component": "Multilingual phishing rule engine (EN/HI/TA)", "Status": "✅ Real, tested"},
        {"Component": "Typosquat / homoglyph URL analysis", "Status": "✅ Real, tested"},
        {"Component": "SEBI registry cross-reference", "Status": "⚠️ Real logic, SYNTHETIC data"},
        {"Component": "Claim-Grounding Engine", "Status": "⚠️ Real logic, seeded filings corpus"},
        {"Component": "Video deepfake detection", "Status": "❌ Not built — contributes nothing, by design"},
        {"Component": "Audio anti-spoofing", "Status": "❌ Not built — contributes nothing, by design"},
        {"Component": "CCA-India Class-3 DSC binding", "Status": "❌ Ed25519 stands in for the prototype"},
    ])
    st.warning(
        "The video and audio detectors return `available: False` and contribute **nothing** to the "
        "trust score rather than fabricating a plausible number. A detector that invents scores is "
        "worse than no detector."
    )
    st.info(
        "**Priority to 9 August:** train **one** media modality properly and report its AUC/EER. "
        "One modality with a real benchmark beats two with hand-waving."
    )
