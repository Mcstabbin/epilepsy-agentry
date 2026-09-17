"""Reproducible synthetic pipeline exercise. No clinical simulation or external AI calls."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import zarr

from .agents.manifest import AspectManifest, Needs
from .agents.runner import run_aspect
from .claims import ClaimStore
from .detectors import assemble_candidates
from .features import compute_l1
from .review import write_review
from .store import CanonicalStore, TimeAuthority


class DemoBackend:
    """A deterministic backend for exercising the contract, not a trained model."""

    def __init__(self, aspect: str):
        self.aspect = aspect

    def complete(self, system: str, messages: list[dict]) -> str:
        evidence = json.loads(messages[0]["content"])["scope"]
        stats = evidence["stats"]
        if self.aspect == "demo_amplitude":
            name = max(stats, key=lambda c: stats[c]["rms_uV"])
            assertion = (f"Synthetic preview: {name} has the highest RMS amplitude among "
                         f"the displayed channels ({stats[name]['rms_uV']:.2f} uV).")
        else:
            values = [s["ptp_uV"] for s in stats.values()]
            assertion = (f"Synthetic preview: channel peak-to-peak amplitudes range from "
                         f"{min(values):.2f} to {max(values):.2f} uV. "
                         "These measurements do not establish whether an event is a seizure.")
        return json.dumps({"claims": [{"claim_type": "signal_observation",
                                      "assertion": assertion, "confidence": 1.0,
                                      "evidence_refs": [evidence["call_id"]]}]})


def run_demo(output_dir: Path, seed: int = 7) -> Path:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {output_dir}; choose a new directory")
    output_dir.mkdir(parents=True)
    sfreq, duration = 128.0, 390
    names = ["Fp1", "F7", "T3", "Fp2", "F8", "T4"]
    rng = np.random.default_rng(seed)
    t = np.arange(int(duration * sfreq)) / sfreq
    signal = rng.normal(0, 6e-6, (len(names), len(t)))
    signal += 15e-6 * np.sin(2 * np.pi * 9 * t)
    annotations = []
    for i in range(6):
        start, stop = 30 + i * 60, 38 + i * 60
        mask = (t >= start) & (t < stop)
        amplitude = 250e-6 if i == 3 else (35 + 8 * i) * 1e-6
        signal[i % len(names), mask] += amplitude * np.sin(2 * np.pi * (5 + i) * t[mask])
        annotations.append({"onset_s": float(start), "duration_s": float(stop - start),
                            "label": f"Synthetic event {i + 1}"})
    signal = signal.astype("float32")
    authority = TimeAuthority(recording_id="synthetic-demo", sfreq=sfreq,
                              origin_utc=datetime(2000, 1, 1, tzinfo=UTC))
    metadata = {"recording_id": authority.recording_id, "sfreq": sfreq, "ch_names": names,
                "time_authority": authority.model_dump(mode="json"),
                "annotations": annotations, "synthetic": True, "generator": "demo-v1", "seed": seed}
    digest = hashlib.sha256(signal.tobytes())
    digest.update(json.dumps(metadata, sort_keys=True).encode())
    metadata["source_sha256"] = digest.hexdigest()
    root = zarr.open_group(str(output_dir / "recording.zarr"), mode="w-")
    root.create_array("eeg", data=signal, chunks=(len(names), int(sfreq * 10)))
    root.attrs.update(metadata)
    store = CanonicalStore(output_dir / "recording.zarr")
    compute_l1(store, output_dir / "features.parquet")
    # Use the six explicit synthetic markers; the demo does not evaluate seizure detection.
    candidates = assemble_candidates(store)
    prompt = output_dir / "demo-prompt.txt"
    prompt.write_text("Describe the supplied synthetic signal statistics only.", encoding="utf-8")
    claims_path = output_dir / "claims.jsonl"
    claims = ClaimStore(claims_path)
    for aspect in ("demo_amplitude", "demo_range"):
        manifest = AspectManifest(
            name=aspect, description="Synthetic pipeline contract demonstration",
            needs=Needs(window="core"), claim_types=["signal_observation"],
            prompt_file=str(prompt), max_scope_calls=1, max_backend_calls=1,
        )
        run_aspect(manifest, candidates, store, DemoBackend(aspect), claims,
                   output_dir / "evidence", model_name="deterministic-demo-v1")
    return write_review(store, candidates, output_dir, claims_path)
