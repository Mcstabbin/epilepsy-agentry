"""L2: candidate episode assembly.

Detections (annotations, button presses, feature-threshold crossings) are clustered
into candidate episodes with generous preictal/postictal margins. Six marked events
become 40-60 candidates once near-misses and technologist marks are included, and
that is where most of the interesting aspects live.
"""

from __future__ import annotations

import duckdb
from pydantic import BaseModel

from ..segment import Segment
from ..store import CanonicalStore

PRE_MARGIN_S = 30 * 60
POST_MARGIN_S = 30 * 60
MERGE_GAP_S = 5 * 60


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


def _feature_seeds(l1_parquet: str, z: float = 6.0) -> list[tuple[float, float, str]]:
    """Windows where median-across-channels line_length exceeds z robust-SDs of the record."""
    q = f"""
    with per_win as (
      select t0, t1, median(line_length) as ll from read_parquet('{l1_parquet}')
      where quality > 0.5 group by t0, t1
    ), stats as (
      select median(ll) as med,
             median(abs(ll - (select median(ll) from per_win))) * 1.4826 as mad
      from per_win
    )
    select t0, t1 from per_win, stats where (ll - med) / nullif(mad, 0) > {z} order by t0
    """
    return [(t0, t1, "l1:line_length") for t0, t1 in duckdb.sql(q).fetchall()]


def assemble_candidates(store: CanonicalStore, l1_parquet: str | None = None) -> list[Candidate]:
    seeds = _annotation_seeds(store)
    if l1_parquet:
        seeds += _feature_seeds(l1_parquet)
    seeds.sort()
    merged: list[tuple[float, float, list[str]]] = []
    for t0, t1, src in seeds:
        if merged and t0 - merged[-1][1] <= MERGE_GAP_S:
            m = merged[-1]
            merged[-1] = (m[0], max(m[1], t1), m[2] + [src])
        else:
            merged.append((t0, t1, [src]))
    chans = tuple(store.ch_names)
    out = []
    for i, (t0, t1, srcs) in enumerate(merged):
        core = Segment(recording_id=store.recording_id, t0=t0, t1=t1, channels=chans)
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
