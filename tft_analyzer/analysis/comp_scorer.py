from __future__ import annotations

from tft_analyzer.models.comp import CompCandidate, NormalizedComp
from tft_analyzer.models.game_state import GameState


class CompScorer:
    def score(self, state: GameState, comps: list[NormalizedComp], limit: int = 5) -> list[CompCandidate]:
        candidates = [self._score_one(state, comp) for comp in comps]
        candidates.sort(key=lambda candidate: (candidate.score, candidate.confidence), reverse=True)
        return candidates[:limit]

    def _score_one(self, state: GameState, comp: NormalizedComp) -> CompCandidate:
        score = 0.0
        confidence = max(0.0, min(1.0, comp.parse_confidence))
        reasons: list[str] = []
        missing: list[str] = []

        occupied_board = sum(1 for slot in state.board_slots if slot.occupied)
        occupied_items = sum(1 for slot in state.item_slots if slot.occupied)
        aug_text = " ".join(str(augment.value or augment.raw_text) for augment in state.augments).lower()

        score += self._unit_overlap_score(comp, occupied_board, reasons, missing)
        score += self._item_fit_score(comp, occupied_items, reasons, missing)
        score += self._augment_fit_score(comp, aug_text, reasons, missing)
        score += self._level_econ_score(state, comp, reasons, missing)

        unknown_penalty = self._unknown_penalty(state, comp, missing)
        score -= unknown_penalty
        score *= 0.7 + 0.3 * confidence
        score = round(max(0.0, min(100.0, score)), 2)
        candidate_confidence = round(max(0.0, min(1.0, confidence - unknown_penalty / 100)), 3)

        return CompCandidate(
            name=comp.name,
            source=comp.source,
            source_url=comp.source_url,
            score=score,
            confidence=candidate_confidence,
            fit_reasons=reasons[:6],
            missing_pieces=missing[:8],
        )

    @staticmethod
    def _unit_overlap_score(comp: NormalizedComp, occupied_board: int, reasons: list[str], missing: list[str]) -> float:
        if not comp.core_units:
            missing.append("core units unavailable in cached comp")
            return 0.0
        expected = len(comp.core_units)
        visible_ratio = min(1.0, occupied_board / max(expected, 1))
        if occupied_board:
            reasons.append(f"visible board has {occupied_board} occupied slots against {expected} listed core units")
        else:
            missing.append("no occupied board slots detected")
        return 26.0 * visible_ratio

    @staticmethod
    def _item_fit_score(comp: NormalizedComp, occupied_items: int, reasons: list[str], missing: list[str]) -> float:
        listed_items = len(comp.carry_items) + len(comp.tank_items)
        if listed_items == 0:
            missing.append("item data unavailable in cached comp")
            return 0.0
        ratio = min(1.0, occupied_items / max(1, min(listed_items, 10)))
        if occupied_items:
            reasons.append(f"{occupied_items} visible item bench slots for {listed_items} listed items")
        else:
            missing.append("no item bench occupancy detected")
        return 18.0 * ratio

    @staticmethod
    def _augment_fit_score(comp: NormalizedComp, augment_text: str, reasons: list[str], missing: list[str]) -> float:
        if not comp.augment_suggestions:
            missing.append("augment data unavailable in cached comp")
            return 0.0
        if not augment_text.strip():
            missing.append("visible augment OCR unavailable")
            return 3.0
        hits = [augment for augment in comp.augment_suggestions if augment.lower() in augment_text]
        if hits:
            reasons.append("visible augment text overlaps cached augment suggestions")
        return min(16.0, 5.0 + len(hits) * 5.5)

    @staticmethod
    def _level_econ_score(state: GameState, comp: NormalizedComp, reasons: list[str], missing: list[str]) -> float:
        points = 0.0
        level = state.level.value if state.level.known else None
        gold = state.gold.value if state.gold.known else None
        text = " ".join([comp.playstyle, *comp.tags, *comp.stage_notes]).lower()

        if level is None:
            missing.append("level unknown")
        elif "fast 8" in text or "fast 9" in text:
            points += 9.0 if int(level) >= 7 else 3.0
            reasons.append(f"level {level} compared with cached leveling tag")
        elif "reroll" in text:
            points += 8.0 if int(level) <= 7 else 4.0
            reasons.append(f"level {level} compared with cached reroll tag")
        else:
            points += 5.0

        if gold is None:
            missing.append("gold unknown")
        else:
            gold_int = int(gold)
            if "economy" in text or "fast" in text:
                points += 7.0 if gold_int >= 30 else 3.0
            else:
                points += 4.0
            reasons.append(f"{gold_int} visible gold included in economy fit")
        return points

    @staticmethod
    def _unknown_penalty(state: GameState, comp: NormalizedComp, missing: list[str]) -> float:
        penalty = 0.0
        for name in ("stage", "hp", "gold", "level"):
            field = getattr(state, name)
            if not field.known:
                penalty += 2.0
        if not comp.core_units:
            penalty += 4.0
        if not comp.carry_items and not comp.tank_items:
            penalty += 3.0
        if comp.parse_confidence < 0.5:
            penalty += 8.0
            missing.append("cached comp parse confidence is low")
        return penalty
