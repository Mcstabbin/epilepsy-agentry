"""The scope tool.

Every agent gets scope(segment, montage, filter, render). It returns a bounded feature
summary, rendered images, and stats for exactly that segment. This is what stops agents
from confabulating about signal they cannot see: if an agent wants to check whether onset
is really left-temporal, it calls scope with a bipolar montage and looks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from ..segment import Segment
from ..store import CanonicalStore

BIPOLAR_LONGITUDINAL = [
    ("Fp1", "F7"), ("F7", "T3"), ("T3", "T5"), ("T5", "O1"),
    ("Fp1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
    ("Fp2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2"),
    ("Fp2", "F8"), ("F8", "T4"), ("T4", "T6"), ("T6", "O2"),
    ("Fz", "Cz"), ("Cz", "Pz"),
]


class ScopeResult(BaseModel):
    call_id: str
    segment_uri: str
    montage: str
    channel_names: list[str]
    stats: dict[str, dict[str, float]]  # per channel: rms, ptp, dominant_hz
    spectrogram_png: str | None = None  # path
    traces_png: str | None = None  # path
    notes: list[str] = []


def _apply_montage(x: np.ndarray, names: list[str], montage: str) -> tuple[np.ndarray, list[str]]:
    if montage == "referential":
        return x, names
    if montage == "average":
        return x - x.mean(axis=0, keepdims=True), names
    if montage == "bipolar_longitudinal":
        idx = {n.upper(): i for i, n in enumerate(names)}
        rows, out = [], []
        for a, b in BIPOLAR_LONGITUDINAL:
            if a.upper() in idx and b.upper() in idx:
                rows.append(x[idx[a.upper()]] - x[idx[b.upper()]])
                out.append(f"{a}-{b}")
        return np.vstack(rows) if rows else x, out or names
    raise ValueError(f"unknown montage {montage!r}")


def _bandpass(x: np.ndarray, sfreq: float, lo: float | None, hi: float | None) -> np.ndarray:
    n = x.shape[-1]
    f = np.fft.rfftfreq(n, 1 / sfreq)
    X = np.fft.rfft(x, axis=-1)
    m = np.ones_like(f, dtype=bool)
    if lo:
        m &= f >= lo
    if hi:
        m &= f <= hi
    X[..., ~m] = 0
    return np.fft.irfft(X, n=n, axis=-1)


def scope(
    store: CanonicalStore,
    seg: Segment,
    render_dir: Path | None = None,
    render: bool = True,
) -> ScopeResult:
    x, names = store.read(seg)
    x = x.astype(np.float64)
    x = _bandpass(x, store.sfreq, seg.filter.highpass_hz, seg.filter.lowpass_hz)
    x, names = _apply_montage(x, names, seg.montage)

    n = x.shape[-1]
    freqs = np.fft.rfftfreq(n, 1 / store.sfreq)
    psd = np.abs(np.fft.rfft(x, axis=-1)) ** 2
    band = (freqs >= 0.5) & (freqs <= 70)
    stats = {}
    for i, ch in enumerate(names):
        dom = float(freqs[band][np.argmax(psd[i][band])]) if band.any() else float("nan")
        stats[ch] = {
            "rms_uV": float(np.sqrt(np.mean(x[i] ** 2)) * 1e6),
            "ptp_uV": float(np.ptp(x[i]) * 1e6),
            "dominant_hz": dom,
        }

    call_id = hashlib.sha256((seg.uri() + str(render)).encode()).hexdigest()[:12]
    res = ScopeResult(call_id=call_id, segment_uri=seg.uri(), montage=seg.montage,
                      channel_names=names, stats=stats)

    if render and render_dir is not None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            render_dir.mkdir(parents=True, exist_ok=True)
            t = np.arange(n) / store.sfreq + seg.t0
            fig, ax = plt.subplots(figsize=(14, 0.45 * len(names) + 1))
            spacing = np.nanmedian([s["ptp_uV"] for s in stats.values()]) * 1e-6 or 1e-4
            for i, ch in enumerate(names):
                ax.plot(t, x[i] - i * spacing, lw=0.5, color="k")
            ax.set_yticks([-i * spacing for i in range(len(names))], names)
            ax.set_xlabel("s")
            ax.set_title(f"{seg.montage}  {seg.t0:.1f}-{seg.t1:.1f}s")
            p = render_dir / f"{call_id}_traces.png"
            fig.tight_layout()
            fig.savefig(p, dpi=110)
            plt.close(fig)
            res.traces_png = str(p)
        except ImportError:
            res.notes.append("matplotlib not installed; no render")
    return res
