from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from tft_analyzer.models.comp import CompCandidate, NormalizedComp
from tft_analyzer.models.game_state import GameState
from tft_analyzer.ui.components import Badge, Card, Chip, EmptyState, FlowRow, IconTile, StatTile, TileGrid, clear_layout


class DashboardPage(QWidget):
    capture_requested = Signal()
    refresh_requested = Signal()
    auto_refresh_toggled = Signal(bool)
    overlay_toggled = Signal(bool)
    comp_open_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.comps: list[NormalizedComp] = []
        self.candidates: list[CompCandidate] = []
        self.state: GameState | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)
        body = QWidget()
        self.body_layout = QGridLayout(body)
        self.body_layout.setContentsMargins(16, 14, 16, 16)
        self.body_layout.setHorizontalSpacing(12)
        self.body_layout.setVerticalSpacing(12)
        scroll.setWidget(body)

        self.state_card = Card("Game State (Live)")
        self.stage_tile = StatTile("Stage")
        self.level_tile = StatTile("Level")
        self.gold_tile = StatTile("Gold")
        self.hp_tile = StatTile("HP")
        stat_row = QHBoxLayout()
        for tile in (self.stage_tile, self.level_tile, self.gold_tile, self.hp_tile):
            stat_row.addWidget(tile)
        self.state_card.layout.addLayout(stat_row)
        self.augment_row = FlowRow()
        self.board_grid = TileGrid(columns=10)
        self.bench_grid = TileGrid(columns=9)
        self.item_grid = TileGrid(columns=10)
        self.state_card.layout.addWidget(QLabel("Augments"))
        self.state_card.layout.addWidget(self.augment_row)
        self.state_card.layout.addWidget(QLabel("Units (Board)"))
        self.state_card.layout.addWidget(self.board_grid)
        self.state_card.layout.addWidget(QLabel("Bench"))
        self.state_card.layout.addWidget(self.bench_grid)
        self.state_card.layout.addWidget(QLabel("Items"))
        self.state_card.layout.addWidget(self.item_grid)

        control_row = QHBoxLayout()
        self.capture_button = QPushButton("Capture Once")
        self.capture_button.setObjectName("PrimaryButton")
        self.capture_button.clicked.connect(self.capture_requested)
        self.auto_refresh = QCheckBox("Auto-refresh")
        self.auto_refresh.toggled.connect(self.auto_refresh_toggled)
        self.overlay_toggle = QCheckBox("Overlay")
        self.overlay_toggle.toggled.connect(self.overlay_toggled)
        control_row.addWidget(self.capture_button)
        control_row.addWidget(self.auto_refresh)
        control_row.addWidget(self.overlay_toggle)
        control_row.addStretch()
        self.state_card.layout.addLayout(control_row)

        self.recommended_card = Card("Recommended Comps")
        self.recommended_layout = QVBoxLayout()
        self.recommended_layout.setContentsMargins(0, 0, 0, 0)
        self.recommended_layout.setSpacing(8)
        self.recommended_card.layout.addLayout(self.recommended_layout)

        self.why_card = Card("Why These Comps?")
        self.why_layout = QVBoxLayout()
        self.why_layout.setContentsMargins(0, 0, 0, 0)
        self.why_layout.setSpacing(6)
        self.why_card.layout.addLayout(self.why_layout)

        self.items_card = Card("Item Suggestions")
        self.item_suggestion_layout = QVBoxLayout()
        self.item_suggestion_layout.setContentsMargins(0, 0, 0, 0)
        self.item_suggestion_layout.setSpacing(10)
        self.items_card.layout.addLayout(self.item_suggestion_layout)

        self.data_card = Card("Data Source")
        self.data_status = QLabel("TFT Academy: unknown")
        self.data_status.setObjectName("Muted")
        self.comp_count = QLabel("Comps: 0")
        self.comp_count.setObjectName("Muted")
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.data_card.layout.addWidget(self.data_status)
        self.data_card.layout.addWidget(self.comp_count)
        self.data_card.layout.addWidget(self.refresh_button)

        self.settings_card = Card("Settings")
        self.overlay_status = QLabel("Overlay: off")
        self.overlay_status.setObjectName("Muted")
        self.settings_card.layout.addWidget(self.overlay_status)
        self.settings_card.layout.addWidget(QLabel("Live analysis is local and non-prescriptive."))

        self.body_layout.addWidget(self.state_card, 0, 0, 2, 1)
        self.body_layout.addWidget(self.recommended_card, 0, 1, 2, 2)
        self.body_layout.addWidget(self.why_card, 0, 3)
        self.body_layout.addWidget(self.items_card, 1, 3)
        self.body_layout.addWidget(self.data_card, 2, 3)
        self.body_layout.addWidget(self.settings_card, 3, 3)
        self.body_layout.setColumnStretch(0, 2)
        self.body_layout.setColumnStretch(1, 2)
        self.body_layout.setColumnStretch(2, 2)
        self.body_layout.setColumnStretch(3, 2)
        self.body_layout.setRowStretch(4, 1)

        self._render_empty()

    def update_state(self, state: GameState | None) -> None:
        self.state = state
        if state is None:
            self._render_empty()
            return
        self.stage_tile.set_value(state.stage.value if state.stage.known else "?")
        self.level_tile.set_value(state.level.value if state.level.known else "?")
        self.gold_tile.set_value(state.gold.value if state.gold.known else "?")
        self.hp_tile.set_value(state.hp.value if state.hp.known else "?")
        self.augment_row.set_items([Chip(str(augment.value or augment.raw_text or "Unknown")) for augment in state.augments[:3]] or [Chip("Unknown")])
        self.board_grid.set_tiles([IconTile(str(slot.index + 1), slot.occupied) for slot in state.board_slots])
        self.bench_grid.set_tiles([IconTile(str(slot.index + 1), slot.occupied) for slot in state.bench_slots])
        self.item_grid.set_tiles([IconTile(str(slot.index + 1), slot.occupied) for slot in state.item_slots])

    def update_comps(self, comps: list[NormalizedComp]) -> None:
        self.comps = comps
        self.comp_count.setText(f"Comps: {len(comps)}")
        if not self.candidates:
            self._render_recommendations()
            self._render_item_suggestions()

    def update_candidates(self, candidates: list[CompCandidate]) -> None:
        self.candidates = candidates
        self._render_recommendations()
        self._render_why()
        self._render_item_suggestions()

    def update_data_status(self, status: dict) -> None:
        state = str(status.get("status", "unknown"))
        finished = str(status.get("finished_at", ""))
        live = "Live" if state in {"ok", "partial"} else state
        self.data_status.setText(f"TFT Academy ({live})\nLast update: {finished or 'unknown'}")

    def set_overlay_checked(self, checked: bool) -> None:
        self.overlay_toggle.blockSignals(True)
        self.overlay_toggle.setChecked(checked)
        self.overlay_toggle.blockSignals(False)
        self.overlay_status.setText("Overlay: on" if checked else "Overlay: off")

    def _render_empty(self) -> None:
        self.stage_tile.set_value("?")
        self.level_tile.set_value("?")
        self.gold_tile.set_value("?")
        self.hp_tile.set_value("?")
        self.augment_row.set_items([Chip("Unknown")])
        self.board_grid.set_tiles([IconTile("", False) for _ in range(28)])
        self.bench_grid.set_tiles([IconTile("", False) for _ in range(9)])
        self.item_grid.set_tiles([IconTile("", False) for _ in range(10)])

    def _render_recommendations(self) -> None:
        clear_layout(self.recommended_layout)
        rows = self.candidates or [
            CompCandidate(comp.name, comp.source, comp.source_url, 0.0, comp.parse_confidence, ["cached comp"], [])
            for comp in self.comps[:3]
        ]
        if not rows:
            self.recommended_layout.addWidget(EmptyState("No cached comps", "Refresh TFT Academy data to populate recommendations."))
            return
        comp_map = {comp.name: comp for comp in self.comps}
        for index, candidate in enumerate(rows[:3], start=1):
            comp = comp_map.get(candidate.name)
            row = Card()
            line = QHBoxLayout()
            line.addWidget(QLabel(str(index)))
            line.addWidget(Badge((comp.tier if comp and comp.tier else "-")[:1] or "-", "#f5c84c"))
            title = QLabel(candidate.name)
            title.setStyleSheet("font-weight: 800; font-size: 14px;")
            line.addWidget(title, stretch=1)
            score = QLabel(f"{candidate.score:.0f}")
            score.setObjectName("AccentText")
            line.addWidget(QLabel("Fit Score"))
            line.addWidget(score)
            view = QPushButton("View")
            view.clicked.connect(lambda _=False, name=candidate.name: self.comp_open_requested.emit(name))
            line.addWidget(view)
            row.layout.addLayout(line)
            units = (comp.core_units if comp else [])[:8]
            row.layout.addWidget(FlowRow())
            row.layout.itemAt(row.layout.count() - 1).widget().set_items([IconTile(unit) for unit in units] or [Chip("Unit data unknown")])  # type: ignore[union-attr]
            reason = "; ".join(candidate.fit_reasons[:2]) if candidate.fit_reasons else (comp.playstyle if comp else "Cached comp")
            muted = QLabel(reason or "Cached comp")
            muted.setObjectName("Muted")
            row.layout.addWidget(muted)
            self.recommended_layout.addWidget(row)

    def _render_why(self) -> None:
        clear_layout(self.why_layout)
        reasons: list[str] = []
        for candidate in self.candidates[:2]:
            reasons.extend(candidate.fit_reasons[:3])
        if not reasons:
            reasons = ["Waiting for detected state", "Cached comps available for comparison"]
        for reason in reasons[:5]:
            label = QLabel(f"+ {reason}")
            label.setWordWrap(True)
            self.why_layout.addWidget(label)

    def _render_item_suggestions(self) -> None:
        clear_layout(self.item_suggestion_layout)
        source = None
        if self.candidates:
            names = {candidate.name for candidate in self.candidates[:1]}
            source = next((comp for comp in self.comps if comp.name in names), None)
        if source is None and self.comps:
            source = self.comps[0]
        if source is None:
            self.item_suggestion_layout.addWidget(EmptyState("No item data", "Cached comp item data will appear here."))
            return
        for title, items in (("Carry", source.carry_items[:8]), ("Tank", source.tank_items[:8])):
            self.item_suggestion_layout.addWidget(QLabel(title))
            row = FlowRow()
            row.set_items([IconTile(item) for item in items] or [Chip("Unknown")])
            self.item_suggestion_layout.addWidget(row)
