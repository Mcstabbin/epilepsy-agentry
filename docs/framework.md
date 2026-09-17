# Framework

## Why a reduction pyramid

A 4-day EMU record is roughly 20-25 channels at 256-512 Hz, plus ECG, plus video. That is
tens of millions of samples per channel. No context window makes that tractable, and LLMs
reason badly about raw time series even when they fit. So the agents never touch raw
signal. They see summaries and renders, and they can zoom back in through one bounded tool.

## Layers

**L0, canonical store.** EDF+ is the archival original. It is transcoded to Zarr chunked
as (all channels x 10 s), with reads spanning the required chunks. One time authority per
recording; every other clock (video, ECG, wearables) is a measured offset from it.

**L1, continuous cheap features.** Fixed cadence (4 s window, 1 s hop), deterministic, no
models. Per-channel band power, line length, nonlinear energy, Hjorth parameters, a
quality score. Later: R-peaks -> HR/HRV, accelerometer magnitude. Lands in Parquet;
DuckDB over it is enough infrastructure. Feature blocks are written incrementally to Parquet.

**L2, candidate assembly.** Currently uses annotations and a reference line-length threshold.
Spike/sharp detection, rhythmicity, sleep staging, and artifact classification are planned.
Overlapping/touching detections cluster into candidate episodes with
onset - 30 min to offset + 30 min margins, because preictal and postictal are where the
interesting aspects live.

**L3, aspect agents.** Fanned out per candidate. Only works because L1/L2 cut the problem
from samples to a smaller set of windows. The number depends on the recording.
The current runner supports candidate signal-summary aspects. Delivery of L1 features,
physiology, and video is unfinished; manifests requiring them fail explicitly.

**L4, cross-episode synthesis (planned).** Stereotypy clustering, ordering effects across the
medication taper, what differed about the events that generalized versus those that did
not. A small set of events can generate review questions, but does not establish predictive
performance or causal explanations.

## The three contracts

**Segment URI** (`segment.py`). `(recording_id, source_sha256, t0, t1, channels, montage,
filter, feature_version)`, hashed. Newly transcoded sources include an EDF fingerprint;
legacy stores do not. Full transform and prompt hashes are still needed for run provenance.

**Aspect manifest** (`aspects/*.yaml`). Declares needs, trigger, permitted claim types,
confidence semantics, prompt file, and a scope-call budget. Adding an aspect is one YAML
and one prompt.

**Scope tool** (`agents/scope.py`). `scope(segment)` returns per-channel stats and rendered
traces in supported montages using a reference FFT filter. Each window is at most 120
seconds; manifests can impose a smaller limit. Calls save a JSON evidence record, and
claims must cite IDs supplied during that invocation. Missing montage pairs fail explicitly.
These checks enforce references, not the medical correctness of an interpretation.

## Claims, not reports

Agents append `{aspect, segment_uri, claim_type, assertion, confidence, evidence_refs}`.
Synthesis reads the table. Conflicts are surfaced (`ea conflicts`), never averaged.

## Two planned review roles

- **artifact_adversary**: tries to explain every candidate as movement, electrode pop,
  EMG, sweat, or line noise. Its conclusions also require validation and review.
- **report_reconciler**: diffs pipeline claims against the formal read. The disagreements
  are the questions for the follow-up appointment.

Their manifests and prompts ship as declarations. The missing input-delivery and
recording-trigger implementations are described in the [roadmap](roadmap.md).

## What this is not

Hypothesis generation for a conversation with an epilepsy team. Not diagnosis, not
treatment guidance, not a second opinion.
