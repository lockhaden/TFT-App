from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class FieldValue:
    value: Any = None
    confidence: float = 0.0
    source: str = "unknown"
    raw_text: str = ""

    @property
    def known(self) -> bool:
        return self.value is not None


@dataclass
class SlotState:
    index: int
    occupied: bool
    confidence: float
    bbox: list[int]
    kind: str


@dataclass
class GameState:
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "unknown"
    screenshot_size: list[int] = field(default_factory=list)
    stage: FieldValue = field(default_factory=FieldValue)
    hp: FieldValue = field(default_factory=FieldValue)
    gold: FieldValue = field(default_factory=FieldValue)
    level: FieldValue = field(default_factory=FieldValue)
    augments: list[FieldValue] = field(default_factory=list)
    board_slots: list[SlotState] = field(default_factory=list)
    bench_slots: list[SlotState] = field(default_factory=list)
    item_slots: list[SlotState] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
