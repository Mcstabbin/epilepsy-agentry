"""L0: canonical store.

EDF+ stays as the archival original. It is transcoded to Zarr chunked as
(all channels x CHUNK_S seconds) so any windowed read is one chunk fetch.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..segment import Segment
from .timebase import TimeAuthority

CHUNK_S = 10.0


def transcode_edf_to_zarr(edf_path: Path, zarr_path: Path, recording_id: str) -> TimeAuthority:
    import mne
    import zarr

    raw = mne.io.read_raw_edf(edf_path, preload=False, verbose="error")
    sfreq = float(raw.info["sfreq"])
    chunk_n = int(CHUNK_S * sfreq)
    n_ch, n_samp = len(raw.ch_names), raw.n_times

    root = zarr.open_group(str(zarr_path), mode="w")
    data = root.create_array(
        "eeg", shape=(n_ch, n_samp), chunks=(n_ch, chunk_n), dtype="float32"
    )
    # stream through in chunk-aligned blocks to bound memory
    block = chunk_n * 60
    for start in range(0, n_samp, block):
        stop = min(start + block, n_samp)
        data[:, start:stop] = raw.get_data(start=start, stop=stop).astype("float32")

    meas = raw.info["meas_date"]
    ta = TimeAuthority(recording_id=recording_id, origin_utc=meas, sfreq=sfreq)
    root.attrs.update(
        {
            "recording_id": recording_id,
            "sfreq": sfreq,
            "ch_names": list(raw.ch_names),
            "time_authority": json.loads(ta.model_dump_json()),
        }
    )
    # annotations become the seed of the L2 event table
    ann = [
        {"onset_s": float(o), "duration_s": float(d), "label": str(l)}
        for o, d, l in zip(raw.annotations.onset, raw.annotations.duration, raw.annotations.description)
    ]
    root.attrs["annotations"] = ann
    return ta


class CanonicalStore:
    def __init__(self, zarr_path: Path):
        import zarr

        self.root = zarr.open_group(str(zarr_path), mode="r")
        self.ch_names: list[str] = list(self.root.attrs["ch_names"])
        self.sfreq: float = float(self.root.attrs["sfreq"])
        self.recording_id: str = self.root.attrs["recording_id"]
        self.time_authority = TimeAuthority.model_validate(self.root.attrs["time_authority"])

    @property
    def duration_s(self) -> float:
        return self.root["eeg"].shape[1] / self.sfreq

    def annotations(self) -> list[dict]:
        return list(self.root.attrs.get("annotations", []))

    def read(self, seg: Segment) -> tuple[np.ndarray, list[str]]:
        """Return (channels x samples) float32 for the segment, referential, unfiltered.
        Montage and filtering are applied downstream so the L0 read stays a pure fetch."""
        idx = [self.ch_names.index(c) for c in seg.channels]
        s0, s1 = int(seg.t0 * self.sfreq), int(seg.t1 * self.sfreq)
        arr = self.root["eeg"][:, s0:s1]
        return arr[idx], list(seg.channels)
