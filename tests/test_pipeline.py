import hashlib
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from epilepsy_agentry.agents.scope import _apply_montage, _bandpass, scope
from epilepsy_agentry.detectors import assemble_candidates
from epilepsy_agentry.features import L1Config, compute_l1
from epilepsy_agentry.segment import Segment
from epilepsy_agentry.store import CanonicalStore, transcode_edf_to_zarr


@pytest.mark.parametrize("duration", [4, 64, 65, 128])
def test_features_cover_every_complete_window_once(make_store, tmp_path, duration):
    store = make_store(duration=duration)
    path = compute_l1(store, tmp_path / "features.parquet")
    frame = pd.read_parquet(path)
    assert len(frame) == (duration - 4 + 1) * len(store.ch_names)
    assert not frame.duplicated(["recording_id", "channel", "t0"]).any()
    assert frame.t0.max() == duration - 4
    assert frame.t1.max() == duration
    assert frame.source_sha256.unique().tolist() == [store.source_sha256]
    parquet = pq.ParquetFile(path)
    assert all(parquet.metadata.row_group(i).num_rows <= 60 * len(store.ch_names)
               for i in range(parquet.num_row_groups))


def test_feature_failures_are_explicit(make_store, tmp_path):
    store = make_store(duration=3)
    with pytest.raises(ValueError, match="shorter"):
        compute_l1(store, tmp_path / "short.parquet")
    with pytest.raises(ValueError, match="samples"):
        compute_l1(store, tmp_path / "tiny.parquet", L1Config(window_s=0.001))
    assert not (tmp_path / "short.parquet").exists()


def test_separate_close_annotations_stay_separate(make_store):
    store = make_store(duration=60, annotations=[
        {"onset_s": 5, "duration_s": 5, "label": "Event one"},
        {"onset_s": 20, "duration_s": 5, "label": "Event two"},
        {"onset_s": 70, "duration_s": 5, "label": "Outside recording"},
    ])
    candidates = assemble_candidates(store)
    assert len(candidates) == 2
    assert [c.core.t0 for c in candidates] == [5, 20]
    assert all(c.context.t1 == 60 for c in candidates)
    assert all(c.core.source_sha256 == store.source_sha256 for c in candidates)
    assert len(assemble_candidates(store, merge_gap_s=15)) == 1


def test_feature_path_with_quote_and_other_recordings(make_store, tmp_path):
    store = make_store()
    path = tmp_path / "friend's features.parquet"
    pd.DataFrame([
        {"recording_id": "different", "t0": t, "t1": t + 1,
         "source_sha256": store.source_sha256,
         "quality": 1, "line_length": ll}
        for t, ll in enumerate([1, 2, 3, 4, 500])
    ]).to_parquet(path)
    assert assemble_candidates(store, str(path)) == []


def test_detector_rejects_features_from_changed_recording(make_store, tmp_path):
    store = make_store()
    path = compute_l1(store, tmp_path / "features.parquet")
    store.source_sha256 = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        assemble_candidates(store, str(path))


def test_scope_identity_includes_store_fingerprint(make_store):
    first = make_store(duration=20)
    second = make_store(duration=21)
    seg = Segment(recording_id="test", t0=0, t1=2, channels=("F3",))
    a, b = scope(first, seg, render=False), scope(second, seg, render=False)
    assert a.call_id != b.call_id
    assert a.segment_uri != b.segment_uri


@pytest.mark.parametrize("updates", [
    {"recording_id": "wrong"}, {"source_sha256": "0" * 64},
    {"t1": 21}, {"t0": -1}, {"t0": 5, "t1": 2}, {"channels": ("missing",)},
])
def test_store_rejects_invalid_scope(make_store, updates):
    store = make_store()
    valid = Segment(recording_id="test", t0=0, t1=10, channels=("F3",))
    with pytest.raises(ValueError):
        store.read(valid.model_copy(update=updates))


def test_montage_does_not_silently_fall_back():
    with pytest.raises(ValueError, match="no channel pairs"):
        _apply_montage(np.ones((1, 100)), ["ECG"], "bipolar_longitudinal")


def test_notch_actually_removes_requested_frequency():
    t = np.arange(2560) / 256
    desired = np.sin(2 * np.pi * 10 * t)
    signal = desired + np.sin(2 * np.pi * 60 * t)
    actual = _bandpass(signal[None, :], 256, 0.5, 70, 60)
    np.testing.assert_allclose(actual[0], desired, atol=1e-12)


def test_scope_persists_evidence(make_store, tmp_path):
    store = make_store()
    seg = Segment(recording_id="test", source_sha256=store.source_sha256,
                  t0=0, t1=10, channels=("F3",))
    result = scope(store, seg, tmp_path / "evidence", render=False)
    assert (tmp_path / "evidence" / f"{result.call_id}.json").is_file()
    assert result.segment_uri == seg.uri()
    with pytest.raises(ValueError, match="wall-clock"):
        store.time_authority.to_wall(0)


def test_real_edf_transcode_preserves_fingerprint_and_markers(tmp_path):
    import mne

    data = np.random.default_rng(2).normal(0, 10e-6, (2, 1000))
    raw = mne.io.RawArray(data, mne.create_info(["F3", "C3"], 100, "eeg"), verbose="error")
    raw.set_meas_date(datetime(2000, 1, 1, tzinfo=UTC))
    raw.set_annotations(mne.Annotations([2], [3], ["Test marker"]))
    edf = tmp_path / "source.edf"
    raw.export(edf, fmt="edf", verbose="error")
    destination = tmp_path / "canonical.zarr"
    transcode_edf_to_zarr(edf, destination, "real-export-test")
    store = CanonicalStore(destination)
    assert store.source_sha256 == hashlib.sha256(edf.read_bytes()).hexdigest()
    assert store.annotations()[0]["label"] == "Test marker"
    assert store.duration_s == 10
    segment = Segment(recording_id=store.recording_id, source_sha256=store.source_sha256,
                      t0=0, t1=10, channels=("F3", "C3"))
    actual, names = store.read(segment)
    np.testing.assert_allclose(actual, data[[1, 0]], atol=1e-8)
    assert names == ["C3", "F3"]
    with pytest.raises(FileExistsError):
        transcode_edf_to_zarr(edf, destination, "replacement")
