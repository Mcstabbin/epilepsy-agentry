"""L2: candidate episode assembly.

Detections (annotations, button presses, feature-threshold crossings) are clustered
into candidate episodes with generous context margins. Candidates include technical
markers and are not confirmed seizures. Separate events are preserved by default;
overlapping or touching seeds merge.
"""

from __future__ import annotations

import math

import duckdb
from pydantic import BaseModel

from ..segment import Segment
from ..store import CanonicalStore

PRE_MARGIN_S = 30 * 60
POST_MARGIN_S = 30 * 60
MERGE_GAP_S = 0.0


class Candidate(BaseModel):
    candidate_id: str
    core: Segment  # the detected event itself
    context: Segment  # core with pre/post margins
    sources: list[str]  # what triggered it: "annotation:Seizure", "button", "l1:line_length"
    labels: list[str] = []


def _annotation_seeds(store: CanonicalStore) -> list[tuple[float, float, str]]:
    return [
        (a["onset_s"], a["onset_s"] + max(a["duration_s"], 1.0), "annotation:" + a["label"])
        for a in store.annotations()
    ]


def _feature_seeds(
    l1_parquet: str, store: CanonicalStore, z: float = 6.0,
) -> list[tuple[float, float, str]]:
    """Windows where median-across-channels line_length exceeds z robust-SDs of the record."""
    q = """
    with per_win as (
      select t0, t1, median(line_length) as ll from read_parquet(?)
      where quality > 0.5 and recording_id = ? group by t0, t1
    ), stats as (
      select median(ll) as med,
             median(abs(ll - (select median(ll) from per_win))) * 1.4826 as mad
      from per_win
    )
    select t0, t1 from per_win, stats where (ll - med) / nullif(mad, 0) > ? order by t0
    """
    with duckdb.connect() as con:
        if store.source_sha256 is not None:
            columns = con.execute("select * from read_parquet(?) limit 0", [l1_parquet]).description
            if "source_sha256" not in {column[0] for column in columns}:
                raise ValueError("feature file has no source fingerprint; recompute features")
            fingerprints = con.execute(
                "select distinct source_sha256 from read_parquet(?) where recording_id = ?",
                [l1_parquet, store.recording_id],
            ).fetchall()
            if any(value != store.source_sha256 for (value,) in fingerprints):
                raise ValueError("feature source fingerprint does not match the recording")
        rows = con.execute(q, [l1_parquet, store.recording_id, z]).fetchall()
    return [(t0, t1, "l1:line_length") for t0, t1 in rows]


def assemble_candidates(
    store: CanonicalStore, l1_parquet: str | None = None, merge_gap_s: float = MERGE_GAP_S,
) -> list[Candidate]:
    if not math.isfinite(merge_gap_s) or merge_gap_s < 0:
        raise ValueError("merge_gap_s must be finite and nonnegative")
    seeds = _annotation_seeds(store)
    if l1_parquet:
        seeds += _feature_seeds(l1_parquet, store)
    seeds = [(max(0.0, t0), min(t1, store.duration_s), src) for t0, t1, src in seeds
             if math.isfinite(t0) and math.isfinite(t1) and t1 > 0 and t0 < store.duration_s
             and t1 > t0]
    seeds.sort()
    merged: list[tuple[float, float, list[str]]] = []
    for t0, t1, src in seeds:
        if merged and t0 - merged[-1][1] <= merge_gap_s:
            m = merged[-1]
            merged[-1] = (m[0], max(m[1], t1), m[2] + [src])
        else:
            merged.append((t0, t1, [src]))
    chans = tuple(store.ch_names)
    out = []
    for i, (t0, t1, srcs) in enumerate(merged):
        core = Segment(recording_id=store.recording_id, source_sha256=store.source_sha256,
                       t0=t0, t1=t1, channels=chans)
        ctx = core.with_margin(PRE_MARGIN_S, POST_MARGIN_S)
        ctx = ctx.model_copy(update={"t1": min(ctx.t1, store.duration_s)})
        out.append(
            Candidate(
                candidate_id=f"{store.recording_id}-c{i:03d}",
                core=core,
                context=ctx,
                sources=sorted(set(srcs)),
            )
        )
    return out
