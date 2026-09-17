"""L1: continuous cheap features.

Fixed cadence, deterministic, no models. Runs once over the whole recording and lands
in Parquet. DuckDB over those files is enough infrastructure at EMU scale.

Reference implementation only. If the aspects are mostly preictal, this set needs to
grow (e.g. longer windows, spectral slope, synchrony/phase-locking, autonomic coupling).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel

from ..store import CanonicalStore

BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 70.0),
}


class L1Config(BaseModel):
    window_s: float = 4.0
    hop_s: float = 1.0
    version: str = "l1-v0"


def _band_power(x: np.ndarray, sfreq: float) -> dict[str, np.ndarray]:
    n = x.shape[-1]
    freqs = np.fft.rfftfreq(n, d=1.0 / sfreq)
    psd = np.abs(np.fft.rfft(x * np.hanning(n), axis=-1)) ** 2 / n
    out = {}
    for name, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        out[f"bp_{name}"] = psd[..., m].sum(axis=-1)
    out["bp_total"] = psd[..., (freqs >= 0.5) & (freqs < 70)].sum(axis=-1)
    return out


def _hjorth(x: np.ndarray) -> dict[str, np.ndarray]:
    d1 = np.diff(x, axis=-1)
    d2 = np.diff(d1, axis=-1)
    v0, v1, v2 = x.var(axis=-1) + 1e-12, d1.var(axis=-1) + 1e-12, d2.var(axis=-1) + 1e-12
    mobility = np.sqrt(v1 / v0)
    complexity = np.sqrt(v2 / v1) / mobility
    return {"hjorth_activity": v0, "hjorth_mobility": mobility, "hjorth_complexity": complexity}


def _window_features(x: np.ndarray, sfreq: float) -> dict[str, np.ndarray]:
    """x: channels x samples for one window. Returns per-channel feature arrays."""
    f: dict[str, np.ndarray] = {}
    f.update(_band_power(x, sfreq))
    f.update(_hjorth(x))
    f["line_length"] = np.abs(np.diff(x, axis=-1)).sum(axis=-1)
    # Teager-Kaiser nonlinear energy
    f["nonlinear_energy"] = (x[:, 1:-1] ** 2 - x[:, :-2] * x[:, 2:]).mean(axis=-1)
    # crude quality score: saturation / flatline -> low quality
    amp = np.ptp(x, axis=-1)
    f["quality"] = np.clip(1.0 - (amp > 500e-6) - (amp < 1e-7), 0, 1).astype(float)
    return f


def compute_l1(store: CanonicalStore, out_path: Path, cfg: L1Config | None = None) -> Path:
    cfg = cfg or L1Config()
    sf = store.sfreq
    win, hop = int(cfg.window_s * sf), int(cfg.hop_s * sf)
    eeg = store.root["eeg"]
    _n_ch, n = eeg.shape
    rows = []
    # read in blocks of 60 windows to bound memory while staying chunk-friendly
    block_n = hop * 60 + win
    for start in range(0, n - win, hop * 60):
        blk = np.asarray(eeg[:, start : start + block_n], dtype=np.float64)
        for w0 in range(0, blk.shape[1] - win + 1, hop):
            x = blk[:, w0 : w0 + win]
            t0 = (start + w0) / sf
            feats = _window_features(x, sf)
            for ci, ch in enumerate(store.ch_names):
                row = {
                    "recording_id": store.recording_id,
                    "t0": t0,
                    "t1": t0 + cfg.window_s,
                    "channel": ch,
                    "feature_version": cfg.version,
                }
                row.update({k: float(v[ci]) for k, v in feats.items()})
                rows.append(row)
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return out_path
