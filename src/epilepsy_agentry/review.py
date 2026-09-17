"""Local, static review packets for a conversation with the care team."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .agents.scope import scope
from .claims import ClaimStore
from .detectors import Candidate
from .segment import Segment
from .store import CanonicalStore

QUESTIONS = [
    "Which marked events did the clinical team confirm as seizures, and which were other events?",
    "How do these times and observations compare with the final EEG report?",
    "Which findings, if any, matter for the follow-up plan?",
    "What should I record at home to make the next appointment more useful?",
    "Can we review the discharge instructions and the team's individualized seizure action plan?",
]

LIMITATIONS = [
    "Candidates are annotations or heuristic flags, not confirmed seizures.",
    "Signal statistics and reference FFT-filtered plots have no clinical validation.",
    "Only the first 30 seconds of each candidate are plotted here; context can be much longer.",
    "No medication timeline, sleep staging, ECG/HRV, wearable data, or video has been reviewed.",
    "No formal EEG report has been reconciled. Missing evidence is not a negative finding.",
    "An evidence citation verifies the source reference, not the medical correctness of a claim.",
]


def write_review(
    store: CanonicalStore,
    candidates: list[Candidate],
    output_dir: Path,
    claims_path: Path | None = None,
) -> Path:
    """Write a standalone HTML page and machine-readable JSON; no remote requests."""
    report_path = output_dir / "report.html"
    json_path = output_dir / "review.json"
    if report_path.exists() or json_path.exists():
        raise FileExistsError("review output already exists; choose a new output directory")
    if claims_path is not None and not claims_path.is_file():
        raise FileNotFoundError(f"claims file does not exist: {claims_path}")
    claims = list(ClaimStore(claims_path)) if claims_path else []
    if any(not claim.segment_uri.startswith(f"seg://{store.recording_id}/") for claim in claims):
        raise ValueError("claims include another recording; supply a recording-specific claims file")
    output_dir.mkdir(parents=True, exist_ok=True)
    synthetic = bool(store.root.attrs.get("synthetic", False))
    evidence_dir = output_dir / "evidence"
    events = []
    for candidate in candidates:
        preview = Segment.model_validate({**candidate.core.model_dump(),
                                           "t1": min(candidate.core.t1, candidate.core.t0 + 30)})
        result = scope(store, preview, evidence_dir)
        events.append({"candidate": candidate.model_dump(), "preview": result.model_dump()})
    packet = {
        "schema_version": "review-v1", "synthetic": synthetic,
        "recording_id": store.recording_id, "source_sha256": store.source_sha256,
        "duration_s": store.duration_s, "channels": store.ch_names,
        "time_authority": store.time_authority.model_dump(mode="json"),
        "events": events, "claims": [c.model_dump(mode="json") for c in claims],
        "limitations": LIMITATIONS, "questions_for_care_team": QUESTIONS,
    }
    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    esc = html.escape
    rows, cards = [], []
    for event in events:
        c, preview = event["candidate"], event["preview"]
        label = c["candidate_id"]
        t0, t1 = c["core"]["t0"], c["core"]["t1"]
        rows.append(f'<tr><td>{esc(label)}</td><td>{t0:.1f}–{t1:.1f} s</td>'
                    f'<td>{t1-t0:.1f} s</td><td>{esc(", ".join(c["sources"]))}</td>'
                    '<td>Unreviewed</td></tr>')
        call_id = preview["call_id"]
        plot = (f'<img loading="lazy" src="evidence/{call_id}_traces.png" '
                f'alt="Signal preview for {esc(label)}">') if preview["traces_png"] else ""
        cards.append(f'<details><summary>{esc(label)}: inspect signal evidence</summary>'
                     f'{plot}<p><a href="evidence/{call_id}.json">Evidence record</a></p>'
                     f'<code>{esc(preview["segment_uri"])}</code></details>')
    claim_items = []
    for claim in claims:
        refs = []
        for ref in claim.evidence_refs:
            if re.fullmatch(r"[0-9a-f]{12,16}", ref) and (evidence_dir / f"{ref}.json").is_file():
                refs.append(f'<a href="evidence/{ref}.json">{ref}</a>')
            else:
                refs.append(f'{esc(ref)} (evidence file not included)')
        claim_items.append(f'<li><strong>{esc(claim.aspect)}</strong>: {esc(claim.assertion)}'
                           f'<br><small>{esc(claim.claim_type)} · Support score '
                           f'{claim.confidence:.2f} (uncalibrated) · Model: {esc(claim.model)}</small>'
                           f'<br>Evidence: {", ".join(refs)}'
                           f'<br><code>{esc(claim.segment_uri)}</code></li>')
    banner = ("SYNTHETIC DEMO — generated signals and deterministic demonstration agents. "
              "These are not your friend's recordings.") if synthetic else (
        "PRIVATE RECORDING — local review aid. Contains sensitive health information.")
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Recording review — {esc(store.recording_id)}</title>
<style>
body {{font:16px/1.6 system-ui,sans-serif; color:#172b37; background:#f5f8fa;
       max-width:1100px; margin:32px auto; padding:0 24px;}}
h1,h2 {{line-height:1.2}} h2 {{margin-top:36px}}
.notice {{border-left:5px solid #267f88; background:#e3f1f3; padding:16px;}}
table {{width:100%; border-collapse:collapse; background:white;}}
th,td {{text-align:left; border-bottom:1px solid #d9e3e8; padding:12px;}}
.scroll {{overflow-x:auto}} details {{background:white; padding:14px; margin:12px 0;}}
summary {{cursor:pointer}} img {{width:100%; height:auto}} li {{margin:12px 0}}
code {{overflow-wrap:anywhere; font-size:12px}} a {{color:#065f74}}
@media print {{body {{background:white; margin:0}} details {{break-inside:avoid}}}}
</style></head><body>
<p class="notice">{esc(banner)}</p>
<h1>Evidence for the next care-team conversation</h1>
<p>Recording <strong>{esc(store.recording_id)}</strong> · {store.duration_s / 60:.1f} minutes ·
{len(store.ch_names)} channels · {len(events)} candidates</p>
<p>This packet organizes observations and open questions. It does not diagnose epilepsy,
predict seizures, or recommend treatment changes.</p>
<h2>Event timeline</h2><p>Times are seconds from the start of the recording.</p>
<div class="scroll"><table><thead><tr><th>Candidate</th><th>Time</th><th>Duration</th>
<th>Why included</th><th>Clinical review</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Evidence previews</h2>{''.join(cards) or '<p>No candidates found.</p>'}
<h2>Agent observations</h2><p>Support scores are not medical probabilities.</p>
<ul>{''.join(claim_items) or '<li>No agent analysis was run.</li>'}</ul>
<h2>Missing evidence and limits</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in LIMITATIONS)}</ul>
<h2>Questions to take to follow-up</h2><ol>{''.join(f'<li>{esc(x)}</li>' for x in QUESTIONS)}</ol>
<p><a href="review.json">Download the structured review packet</a></p>
</body></html>'''
    report_path.write_text(document, encoding="utf-8")
    return report_path
