# epilepsy-agentry

A framework for turning a multi-day epilepsy monitoring unit (EMU) recording into
something a pool of LLM agents can reason about without ever touching raw signal.

**This is hypothesis generation to bring back to an epilepsy team. It is not a
diagnostic tool and not a second opinion.**

## The idea in one paragraph

A 4-day EMU record is tens of millions of samples per channel plus video. Agents
cannot reason over that. So the data goes through a *reduction pyramid*: a
seekable canonical store (L0), deterministic continuous features (L1),
deterministic detectors that assemble candidate episodes (L2), aspect agents
fanned out per episode (L3), and cross-episode synthesis (L4). Agents emit
*claims*, not reports, and every claim points at a content-hashed *segment URI*
so it can be reproduced and audited. A `scope()` tool lets an agent zoom back
into the signal when it needs to look, so it never has to confabulate.

See [docs/framework.md](docs/framework.md) for the full design and
[docs/records-request.md](docs/records-request.md) for what to ask the hospital for.

## Layout

```
src/epilepsy_agentry/
  store/       L0: EDF+ -> Zarr transcode, time authority, clock offsets
  features/    L1: fixed-cadence deterministic features -> Parquet
  detectors/   L2: spikes, rhythmicity, artifact scoring, episode assembly
  agents/      L3/L4: aspect manifests, scope tool, agent runner
  claims/      shared claim store (append-only)
  segment.py   the Segment URI contract
aspects/       one YAML per aspect agent
docs/          design notes
```

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev,physio]"
ea inspect path/to/recording.edf
ea transcode path/to/recording.edf data/rec001.zarr
ea features data/rec001.zarr data/rec001_l1.parquet
```

## Data hygiene

Recordings are protected health information. `data/` and every signal or video
extension are gitignored. Do not commit them. Do not put them in prompts either;
that is what the reduction pyramid is for.

## Status

Skeleton. Contracts and interfaces are defined; the L1 feature set and the
detectors are minimal reference implementations meant to be replaced.
