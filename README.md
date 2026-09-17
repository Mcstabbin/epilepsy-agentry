# epilepsy-agentry

A local research framework for turning epilepsy monitoring recordings into an
evidence packet a person can discuss with their epilepsy team. The planned agent
pool gives each specialist a bounded view of the data and requires source citations.

**This is hypothesis generation to bring back to an epilepsy team. It is not a
diagnostic tool and not a second opinion.**

## The idea in one paragraph

A 4-day EMU record is tens of millions of samples per channel plus video. Agents
cannot reason over that. So the data goes through a *reduction pyramid*: a
seekable canonical store (L0), deterministic continuous features (L1),
deterministic detectors that assemble candidate episodes (L2), aspect agents
fanned out per episode (L3), and cross-episode synthesis (L4). Agents emit
*claims*, not reports, and every claim points at a content-hashed *segment URI*
so it can be inspected and audited. A bounded `scope()` tool supplies signal statistics,
plots, and persistent evidence records. Citations do not guarantee that an interpretation
is correct; clinical review and validation remain necessary.

See [docs/framework.md](docs/framework.md) for the full design and
[docs/records-request.md](docs/records-request.md) for what to ask the hospital for.
Start with [helping your friend](docs/helping-your-friend.md) for the practical workflow,
and [the roadmap](docs/roadmap.md) for the next engineering priorities.

## Layout

```
src/epilepsy_agentry/
  store/       L0: EDF+ -> Zarr transcode, time authority, clock offsets
  features/    L1: fixed-cadence deterministic features -> Parquet
  detectors/   L2: annotation and line-length candidate assembly
  agents/      L3/L4: aspect manifests, scope tool, agent runner
  claims/      shared claim store (append-only)
  segment.py   the Segment URI contract
  demo.py      reproducible synthetic recording and demonstration backends
  review.py    local HTML/JSON review packets
aspects/       one YAML per aspect agent
docs/          design notes
```

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"
ea demo --output-dir data/demo
```

Open `data/demo/report.html`. This runs six **synthetic** marked events through Zarr,
streaming Parquet features, candidate assembly, and two deterministic demonstration
agents. The report contains traces, cited observations, missing evidence, and questions
for follow-up. No API key, model download, or external service is used. It is a plumbing
test, not a seizure detector or evidence of medical benefit. To repeat it, choose a new
output directory; existing outputs are preserved.

For recordings you have permission to process:

```bash
ea inspect path/to/recording.edf
ea transcode path/to/recording.edf data/rec001.zarr
ea features data/rec001.zarr data/rec001_l1.parquet
ea candidates data/rec001.zarr --l1-parquet data/rec001_l1.parquet
ea review data/rec001.zarr data/rec001-review
```

`ea review` uses recording annotations and does not run clinical agents. All annotations
are included as candidates, including technical markers. Its plots show at most 30
seconds per event. Read the limitations in the packet before interpreting it.
Optional physiology libraries can be installed with `pip install -e ".[physio]"`;
ECG/HRV extraction and delivery to agents are still planned.

## Data hygiene

Treat recordings, annotations, reports, images, and derived features as sensitive health
data. Keep generated artifacts under the gitignored `data/` directory, work with the
person's permission, and review any export before sharing it. Gitignore is not encryption
or access control. Summaries and plots can still identify someone. No cloud backend ships;
the pluggable backend interface does not itself enforce privacy or de-identification.

## Status

Working synthetic demo and local review export, with regression tests for bounded
feature processing, EDF import, time/channel validation, scope budgets, and evidence
citations. Run `python -m pytest -q` and `python -m ruff check .`.

The L1 feature set and candidate detector remain reference implementations. The clinical
aspect YAMLs are design declarations: L1/physiology/video input delivery, recording-level
report reconciliation, model adapters, and clinical validation are unfinished. The runner
rejects those unsupported requirements explicitly instead of running without the data.
It supports candidate-triggered signal-summary aspects, as exercised by the demo.
