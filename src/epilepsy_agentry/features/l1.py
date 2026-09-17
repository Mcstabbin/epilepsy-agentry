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
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

from ..store import CanonicalStore

BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 70.0),
}


class L1Config(BaseModel):
    window_s: float = Field(default=4.0, gt=0, allow_inf_nan=False)
    hop_s: float = Field(default=1.0, gt=0, allow_inf_nan=False)
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
    if win < 3 or hop < 1:
        raise ValueError("window must contain at least 3 samples; hop at least 1")
    eeg = store.root["eeg"]
    _n_ch, n = eeg.shape
    if n < win:
        raise ValueError("recording is shorter than one feature window")
    if out_path.exists():
        raise FileExistsError(f"refusing to overwrite {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    try:
        # Each block owns at most 60 starts. Read only the overlap those windows need.
        for start in range(0, n - win + 1, hop * 60):
            count = min(60, (n - win - start) // hop + 1)
            stop = start + (count - 1) * hop + win
            blk = np.asarray(eeg[:, start:stop], dtype=np.float64)
            rows = []
            for offset in range(count):
                w0 = offset * hop
                feats = _window_features(blk[:, w0:w0 + win], sf)
                for ci, ch in enumerate(store.ch_names):
                    row = {
                        "recording_id": store.recording_id,
                        "source_sha256": store.source_sha256 or "unknown",
                        "t0": (start + w0) / sf,
                        "t1": (start + w0 + win) / sf,
                        "channel": ch,
                        "feature_version": cfg.version,
                    }
                    row.update({k: float(v[ci]) for k, v in feats.items()})
                    rows.append(row)
            table = pa.Table.from_pandas(pd.DataFrame(rows), preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(out_path, table.schema, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    return out_path
