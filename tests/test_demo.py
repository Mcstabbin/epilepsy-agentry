import json

import pytest
from typer.testing import CliRunner

from epilepsy_agentry.claims import Claim, ClaimStore
from epilepsy_agentry.cli import app
from epilepsy_agentry.review import write_review


def test_demo_cli_runs_without_external_services(tmp_path):
    output = tmp_path / "demo"
    result = CliRunner().invoke(app, ["demo", "--output-dir", str(output)])
    assert result.exit_code == 0, result.output
    packet = json.loads((output / "review.json").read_text())
    assert packet["synthetic"] is True
    assert len(packet["events"]) == 6
    assert len(packet["claims"]) == 12
    for claim in packet["claims"]:
        for ref in claim["evidence_refs"]:
            assert (output / "evidence" / f"{ref}.json").exists()
    report = (output / "report.html").read_text(encoding="utf-8")
    assert "SYNTHETIC DEMO" in report
    assert "Questions to take to follow-up" in report
    assert "https://" not in report
    repeat = CliRunner().invoke(app, ["demo", "--output-dir", str(output)])
    assert repeat.exit_code != 0
    assert "refusing to overwrite" in repeat.output


def test_review_escapes_recording_text(make_store, tmp_path):
    store = make_store()
    store.recording_id = '<script>alert("test")</script>'
    path = write_review(store, [], tmp_path / "review")
    content = path.read_text(encoding="utf-8")
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "No agent analysis was run" in content


def test_review_rejects_claims_from_another_recording(make_store, tmp_path):
    path = tmp_path / "claims.jsonl"
    ClaimStore(path).append(Claim(aspect="test", segment_uri="seg://another/0-1",
                                 claim_type="observation", assertion="test", confidence=0.5))
    with pytest.raises(ValueError, match="another recording"):
        write_review(make_store(), [], tmp_path / "review", path)
    assert not (tmp_path / "review").exists()
