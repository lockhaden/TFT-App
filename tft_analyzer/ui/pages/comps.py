from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget

from tft_analyzer.models.comp import CompCandidate, NormalizedComp
from tft_analyzer.ui.components import Badge, Card, Chip, EmptyState, FlowRow, IconTile, Panel, SearchBar, TileGrid, clear_layout


class CompsListPage(QWidget):
    comp_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.comps: list[NormalizedComp] = []
        self.candidates: dict[str, CompCandidate] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        toolbar = QHBoxLayout()
        self.set_filter = QComboBox()
        self.set_filter.addItems(["Set 17", "All Sets"])
        self.patch_filter = QComboBox()
        self.patch_filter.addItems(["All Patches"])
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All Tiers", "S", "A", "B", "C", "X", "Unknown"])
        self.tier_filter.currentTextChanged.connect(lambda _: self._render())
        self.patch_filter.currentTextChanged.connect(lambda _: self._render())
        self.search = SearchBar("Search comps...")
        self.search.text_changed.connect(lambda _: self._render())
        for widget in (self.set_filter, self.patch_filter, self.tier_filter):
            toolbar.addWidget(widget)
        toolbar.addWidget(self.search, stretch=1)
        root.addLayout(toolbar)

        self.summary = QLabel("Showing 0 comps")
        self.summary.setObjectName("Muted")
        root.addWidget(self.summary)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)
        self.content = QWidget()
        self.list_layout = QVBoxLayout(self.content)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.scroll.setWidget(self.content)

    def update_comps(self, comps: list[NormalizedComp]) -> None:
        self.comps = comps
        patches = sorted({comp.patch_label for comp in comps if comp.patch_label}, reverse=True)
        current = self.patch_filter.currentText()
        self.patch_filter.blockSignals(True)
        self.patch_filter.clear()
        self.patch_filter.addItem("All Patches")
        self.patch_filter.addItems(patches)
        if current in ["All Patches", *patches]:
            self.patch_filter.setCurrentText(current)
        self.patch_filter.blockSignals(False)
        self._render()

    def update_candidates(self, candidates: list[CompCandidate]) -> None:
        self.candidates = {candidate.name: candidate for candidate in candidates}
        self._render()

    def _filtered(self) -> list[NormalizedComp]:
        query = self.search.text().strip().lower()
        tier = self.tier_filter.currentText()
        patch = self.patch_filter.currentText()
        rows: list[NormalizedComp] = []
        for comp in self.comps:
            haystack = " ".join([comp.name, comp.playstyle, comp.tier, *comp.core_units, *comp.tags]).lower()
            if query and query not in haystack:
                continue
            if tier != "All Tiers":
                if tier == "Unknown" and comp.tier:
                    continue
                if tier != "Unknown" and comp.tier != tier:
                    continue
            if patch != "All Patches" and comp.patch_label != patch:
                continue
            rows.append(comp)
        return rows

    def _render(self) -> None:
        clear_layout(self.list_layout)
        rows = self._filtered()
        self.summary.setText(f"Showing {len(rows)} of {len(self.comps)} comps")
        if not rows:
            self.list_layout.addWidget(EmptyState("No comps found", "Try another filter or refresh TFT Academy data."))
            self.list_layout.addStretch()
            return
        for index, comp in enumerate(rows, start=1):
            self.list_layout.addWidget(self._comp_card(index, comp))
        self.list_layout.addStretch()

    def _comp_card(self, index: int, comp: NormalizedComp) -> Card:
        card = Card()
        candidate = self.candidates.get(comp.name)
        top = QHBoxLayout()
        top.addWidget(QLabel(str(index)))
        top.addWidget(Badge(comp.tier or "-", "#f5c84c" if comp.tier in {"S", "A"} else "#8d75ff"))
        name = QLabel(comp.name)
        name.setStyleSheet("font-size: 14px; font-weight: 800;")
        top.addWidget(name, stretch=1)
        top.addWidget(QLabel(comp.playstyle or "Unknown style"))
        score = QLabel(f"{candidate.score:.0f}" if candidate else "-")
        score.setObjectName("AccentText")
        top.addWidget(QLabel("Fit"))
        top.addWidget(score)
        view = QPushButton("View")
        view.clicked.connect(lambda _=False, c=comp: self.comp_selected.emit(c))
        top.addWidget(view)
        card.layout.addLayout(top)
        unit_row = FlowRow()
        unit_row.set_items([IconTile(unit) for unit in comp.core_units[:10]] or [Chip("Units unknown")])
        card.layout.addWidget(unit_row)
        tags = FlowRow()
        tags.set_items([Chip(tag) for tag in comp.tags[:4]] or [Chip(comp.source)])
        card.layout.addWidget(tags)
        return card


class CompDetailsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.comp: NormalizedComp | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        header = Card()
        top = QHBoxLayout()
        self.name_label = QLabel("Select a comp")
        self.name_label.setStyleSheet("font-size: 18px; font-weight: 900;")
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("Muted")
        self.meta_label.setWordWrap(True)
        self.meta_label.setMinimumWidth(0)
        top.addWidget(self.name_label, stretch=1)
        self.tier_badge = Badge("-", "#8d75ff")
        top.addWidget(self.tier_badge)
        header.layout.addLayout(top)
        header.layout.addWidget(self.meta_label)
        root.addWidget(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)
        self.overview = QWidget()
        self.overview_layout = QGridLayout(self.overview)
        self.overview_layout.setContentsMargins(12, 12, 12, 12)
        self.overview_layout.setSpacing(12)
        self._add_scroll_tab(self.overview, "Overview")
        self.items_tab = QWidget()
        self.items_layout = QVBoxLayout(self.items_tab)
        self._add_scroll_tab(self.items_tab, "Items")
        self.augments_tab = QWidget()
        self.augments_layout = QVBoxLayout(self.augments_tab)
        self._add_scroll_tab(self.augments_tab, "Augments")
        self.plan_tab = QWidget()
        self.plan_layout = QVBoxLayout(self.plan_tab)
        self._add_scroll_tab(self.plan_tab, "Plan")

        self.core_card = Card("Core Units")
        self.core_grid = TileGrid(columns=10)
        self.core_card.layout.addWidget(self.core_grid)
        self.flex_card = Card("Flex Units")
        self.flex_grid = TileGrid(columns=10)
        self.flex_card.layout.addWidget(self.flex_grid)
        self.board_card = Card("Positioning")
        self.board_grid = TileGrid(columns=7)
        self.board_card.layout.addWidget(self.board_grid)
        self.notes_card = Card("Notes")
        self.notes_layout = QVBoxLayout()
        self.notes_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_card.layout.addLayout(self.notes_layout)
        self.overview_layout.addWidget(self.core_card, 0, 0)
        self.overview_layout.addWidget(self.flex_card, 1, 0)
        self.overview_layout.addWidget(self.board_card, 0, 1, 2, 1)
        self.overview_layout.addWidget(self.notes_card, 0, 2, 2, 1)
        self.overview_layout.setColumnStretch(0, 2)
        self.overview_layout.setColumnStretch(1, 2)
        self.overview_layout.setColumnStretch(2, 1)

    def _add_scroll_tab(self, widget: QWidget, title: str) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumSize(0, 0)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        self.tabs.addTab(scroll, title)

    def update_comp(self, comp: NormalizedComp | None) -> None:
        self.comp = comp
        if comp is None:
            self.name_label.setText("Select a comp")
            self.meta_label.setText("Choose a comp from the list.")
            self.core_grid.set_tiles([])
            self.flex_grid.set_tiles([])
            self.board_grid.set_tiles([])
            return
        self.name_label.setText(comp.name)
        self.tier_badge.setText(comp.tier or "-")
        self.meta_label.setText(f"{comp.playstyle or 'Unknown style'} | Patch {comp.patch_label or 'unknown'} | Confidence {comp.parse_confidence:.2f}")
        self.core_grid.set_tiles([IconTile(unit) for unit in comp.core_units] or [Chip("Unknown")])
        self.flex_grid.set_tiles([IconTile(unit) for unit in comp.optional_units] or [Chip("Unknown")])
        self.board_grid.set_tiles([IconTile(unit) for unit in comp.core_units[:28]] + [IconTile("", False) for _ in range(max(0, 28 - len(comp.core_units[:28])))])
        self._render_list(self.items_layout, [("Carry items", comp.carry_items), ("Tank items", comp.tank_items)])
        self._render_list(self.augments_layout, [("Augments", comp.augment_suggestions)])
        self._render_list(self.plan_layout, [("Stage notes", comp.stage_notes), ("Tags", comp.tags), ("Source", [comp.source_url])])
        clear_layout(self.notes_layout)
        for note in comp.stage_notes[:8] or ["No stage notes parsed from source."]:
            label = QLabel(note)
            label.setWordWrap(True)
            self.notes_layout.addWidget(label)
        self.notes_layout.addStretch()

    @staticmethod
    def _render_list(layout: QVBoxLayout, sections: list[tuple[str, list[str]]]) -> None:
        clear_layout(layout)
        for title, values in sections:
            card = Card(title)
            row = FlowRow()
            row.set_items([IconTile(value) if len(value) < 24 else Chip(value) for value in values] or [Chip("Unknown")])
            card.layout.addWidget(row)
            layout.addWidget(card)
        layout.addStretch()


def group_comps_by_tier(comps: list[NormalizedComp]) -> dict[str, list[NormalizedComp]]:
    grouped: dict[str, list[NormalizedComp]] = defaultdict(list)
    for comp in comps:
        grouped[comp.tier or "Unknown"].append(comp)
    return grouped
