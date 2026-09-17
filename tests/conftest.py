import hashlib

import numpy as np
import pytest
import zarr

from epilepsy_agentry.store import CanonicalStore, TimeAuthority


@pytest.fixture
def make_store(tmp_path):
    def create(duration=20, sfreq=100, annotations=None, names=("F3", "C3")):
        data = np.random.default_rng(4).normal(0, 20e-6, (len(names), int(duration * sfreq)))
        path = tmp_path / f"store-{len(list(tmp_path.glob('store-*')))}.zarr"
        root = zarr.open_group(str(path), mode="w-")
        root.create_array("eeg", data=data.astype("float32"), chunks=(len(names), int(sfreq)))
        root.attrs.update({
            "recording_id": "test", "sfreq": sfreq, "ch_names": list(names),
            "source_sha256": hashlib.sha256(data.tobytes()).hexdigest(),
            "time_authority": TimeAuthority(recording_id="test", origin_utc=None,
                                             sfreq=sfreq).model_dump(mode="json"),
            "annotations": annotations or [],
        })
        return CanonicalStore(path)
    return create
