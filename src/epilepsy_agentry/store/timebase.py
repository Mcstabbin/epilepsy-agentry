"""One time authority per recording. Every other clock (video, ECG box, wearables)
is expressed as a measured offset from it. Clock drift between video and EEG is
real and will silently wreck event alignment if assumed away."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ClockOffset(BaseModel):
    source: str  # "video", "ecg", "wearable:oura", ...
    offset_s: float  # add to source time to get authority time
    drift_ppm: float = 0.0  # linear drift, parts per million
    measured_at_s: float = 0.0  # authority time at which offset was measured
    method: str = "unspecified"  # "sync_pulse", "button_press", "vendor_header", ...

    def to_authority(self, source_t: float) -> float:
        elapsed = source_t - (self.measured_at_s - self.offset_s)
        return source_t + self.offset_s + elapsed * self.drift_ppm * 1e-6


class TimeAuthority(BaseModel):
    recording_id: str
    origin_utc: datetime | None
    sfreq: float = Field(gt=0, allow_inf_nan=False)
    offsets: dict[str, ClockOffset] = {}

    def to_wall(self, t_s: float) -> datetime:
        if self.origin_utc is None:
            raise ValueError("recording has no known wall-clock origin")
        return datetime.fromtimestamp(self.origin_utc.timestamp() + t_s, tz=UTC)

    def to_sample(self, t_s: float) -> int:
        return round(t_s * self.sfreq)

    def from_source(self, source: str, source_t: float) -> float:
        if source not in self.offsets:
            raise KeyError(f"no clock offset registered for {source!r}")
        return self.offsets[source].to_authority(source_t)
