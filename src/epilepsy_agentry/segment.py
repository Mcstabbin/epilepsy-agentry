"""The Segment URI contract.

Every piece of data an agent sees, and every claim an agent makes, is addressed by a
Segment. Two segments with identical fields have identical content hashes, which is
what makes agent outputs comparable across runs and lets you tell whether a finding
changed because the data changed, the feature extractor changed, or the prompt changed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Montage = Literal["referential", "bipolar_longitudinal", "bipolar_transverse", "average"]


class FilterState(BaseModel):
    highpass_hz: float | None = 0.5
    lowpass_hz: float | None = 70.0
    notch_hz: float | None = 60.0


class Segment(BaseModel):
    recording_id: str
    t0: float = Field(description="seconds from recording time authority origin")
    t1: float
    channels: tuple[str, ...] = Field(description="sorted canonical channel names")
    montage: Montage = "referential"
    filter: FilterState = FilterState()
    feature_version: str = "l1-v0"

    @field_validator("channels")
    @classmethod
    def _sorted(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(v))

    @property
    def duration(self) -> float:
        return self.t1 - self.t0

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def uri(self) -> str:
        return (
            f"seg://{self.recording_id}/{self.t0:.3f}-{self.t1:.3f}"
            f"?montage={self.montage}&fv={self.feature_version}&h={self.content_hash()}"
        )

    def with_margin(self, before: float, after: float) -> Segment:
        return self.model_copy(update={"t0": max(0.0, self.t0 - before), "t1": self.t1 + after})
