from __future__ import annotations

from tft_analyzer.analysis.comp_scorer import CompScorer
from tft_analyzer.models.comp import CompCandidate, NormalizedComp
from tft_analyzer.models.game_state import GameState


class NeutralAnalyzer:
    def __init__(self) -> None:
        self.comp_scorer = CompScorer()

    def analyze(self, state: GameState, cached_comps: list[NormalizedComp] | None = None) -> list[str]:
        lines: list[str] = []
        lines.append(f"Game phase estimate: {self._phase(state)}")
        lines.append(f"Econ summary: {self._econ(state)}")
        lines.append(f"Board occupancy: {self._slots(state.board_slots, 'board')}")
        lines.append(f"Bench occupancy: {self._slots(state.bench_slots, 'bench')}")
        lines.append(f"Item summary: {self._slots(state.item_slots, 'item bench')}")

        tags = self._archetype_tags(state)
        lines.append("Possible archetype tags: " + (", ".join(tags) if tags else "unknown from visible state"))

        warnings = list(state.warnings)
        for name in ("stage", "hp", "gold", "level"):
            field = getattr(state, name)
            if not field.known or field.confidence < 0.45:
                warnings.append(f"{name} is unknown or low confidence")
        if warnings:
            lines.append("Warnings: " + "; ".join(dict.fromkeys(warnings)))
        if cached_comps:
            candidates = self.score_comps(state, cached_comps)
            lines.append(f"Cached comp candidates considered: {len(cached_comps)}")
            if candidates:
                top = candidates[0]
                lines.append(f"Top cached comp fit: {top.name} ({top.score:.1f}, confidence {top.confidence:.2f})")
        return lines

    def score_comps(self, state: GameState, cached_comps: list[NormalizedComp], limit: int = 5) -> list[CompCandidate]:
        return self.comp_scorer.score(state, cached_comps, limit)

    @staticmethod
    def _phase(state: GameState) -> str:
        if isinstance(state.stage.value, str):
            first = state.stage.value.split("-", maxsplit=1)[0]
            if first.isdigit():
                stage_num = int(first)
                if stage_num <= 2:
                    return "early game"
                if stage_num <= 4:
                    return "mid game"
                return "late game"
        return "unknown"

    @staticmethod
    def _econ(state: GameState) -> str:
        if state.gold.value is None:
            return "gold unknown"
        gold = int(state.gold.value)
        band = "low" if gold < 10 else "moderate" if gold < 30 else "high"
        return f"{gold} gold detected ({band} visible economy)"

    @staticmethod
    def _slots(slots: list, label: str) -> str:
        if not slots:
            return f"{label} slots not configured"
        occupied = sum(1 for slot in slots if slot.occupied)
        avg_conf = sum(slot.confidence for slot in slots) / len(slots)
        return f"{occupied}/{len(slots)} occupied, average confidence {avg_conf:.2f}"

    @staticmethod
    def _archetype_tags(state: GameState) -> list[str]:
        text = " ".join(str(augment.value or augment.raw_text) for augment in state.augments).lower()
        tags: list[str] = []
        keyword_map = {
            "economy": ["rich", "gold", "interest", "investment"],
            "combat": ["combat", "damage", "power", "strike"],
            "reroll": ["reroll", "refresh", "shop"],
            "vertical trait": ["crest", "crown", "heart", "emblem"],
            "items": ["item", "anvil", "artifact", "component"],
        }
        for tag, keywords in keyword_map.items():
            if any(keyword in text for keyword in keywords):
                tags.append(tag)
        return tags[:3]
