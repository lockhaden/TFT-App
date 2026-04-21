from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NormalizedComp:
    name: str
    source: str
    source_url: str
    tier: str = ""
    patch_label: str = ""
    playstyle: str = ""
    core_units: list[str] = field(default_factory=list)
    optional_units: list[str] = field(default_factory=list)
    carry_items: list[str] = field(default_factory=list)
    tank_items: list[str] = field(default_factory=list)
    augment_suggestions: list[str] = field(default_factory=list)
    stage_notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    parse_confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompCandidate:
    name: str
    source: str
    source_url: str
    score: float
    confidence: float
    fit_reasons: list[str] = field(default_factory=list)
    missing_pieces: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
