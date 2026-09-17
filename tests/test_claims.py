from epilepsy_agentry.claims import Claim, ClaimStore


def test_conflicts_surface_disagreement(tmp_path):
    cs = ClaimStore(tmp_path / "claims.jsonl")
    cs.append(Claim(aspect="a", segment_uri="seg://r/0-1", claim_type="onset_region",
                    assertion="left temporal", confidence=0.7))
    cs.append(Claim(aspect="b", segment_uri="seg://r/0-1", claim_type="onset_region",
                    assertion="right temporal", confidence=0.6))
    cs.append(Claim(aspect="a", segment_uri="seg://r/0-1", claim_type="onset_time",
                    assertion="t=0.4", confidence=0.9))
    conf = cs.conflicts()
    assert list(conf) == [("seg://r/0-1", "onset_region")]
    assert len(conf[("seg://r/0-1", "onset_region")]) == 2
