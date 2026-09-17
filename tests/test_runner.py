import importlib
import json

import pytest

from epilepsy_agentry.agents.manifest import AspectManifest, Needs
from epilepsy_agentry.agents.runner import run_aspect
from epilepsy_agentry.agents.scope import ScopeResult
from epilepsy_agentry.claims import ClaimStore
from epilepsy_agentry.detectors import assemble_candidates


@pytest.fixture
def execution(make_store, tmp_path, monkeypatch):
    store = make_store(annotations=[{"onset_s": 2, "duration_s": 8, "label": "Event"}])
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Describe evidence only.")
    manifest = AspectManifest(name="test", description="test", prompt_file=str(prompt),
                              needs=Needs(window="core", channels=["F3"]),
                              claim_types=["observation"], max_backend_calls=3,
                              max_scope_calls=2, max_scope_duration_s=5)
    scopes = []

    def fake_scope(store, seg, render_dir):
        scopes.append(seg)
        return ScopeResult(call_id=seg.content_hash(), segment_uri=seg.uri(),
                           montage=seg.montage, channel_names=list(seg.channels), stats={})

    monkeypatch.setattr(importlib.import_module("epilepsy_agentry.agents.runner"), "scope", fake_scope)
    claims = ClaimStore(tmp_path / "claims.jsonl")
    return manifest, store, assemble_candidates(store), claims, tmp_path, scopes


class Backend:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def complete(self, system, messages):
        self.calls += 1
        return self.response(messages) if callable(self.response) else self.response


def invoke(execution, backend):
    manifest, store, candidates, claims, path, _ = execution
    return run_aspect(manifest, candidates, store, backend, claims, path)


def valid_claim(messages):
    evidence = json.loads(messages[0]["content"])["scope"]["call_id"]
    return {"claim_type": "observation", "assertion": "Observed example",
            "confidence": 0.5, "evidence_refs": [evidence]}


def test_accepts_cited_claim_and_honors_initial_scope_limits(execution):
    backend = Backend(lambda messages: json.dumps({"claims": [valid_claim(messages)]}))
    assert invoke(execution, backend) == 1
    assert execution[-1][0].duration == 5
    assert execution[-1][0].channels == ("F3",)
    assert len(list(execution[3])) == 1


@pytest.mark.parametrize("reply", ["not json", "[]", '{"claims": {}}', '{"unexpected": 1}',
                                        '{"claims": [], "scope": {}}'])
def test_invalid_responses_cannot_loop_forever(execution, reply):
    backend = Backend(reply)
    with pytest.raises(RuntimeError, match="exhausted 3"):
        invoke(execution, backend)
    assert backend.calls == 3
    assert len(execution[-1]) == 1
    assert list(execution[3]) == []


@pytest.mark.parametrize("scope_request", [
    {"t0": 0, "t1": 3}, {"t0": 9, "t1": 12}, {"t0": 3, "t1": 2},
    {"t0": 2, "t1": 10}, {"t0": float("nan"), "t1": 5},
    {"t0": 2, "t1": 4, "montage": "invented"},
])
def test_rejects_out_of_scope_requests_without_reading(execution, scope_request):
    with pytest.raises(RuntimeError):
        invoke(execution, Backend(json.dumps({"scope": scope_request})))
    assert len(execution[-1]) == 1


@pytest.mark.parametrize("change", [
    {"evidence_refs": ["invented"]}, {"evidence_refs": []},
    {"claim_type": "diagnosis"}, {"confidence": float("nan")}, {"confidence": 2},
])
def test_invalid_claim_batch_writes_nothing(execution, change):
    def response(messages):
        claim = valid_claim(messages)
        return json.dumps({"claims": [claim, {**claim, **change}]})
    with pytest.raises(RuntimeError):
        invoke(execution, Backend(response))
    assert list(execution[3]) == []


def test_initial_scope_counts_against_budget(execution):
    execution[0].max_scope_calls = 1
    with pytest.raises(RuntimeError, match="scope budget exhausted"):
        invoke(execution, Backend('{"scope": {"t0": 2, "t1": 4}}'))
    assert len(execution[-1]) == 1


def test_can_scope_then_finish(execution):
    def respond(messages):
        if len(messages) == 1:
            return '{"scope": {"t0": 3, "t1": 4}}'
        claim = valid_claim(messages)
        claim["evidence_refs"] = [json.loads(messages[-1]["content"])["call_id"]]
        return json.dumps({"claims": [claim]})
    assert invoke(execution, Backend(respond)) == 1
    assert len(execution[-1]) == 2


def test_missing_modalities_fail_before_backend(execution):
    execution[0].needs.physio = ["ecg"]
    backend = Backend('{"claims": []}')
    with pytest.raises(NotImplementedError, match="not yet wired"):
        invoke(execution, backend)
    assert backend.calls == 0
    assert execution[-1] == []
