"""Claims, not reports.

Agents append {aspect, segment_uri, assertion, confidence, evidence_refs}. Synthesis (L4)
happens over the claim table. Conflicting claims stay conflicting; nothing is averaged.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Claim(BaseModel):
    aspect: str
    segment_uri: str
    claim_type: str  # declared in the aspect manifest
    assertion: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = []  # scope() call ids, feature rows, video timestamps
    prompt_version: str = "unversioned"
    model: str = "unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ClaimStore:
    """Append-only JSONL. Swap for DuckDB when the table gets large; the contract is the row."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, claim: Claim) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(claim.model_dump_json() + "\n")

    def __iter__(self) -> Iterator[Claim]:
        if not self.path.exists():
            return iter(())
        with self.path.open(encoding="utf-8") as f:
            return iter([Claim.model_validate_json(line) for line in f if line.strip()])

    def by_segment(self, segment_uri: str) -> list[Claim]:
        return [c for c in self if c.segment_uri == segment_uri]

    def conflicts(self) -> dict[tuple[str, str], list[Claim]]:
        """Same (segment, claim_type) asserted by >1 aspect. Surfaced, never resolved here."""
        groups: dict[tuple[str, str], list[Claim]] = {}
        for c in self:
            groups.setdefault((c.segment_uri, c.claim_type), []).append(c)
        return {k: v for k, v in groups.items() if len({c.aspect for c in v}) > 1}
