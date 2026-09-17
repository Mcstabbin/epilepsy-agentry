"""L3 runner: fan an aspect out over candidates.

The LLM call is behind a single seam (`AgentBackend.complete`) so you can plug in any
provider, or a recorded/fake backend for tests. The runner enforces the manifest's
scope-call budget and only accepts claims whose type the manifest declared.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from ..claims import Claim, ClaimStore
from ..detectors import Candidate
from ..store import CanonicalStore
from .manifest import AspectManifest
from .scope import scope

SYSTEM_PREAMBLE = """You are one aspect agent in a pool analysing a personal EEG monitoring
record. You see only derived summaries and rendered images of the segment you were given.
You may request up to {budget} scope() calls by replying with JSON
{{"scope": {{"t0": <s>, "t1": <s>, "montage": "<referential|bipolar_longitudinal|average>"}}}}.
When done, reply with JSON {{"claims": [{{"claim_type": ..., "assertion": ..., "confidence": 0-1,
"evidence_refs": [scope call ids]}}]}}. Allowed claim_types: {claim_types}.
Confidence semantics: {conf}. Do not diagnose. Do not recommend treatment. Assert only what
the scoped evidence supports."""


class AgentBackend(Protocol):
    def complete(self, system: str, messages: list[dict]) -> str: ...


def _triggers(m: AspectManifest, c: Candidate) -> bool:
    t = m.trigger
    if t.when == "every_candidate":
        return True
    if t.when != "candidate":
        return False
    if c.core.duration < t.min_core_duration_s:
        return False
    return not t.sources_any or any(s in c.sources for s in t.sources_any)


def run_aspect(
    manifest: AspectManifest,
    candidates: list[Candidate],
    store: CanonicalStore,
    backend: AgentBackend,
    claims: ClaimStore,
    render_dir: Path,
    model_name: str = "unknown",
) -> int:
    prompt = Path(manifest.prompt_file).read_text(encoding="utf-8")
    system = SYSTEM_PREAMBLE.format(
        budget=manifest.max_scope_calls,
        claim_types=manifest.claim_types,
        conf=manifest.confidence_semantics,
    ) + "\n\n" + prompt
    emitted = 0
    for c in candidates:
        if not _triggers(manifest, c):
            continue
        seg = c.context if manifest.needs.window == "context" else c.core
        seg = seg.model_copy(update={"montage": manifest.needs.montage})
        first = scope(store, seg, render_dir)
        messages = [{"role": "user", "content": json.dumps(
            {"candidate": c.model_dump(), "scope": first.model_dump()}, default=str)}]
        calls = 1
        while True:
            reply = backend.complete(system, messages)
            messages.append({"role": "assistant", "content": reply})
            try:
                data = json.loads(reply)
            except json.JSONDecodeError:
                messages.append({"role": "user", "content": "Reply with valid JSON only."})
                continue
            if "scope" in data and calls < manifest.max_scope_calls:
                req = data["scope"]
                s2 = seg.model_copy(update={"t0": float(req["t0"]), "t1": float(req["t1"]),
                                            "montage": req.get("montage", seg.montage)})
                r = scope(store, s2, render_dir)
                calls += 1
                messages.append({"role": "user", "content": json.dumps(r.model_dump())})
                continue
            for cl in data.get("claims", []):
                if cl.get("claim_type") not in manifest.claim_types:
                    continue
                claims.append(Claim(
                    aspect=manifest.name, segment_uri=seg.uri(), claim_type=cl["claim_type"],
                    assertion=cl["assertion"], confidence=float(cl.get("confidence", 0)),
                    evidence_refs=list(cl.get("evidence_refs", [])),
                    prompt_version=manifest.version, model=model_name,
                ))
                emitted += 1
            break
    return emitted
