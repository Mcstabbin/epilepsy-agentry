"""The Segment URI contract.

Every piece of data an agent sees, and every claim an agent makes, is addressed by a
Segment. Identical fields produce identical hashes. New stores include a source-file
fingerprint; legacy stores may not. Transform and prompt provenance must be recorded
separately, and canonical stores must be treated as immutable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Montage = Literal["referential", "bipolar_longitudinal", "bipolar_transverse", "average"]


class FilterState(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    highpass_hz: float | None = Field(default=0.5, gt=0)
    lowpass_hz: float | None = Field(default=70.0, gt=0)
    notch_hz: float | None = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def ordered(self) -> FilterState:
        if (self.highpass_hz is not None and self.lowpass_hz is not None
                and self.highpass_hz >= self.lowpass_hz):
            raise ValueError("highpass_hz must be below lowpass_hz")
        return self


class Segment(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    recording_id: str = Field(min_length=1)
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    t0: float = Field(ge=0, description="seconds from recording time authority origin")
    t1: float = Field(gt=0)
    channels: tuple[str, ...] = Field(min_length=1, description="sorted canonical channel names")
    montage: Montage = "referential"
    filter: FilterState = FilterState()
    feature_version: str = "l1-v0"

    @field_validator("channels")
    @classmethod
    def _sorted(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v) or any(not c.strip() for c in v):
            raise ValueError("channels must be nonempty and unique")
        return tuple(sorted(v))

    @model_validator(mode="after")
    def ordered(self) -> Segment:
        if self.t1 <= self.t0:
            raise ValueError("t1 must be greater than t0")
        return self

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
        if before < 0 or after < 0:
            raise ValueError("margins must be nonnegative")
        return Segment.model_validate({**self.model_dump(),
                                       "t0": max(0.0, self.t0 - before), "t1": self.t1 + after})
