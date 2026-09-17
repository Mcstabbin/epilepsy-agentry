from epilepsy_agentry.segment import Segment


def test_hash_is_order_independent():
    a = Segment(recording_id="r", t0=0, t1=10, channels=("F3", "C3"))
    b = Segment(recording_id="r", t0=0, t1=10, channels=("C3", "F3"))
    assert a.content_hash() == b.content_hash()
    assert a.uri() == b.uri()


def test_hash_changes_with_feature_version():
    a = Segment(recording_id="r", t0=0, t1=10, channels=("F3",))
    b = a.model_copy(update={"feature_version": "l1-v1"})
    assert a.content_hash() != b.content_hash()


def test_margin_clamps_at_zero():
    s = Segment(recording_id="r", t0=5, t1=10, channels=("F3",)).with_margin(60, 60)
    assert s.t0 == 0.0 and s.t1 == 70.0
