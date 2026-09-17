"""Aspect manifests.

Each agent is a declaration, not pipeline code: what it needs, what triggers it, what
claim types it may emit, and how its confidence should be read. Adding an aspect is one
YAML file in aspects/ plus one prompt file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Trigger(BaseModel):
    when: Literal["candidate", "every_candidate", "recording", "claim"] = "candidate"
    sources_any: list[str] = []  # e.g. ["annotation:Seizure", "button"]; empty = any
    min_core_duration_s: float = 0.0
    claim_type: str | None = None  # for when="claim": fire when this claim type appears


class Needs(BaseModel):
    channels: list[str] | Literal["all"] = "all"
    montage: str = "referential"
    features: list[str] = []  # L1 columns this aspect reads
    physio: list[str] = []  # "ecg", "hr", "hrv", "accel"
    video: bool = False
    window: Literal["core", "context"] = "context"


class AspectManifest(BaseModel):
    name: str
    description: str
    version: str = "0.1"
    trigger: Trigger = Trigger()
    needs: Needs = Needs()
    claim_types: list[str] = Field(min_length=1)
    confidence_semantics: str = "0 = no support in evidence, 1 = unambiguous in scoped signal"
    prompt_file: str
    max_scope_calls: int = 8  # cost bound per invocation

    @classmethod
    def from_yaml(cls, path: Path) -> AspectManifest:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_manifests(aspects_dir: Path) -> list[AspectManifest]:
    return [AspectManifest.from_yaml(p) for p in sorted(aspects_dir.glob("*.yaml"))]
