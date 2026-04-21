from __future__ import annotations

from collections import defaultdict

from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from tft_analyzer.models.comp import NormalizedComp
from tft_analyzer.ui.components import Badge, Card, Chip, EmptyState, FlowRow, IconTile, SearchBar, TileGrid, clear_layout


SAMPLE_ITEMS = [
    "Bloodthirster",
    "Infinity Edge",
    "Spear of Shojin",
    "Guinsoo's Rageblade",
    "Hand of Justice",
    "Blue Buff",
    "Jeweled Gauntlet",
    "Last Whisper",
    "Red Buff",
    "Morellonomicon",
    "Titan's Resolve",
    "Redemption",
    "Gargoyle Stoneplate",
    "Warmog's Armor",
    "Dragon's Claw",
    "Bramble Vest",
]

SAMPLE_AUGMENTS = [
    "Cybernetic Bulk",
    "Combat Caster",
    "Portable Forge",
    "Tiny Titans",
    "Item Grab Bag",
    "Pandora's Items",
    "Heroic Grab Bag",
    "Lategame Specialist",
]


class ItemsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.items = SAMPLE_ITEMS
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        self.search = SearchBar("Search items...")
        self.search.text_changed.connect(lambda _: self._render())
        root.addWidget(self.search)
        grid = QGridLayout()
        root.addLayout(grid, stretch=1)
        self.item_card = Card("Items")
        self.item_grid = TileGrid(columns=8)
        self.item_card.layout.addWidget(self.item_grid)
        self.builder_card = Card("Item Builder")
        self.recipe_row = FlowRow()
        self.builder_card.layout.addWidget(QLabel("Recipe / build area"))
        self.builder_card.layout.addWidget(self.recipe_row)
        self.builder_card.layout.addWidget(QPushButton("View All Recipes"))
        grid.addWidget(self.item_card, 0, 0, 2, 2)
        grid.addWidget(self.builder_card, 0, 2)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(2, 1)
        self._render()

    def update_items(self, items: list[str]) -> None:
        self.items = items or SAMPLE_ITEMS
        self._render()

    def _render(self) -> None:
        query = self.search.text().lower()
        rows = [item for item in self.items if not query or query in item.lower()]
        self.item_grid.set_tiles([IconTile(item) for item in rows])
        self.recipe_row.set_items([IconTile(item) for item in rows[:5]] or [Chip("No item selected")])


class AugmentsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.augments = SAMPLE_AUGMENTS
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        controls = QHBoxLayout()
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All", "Combat", "Econ", "Items", "Hero"])
        self.search = SearchBar("Search augments...")
        self.search.text_changed.connect(lambda _: self._render())
        self.tier_filter.currentTextChanged.connect(lambda _: self._render())
        controls.addWidget(self.tier_filter)
        controls.addWidget(self.search, stretch=1)
        root.addLayout(controls)
        self.grid = TileGrid(columns=5)
        card = Card("Augments")
        card.layout.addWidget(self.grid)
        root.addWidget(card, stretch=1)
        self._render()

    def update_augments(self, augments: list[str]) -> None:
        self.augments = augments or SAMPLE_AUGMENTS
        self._render()

    def _render(self) -> None:
        query = self.search.text().lower()
        rows = [augment for augment in self.augments if not query or query in augment.lower()]
        self.grid.set_tiles([IconTile(augment) for augment in rows])


class UnitsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.units: list[str] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        controls = QHBoxLayout()
        self.cost_filter = QComboBox()
        self.cost_filter.addItems(["All Costs", "1 Cost", "2 Cost", "3 Cost", "4 Cost", "5 Cost"])
        self.cost_filter.currentTextChanged.connect(lambda _: self._render())
        self.search = SearchBar("Search units...")
        self.search.text_changed.connect(lambda _: self._render())
        controls.addWidget(self.cost_filter)
        controls.addWidget(self.search, stretch=1)
        root.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, stretch=1)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        self.scroll.setWidget(self.content)

    def update_units(self, units: list[str]) -> None:
        self.units = sorted(set(units))
        self._render()

    def _render(self) -> None:
        clear_layout(self.layout)
        if not self.units:
            self.layout.addWidget(EmptyState("No units", "Unit data appears after TFT Academy comp data is cached."))
            return
        query = self.search.text().lower()
        grouped: dict[int, list[str]] = defaultdict(list)
        for unit in self.units:
            if query and query not in unit.lower():
                continue
            cost = self._fake_cost(unit)
            selected = self.cost_filter.currentText()
            if selected != "All Costs" and not selected.startswith(str(cost)):
                continue
            grouped[cost].append(unit)
        for cost in range(1, 6):
            values = grouped.get(cost, [])
            if not values:
                continue
            card = Card(f"{cost} Cost")
            grid = TileGrid(columns=9)
            grid.set_tiles([IconTile(unit) for unit in values])
            card.layout.addWidget(grid)
            self.layout.addWidget(card)
        self.layout.addStretch()

    @staticmethod
    def _fake_cost(unit: str) -> int:
        return (sum(ord(char) for char in unit) % 5) + 1


class TierListPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.comps: list[NormalizedComp] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        self.scroll.setWidget(self.content)

    def update_comps(self, comps: list[NormalizedComp]) -> None:
        self.comps = comps
        self._render()

    def _render(self) -> None:
        clear_layout(self.layout)
        if not self.comps:
            self.layout.addWidget(EmptyState("No tier list data", "Refresh TFT Academy data to populate tiers."))
            return
        grouped: dict[str, list[NormalizedComp]] = defaultdict(list)
        for comp in self.comps:
            grouped[comp.tier or "Unknown"].append(comp)
        for tier in ["S", "A", "B", "C", "X", "Unknown"]:
            rows = grouped.get(tier, [])
            if not rows:
                continue
            card = Card(f"{tier} Tier")
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(8)
            for index, comp in enumerate(rows):
                panel = Card()
                header = QHBoxLayout()
                header.addWidget(Badge(comp.tier or "-", "#f5c84c"))
                header.addWidget(QLabel(comp.name), stretch=1)
                panel.layout.addLayout(header)
                units = FlowRow()
                units.set_items([IconTile(unit) for unit in comp.core_units[:6]] or [Chip("Unknown")])
                panel.layout.addWidget(units)
                grid.addWidget(panel, index // 3, index % 3)
            card.layout.addLayout(grid)
            self.layout.addWidget(card)
        self.layout.addStretch()


class TeamBuilderPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.units: list[str] = []
        root = QGridLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)
        self.board_card = Card("Team Builder")
        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(QPushButton("Import From Game"))
        top.addWidget(QPushButton("Save Team"))
        top.addWidget(QPushButton("Clear Board"))
        self.board_card.layout.addLayout(top)
        self.board_grid = TileGrid(columns=7)
        self.board_card.layout.addWidget(self.board_grid)
        self.pool_card = Card("Unit Pool")
        self.pool_grid = TileGrid(columns=10)
        self.pool_card.layout.addWidget(self.pool_grid)
        self.traits_card = Card("Traits")
        self.traits_card.layout.addWidget(QLabel("Trait summary will update when unit trait data is available."))
        root.addWidget(self.board_card, 0, 0, 2, 2)
        root.addWidget(self.traits_card, 0, 2)
        root.addWidget(self.pool_card, 2, 0, 1, 3)
        root.setColumnStretch(0, 2)
        self._render()

    def update_units(self, units: list[str]) -> None:
        self.units = sorted(set(units))
        self._render()

    def update_comp(self, comp: NormalizedComp | None) -> None:
        if comp:
            self.units = comp.core_units + [unit for unit in comp.optional_units if unit not in comp.core_units]
        self._render()

    def _render(self) -> None:
        board_units = self.units[:28]
        self.board_grid.set_tiles([IconTile(unit) for unit in board_units] + [IconTile("", False) for _ in range(max(0, 28 - len(board_units)))])
        self.pool_grid.set_tiles([IconTile(unit) for unit in self.units] or [Chip("No unit data")])


class MatchHistoryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        filters = QHBoxLayout()
        filters.addWidget(QComboBox())
        filters.itemAt(0).widget().addItems(["All Sets", "Current Set"])  # type: ignore[union-attr]
        filters.addWidget(QComboBox())
        filters.itemAt(1).widget().addItems(["All Placements", "Top 4", "Bottom 4"])  # type: ignore[union-attr]
        filters.addStretch()
        root.addLayout(filters)
        self.card = Card("Match History")
        self.card.layout.addWidget(EmptyState("No local match history", "The current backend does not store completed matches yet."))
        root.addWidget(self.card, stretch=1)

    def update_matches(self, matches: list[dict]) -> None:
        clear_layout(self.card.layout)
        title = QLabel("MATCH HISTORY")
        title.setObjectName("SectionTitle")
        self.card.layout.addWidget(title)
        if not matches:
            self.card.layout.addWidget(EmptyState("No local match history", "The current backend does not store completed matches yet."))
            return
        for match in matches:
            self.card.layout.addWidget(QLabel(str(match)))
