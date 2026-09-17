# Framework

## Why a reduction pyramid

A 4-day EMU record is roughly 20-25 channels at 256-512 Hz, plus ECG, plus video. That is
tens of millions of samples per channel. No context window makes that tractable, and LLMs
reason badly about raw time series even when they fit. So the agents never touch raw
signal. They see summaries and renders, and they can zoom back in through one bounded tool.

## Layers

**L0, canonical store.** EDF+ is the archival original. It is transcoded to Zarr chunked
as (all channels x 10 s) so a windowed read is one fetch. One time authority per
recording; every other clock (video, ECG, wearables) is a measured offset from it.

**L1, continuous cheap features.** Fixed cadence (4 s window, 1 s hop), deterministic, no
models. Per-channel band power, line length, nonlinear energy, Hjorth parameters, a
quality score. Later: R-peaks -> HR/HRV, accelerometer magnitude. Lands in Parquet;
DuckDB over it is enough infrastructure.

**L2, deterministic detectors and candidate assembly.** Spike/sharp detection, rhythmicity,
sleep staging, artifact classification. Detections cluster into candidate episodes with
onset - 30 min to offset + 30 min margins, because preictal and postictal are where the
interesting aspects live.

**L3, aspect agents.** Fanned out per candidate. Only works because L1/L2 cut the problem
from millions of samples to ~50 objects of a few KB each.

**L4, cross-episode synthesis.** Stereotypy clustering, ordering effects across the
medication taper, what differed about the events that generalized versus those that did
not. With six events this is where the real signal is.

## The three contracts

**Segment URI** (`segment.py`). `(recording_id, t0, t1, channels, montage, filter,
feature_version)`, content-hashed. Everything is addressed this way. If a finding changes
between runs you can tell whether the data, the extractor, or the prompt changed.

**Aspect manifest** (`aspects/*.yaml`). Declares needs, trigger, permitted claim types,
confidence semantics, prompt file, and a scope-call budget. Adding an aspect is one YAML
and one prompt.

**Scope tool** (`agents/scope.py`). `scope(segment)` returns per-channel stats and rendered
traces for exactly that segment, in the requested montage and filter. It is cheap,
bounded by the manifest budget, and every call has an id an agent must cite as evidence.

## Claims, not reports

Agents append `{aspect, segment_uri, claim_type, assertion, confidence, evidence_refs}`.
Synthesis reads the table. Conflicts are surfaced (`ea conflicts`), never averaged.

## Two aspects that ship regardless

- **artifact_adversary**: tries to explain every candidate as movement, electrode pop,
  EMG, sweat, or line noise. Makes the rest trustworthy enough to bring to a neurologist.
- **report_reconciler**: diffs pipeline claims against the formal read. The disagreements
  are the questions for the follow-up appointment.

## What this is not

Hypothesis generation for a conversation with an epilepsy team. Not diagnosis, not
treatment guidance, not a second opinion.
