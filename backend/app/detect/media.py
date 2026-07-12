"""
PRAMAAN Shield — video and audio channels.

READ THIS BEFORE THE JURY ROUND.

These are honest stubs. They return `available: False` and contribute NOTHING to
the trust score until the weights are in place. They do not fabricate a
plausible-looking number.

That is deliberate. A detector that invents scores is worse than no detector,
and a SEBI jury will ask you to show the benchmark. Ship the seal check — which
is real, deterministic, and already working — and be straight about what is not
built yet. Calibration beats theatre.

WHAT TO BUILD BY 9 AUGUST
-------------------------
Pick ONE of video or audio and do it properly. Both, done badly, is worse than
one, done well.

Video (recommended — it is what the problem statement leads with):
  - Backbone:   EfficientNet-B4 or Xception on face crops (RetinaFace for detection)
  - Train/eval: FaceForensics++ (c23), Celeb-DF v2, DFDC preview
  - Report:     AUC and EER, plus FPR at your chosen operating threshold
  - Watch out:  WhatsApp re-encodes video hard. Train on compressed variants or
                your numbers will not survive contact with the demo.

Audio:
  - Backbone:   AASIST or RawNet2 over wav2vec2 embeddings
  - Train/eval: ASVspoof 2021 LA + the In-the-Wild set
  - Report:     EER

rPPG pulse-liveness (the slide-5 crown jewel):
  - This is real science and it is a genuinely strong signal, but it is fragile
    under compression. Prototype it, measure it, and if it underperforms on
    WhatsApp-grade video, DEMOTE IT to a supporting signal and lead with
    lip-sync desync (SyncNet), which is far more robust to re-encoding.
  - Do not put a number on a slide you have not measured.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaResult:
    modality: str
    available: bool
    risk: float | None
    detail: str


def analyse_video(_data: bytes) -> MediaResult:
    return MediaResult(
        modality="video",
        available=False,
        risk=None,
        detail=(
            "Video deepfake model not yet loaded. Planned: EfficientNet-B4 / Xception "
            "face-forgery ensemble + SyncNet lip-sync desync, benchmarked on "
            "FaceForensics++ and Celeb-DF v2. This modality contributes nothing to the "
            "trust score until it is trained and measured."
        ),
    )


def analyse_audio(_data: bytes) -> MediaResult:
    return MediaResult(
        modality="audio",
        available=False,
        risk=None,
        detail=(
            "Audio anti-spoofing model not yet loaded. Planned: AASIST / RawNet2 over "
            "wav2vec2 embeddings, benchmarked on ASVspoof 2021 LA. This modality "
            "contributes nothing to the trust score until it is trained and measured."
        ),
    )
