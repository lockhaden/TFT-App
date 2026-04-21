from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tft_analyzer.analysis.analyzer import NeutralAnalyzer
from tft_analyzer.capture.window_capture import capture_screen_region, capture_window
from tft_analyzer.config.config_manager import ConfigManager
from tft_analyzer.models.comp import CompCandidate, NormalizedComp
from tft_analyzer.models.game_state import GameState
from tft_analyzer.sources.scrape_service import ScrapeService
from tft_analyzer.storage.comp_repository import CompRepository
from tft_analyzer.ui.components import clear_layout
from tft_analyzer.ui.overlay_window import OverlayWindow
from tft_analyzer.ui.pages import (
    AugmentsPage,
    CompDetailsPage,
    CompsListPage,
    DashboardPage,
    ItemsPage,
    MatchHistoryPage,
    SettingsPage,
    TeamBuilderPage,
    TierListPage,
    UnitsPage,
)
from tft_analyzer.ui.theme import apply_theme
from tft_analyzer.vision.state_extractor import StateExtractor

LOGGER = logging.getLogger(__name__)


class ScrapeNotifier(QObject):
    finished = Signal(object, object, bool)


class MainWindow(QMainWindow):
    """Desktop shell/controller.

    UI widgets are intentionally presentation-only. Existing capture, OCR,
    analyzer, overlay, and scraper services stay here and push data into pages
    through page update methods.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        super().__init__()
        self.config_manager = config_manager
        self.extractor = StateExtractor(config_manager.data)
        self.analyzer = NeutralAnalyzer()
        self.comp_repo = CompRepository(Path("cache/tft_comps.sqlite3"))
        self.scrape_service = ScrapeService(self.comp_repo, Path("config/tft_academy_scraper.json"))
        self.overlay = OverlayWindow()

        self.current_image_bgr = None
        self.current_pixmap: QPixmap | None = None
        self.current_state: GameState | None = None
        self.current_candidates: list[CompCandidate] = []
        self.cached_comps = self.comp_repo.list_comps()
        self.capture_in_progress = False
        self.capture_count = 0
        self.last_panel_update = 0.0
        self.scrape_in_progress = False
        self.scrape_thread: threading.Thread | None = None
        self.scrape_notifier = ScrapeNotifier()
        self.scrape_notifier.finished.connect(self._finish_tft_academy_refresh)
        self.nav_buttons: dict[str, QPushButton] = {}

        self.setWindowTitle("TFT Compass")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture_once)

        self._build_shell()
        apply_theme(self)
        self._connect_pages()
        self._update_cache_status()
        self._update_comp_pages()
        self.navigate("Dashboard")
        QTimer.singleShot(500, self._auto_refresh_tft_academy_on_startup)

    def _build_shell(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 16, 12, 12)
        side_layout.setSpacing(6)
        brand = QLabel("TFT COMPASS")
        brand.setObjectName("BrandTitle")
        side_layout.addWidget(brand)
        side_layout.addSpacing(16)

        self.pages: dict[str, QWidget] = {}
        self.stack = QStackedWidget()
        self.stack.setMinimumSize(0, 0)
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.dashboard_page = DashboardPage()
        self.comps_page = CompsListPage()
        self.comp_details_page = CompDetailsPage()
        self.items_page = ItemsPage()
        self.augments_page = AugmentsPage()
        self.units_page = UnitsPage()
        self.tier_page = TierListPage()
        self.team_builder_page = TeamBuilderPage()
        self.match_history_page = MatchHistoryPage()
        self.settings_page = SettingsPage(self.config_manager.data)

        for name, page in [
            ("Dashboard", self.dashboard_page),
            ("Comps", self.comps_page),
            ("Comp Details", self.comp_details_page),
            ("Items", self.items_page),
            ("Augments", self.augments_page),
            ("Units", self.units_page),
            ("Tier List", self.tier_page),
            ("Team Builder", self.team_builder_page),
            ("Match History", self.match_history_page),
            ("Settings", self.settings_page),
        ]:
            self.pages[name] = page
            self.stack.addWidget(page)

        for name in ["Dashboard", "Comps", "Items", "Augments", "Units", "Tier List", "Team Builder", "Match History", "Settings"]:
            button = QPushButton(name)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, page_name=name: self.navigate(page_name))
            self.nav_buttons[name] = button
            side_layout.addWidget(button)
        side_layout.addStretch()
        self.sidebar_status = QLabel("TFT Academy\nunknown")
        self.sidebar_status.setObjectName("Muted")
        self.sidebar_status.setWordWrap(True)
        side_layout.addWidget(self.sidebar_status)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        topbar = QWidget()
        topbar.setObjectName("TopBar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(16, 10, 14, 10)
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("PageTitle")
        self.page_title.setMinimumWidth(0)
        self.patch_label = QLabel("Patch unknown")
        self.patch_label.setObjectName("Muted")
        self.patch_label.setMinimumWidth(0)
        self.data_label = QLabel("Data updated: unknown")
        self.data_label.setObjectName("Muted")
        self.data_label.setMinimumWidth(0)
        self.data_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.setObjectName("PrimaryButton")
        self.refresh_button.clicked.connect(self.refresh_tft_academy_data)
        top_layout.addWidget(self.page_title)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.patch_label)
        top_layout.addSpacing(18)
        top_layout.addWidget(self.data_label)
        top_layout.addStretch()
        top_layout.addWidget(self.refresh_button)
        for text, action in [("-", self.showMinimized), ("[]", self.showNormal), ("X", self.close)]:
            button = QPushButton(text)
            button.setObjectName("IconButton")
            button.clicked.connect(action)
            top_layout.addWidget(button)

        main_layout.addWidget(topbar)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(divider)
        main_layout.addWidget(self.stack, stretch=1)

        shell.addWidget(sidebar)
        shell.addWidget(main, stretch=1)
        self.setCentralWidget(root)

    def _connect_pages(self) -> None:
        self.dashboard_page.capture_requested.connect(self.capture_once)
        self.dashboard_page.refresh_requested.connect(self.refresh_tft_academy_data)
        self.dashboard_page.auto_refresh_toggled.connect(self._toggle_auto_refresh)
        self.dashboard_page.overlay_toggled.connect(self._toggle_overlay)
        self.dashboard_page.comp_open_requested.connect(self._select_comp_by_name)

        self.comps_page.comp_selected.connect(self._select_comp)

        self.settings_page.capture_requested.connect(self.capture_once)
        self.settings_page.export_requested.connect(self.export_json)
        self.settings_page.export_comps_requested.connect(self.export_comp_cache_json)
        self.settings_page.save_debug_requested.connect(self.save_debug_crops)
        self.settings_page.refresh_requested.connect(self.refresh_tft_academy_data)
        self.settings_page.overlay_toggled.connect(self._toggle_overlay)
        self.settings_page.click_through_toggled.connect(self.overlay.set_click_through)
        self.settings_page.opacity_changed.connect(lambda value: self.overlay.setWindowOpacity(value / 100))
        self.settings_page.calibration_changed.connect(lambda _: self._refresh_preview_overlay())
        self.settings_page.calibration_target_changed.connect(lambda _: self._refresh_preview_overlay())
        self.settings_page.preview.region_drawn.connect(self._save_calibrated_region)
        self.settings_page.refresh_interval.valueChanged.connect(self._update_refresh_interval)

    def navigate(self, name: str) -> None:
        if name not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[name])
        self.page_title.setText(name)
        for button_name, button in self.nav_buttons.items():
            button.blockSignals(True)
            button.setChecked(button_name == name)
            button.blockSignals(False)

    def capture_once(self) -> None:
        if self.capture_in_progress:
            return
        self.capture_in_progress = True
        is_auto = self.dashboard_page.auto_refresh.isChecked()
        self._sync_capture_config(save=not is_auto)
        try:
            capture = self._capture()
            self.capture_count += 1
            include_ocr = (
                (not is_auto)
                or (not self.settings_page.live_fast_mode.isChecked())
                or self.capture_count % max(1, self.settings_page.ocr_every.value()) == 0
            )
            previous = self.current_state
            self.current_image_bgr = capture.image_bgr
            if not is_auto or self.settings_page.preview_live.isChecked():
                self._show_preview(capture.image_bgr)
            self.current_state = self.extractor.extract(
                capture.image_bgr,
                capture.source,
                debug_dir=None,
                include_ocr=include_ocr,
            )
            if previous and not include_ocr:
                self._carry_forward_ocr(previous, self.current_state)
            self._render_analysis(lightweight=is_auto and self.settings_page.live_fast_mode.isChecked())
        except Exception as exc:
            LOGGER.exception("Capture failed")
            if not is_auto:
                QMessageBox.warning(self, "Capture failed", str(exc))
        finally:
            self.capture_in_progress = False

    def _capture(self):
        capture_cfg = self.config_manager.data.setdefault("capture", {})
        mode = capture_cfg.get("mode", "window")
        if mode == "window":
            return capture_window(capture_cfg.get("window_title_contains", "League of Legends (TM) Client"))
        if mode == "region":
            x, y, w, h = capture_cfg.get("region", [0, 0, 1920, 1080])
            return capture_screen_region([x, y, x + w, y + h])
        return capture_screen_region()

    def _show_preview(self, image_bgr) -> None:  # type: ignore[no-untyped-def]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.current_pixmap = QPixmap.fromImage(image)
        self.settings_page.preview.set_source_pixmap(self.current_pixmap, image_bgr.shape)
        self._refresh_preview_overlay()

    def _toggle_auto_refresh(self, enabled: bool) -> None:
        if enabled:
            self.capture_count = 0
            self.timer.start(self.settings_page.refresh_interval.value())
        else:
            self.timer.stop()

    def _update_refresh_interval(self, value: int) -> None:
        self.config_manager.data.setdefault("capture", {})["auto_refresh_ms"] = value
        self.config_manager.save()
        if self.dashboard_page.auto_refresh.isChecked():
            self.timer.start(value)

    def _sync_capture_config(self, save: bool = True) -> None:
        self.config_manager.data["capture"] = self.settings_page.capture_config()
        if save:
            self.config_manager.save()
        self.extractor = StateExtractor(self.config_manager.data)

    def _save_calibrated_region(self, rect: QRect) -> None:
        if self.current_image_bgr is None or self.current_pixmap is None:
            return
        preview = self.settings_page.preview
        label_size = preview.size()
        pixmap_size = self.current_pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio).size()
        offset_x = (label_size.width() - pixmap_size.width()) / 2
        offset_y = (label_size.height() - pixmap_size.height()) / 2
        scale_x = self.current_image_bgr.shape[1] / pixmap_size.width()
        scale_y = self.current_image_bgr.shape[0] / pixmap_size.height()
        x = int((rect.x() - offset_x) * scale_x)
        y = int((rect.y() - offset_y) * scale_y)
        w = int(rect.width() * scale_x)
        h = int(rect.height() * scale_y)
        image_w = self.current_image_bgr.shape[1]
        image_h = self.current_image_bgr.shape[0]
        x = max(0, min(image_w - 1, x))
        y = max(0, min(image_h - 1, y))
        w = max(1, min(image_w - x, w))
        h = max(1, min(image_h - y, h))
        bbox = [x, y, w, h]
        self.config_manager.data["base_resolution"] = [image_w, image_h]
        target = self.settings_page.calibration_target.currentText()
        if target == "board_slots":
            self._set_slot_grid(target, bbox, cols=7, rows=4, stagger=True)
        elif target == "bench_slots":
            self._set_slot_grid(target, bbox, cols=9, rows=1, stagger=False)
        elif target == "item_slots":
            self._set_slot_grid(target, bbox, cols=1, rows=10, stagger=False)
        else:
            self.config_manager.set_region(target, bbox)
        self.extractor = StateExtractor(self.config_manager.data)
        self._refresh_preview_overlay()
        QMessageBox.information(self, "Calibration saved", f"Saved {target} region: {bbox}")

    def _set_slot_grid(self, name: str, bbox: list[int], cols: int, rows: int, stagger: bool) -> None:
        x, y, w, h = bbox
        cell_w = w / max(cols, 1)
        cell_h = h / max(rows, 1)
        slots: list[dict[str, list[int]]] = []
        for row in range(rows):
            for col in range(cols):
                offset = cell_w / 2 if stagger and row % 2 else 0
                slots.append(
                    {
                        "bbox": [
                            round(x + col * cell_w + offset),
                            round(y + row * cell_h),
                            max(1, round(cell_w * 0.82)),
                            max(1, round(cell_h * 0.82)),
                        ]
                    }
                )
        self.config_manager.get_regions()[name] = slots
        self.config_manager.save()

    def _refresh_preview_overlay(self) -> None:
        image_shape = self.current_image_bgr.shape if self.current_image_bgr is not None else None
        self.settings_page.preview.set_calibration_context(
            self.config_manager.get_regions(),
            self.config_manager.data.get("base_resolution", [1920, 1080]),
            image_shape,
            self.settings_page.calibration_target.currentText(),
            self.settings_page.calibration.isChecked(),
        )

    def refresh_tft_academy_data(self) -> None:
        self._start_tft_academy_refresh(show_errors=True)

    def _auto_refresh_tft_academy_on_startup(self) -> None:
        self._start_tft_academy_refresh(show_errors=False)

    def _start_tft_academy_refresh(self, show_errors: bool) -> None:
        if self.scrape_in_progress:
            return
        self.scrape_in_progress = True
        self.refresh_button.setEnabled(False)
        self.dashboard_page.refresh_button.setEnabled(False)
        self.data_label.setText("Data refresh running...")
        self.scrape_thread = threading.Thread(target=self._run_tft_academy_refresh, args=(show_errors,), daemon=True)
        self.scrape_thread.start()

    def _run_tft_academy_refresh(self, show_errors: bool) -> None:
        try:
            result = self.scrape_service.refresh_tft_academy()
            self.scrape_notifier.finished.emit(result, None, show_errors)
        except Exception as exc:
            LOGGER.exception("TFT Academy scrape worker failed")
            self.scrape_notifier.finished.emit(None, exc, show_errors)

    def _finish_tft_academy_refresh(self, result, exc, show_errors: bool) -> None:  # type: ignore[no-untyped-def]
        self.scrape_in_progress = False
        self.refresh_button.setEnabled(True)
        self.dashboard_page.refresh_button.setEnabled(True)
        self.scrape_thread = None
        if exc is not None:
            self.comp_repo.record_scrape_run("tft_academy", "failed", str(exc), 0, datetime.now().isoformat())
            if show_errors:
                QMessageBox.warning(self, "Scrape failed", str(exc))
        self.cached_comps = self.comp_repo.list_comps()
        self._update_cache_status()
        self._update_comp_pages()
        self._render_analysis()

    def _update_cache_status(self) -> None:
        status = self.comp_repo.last_scrape_status()
        count = self.comp_repo.count_comps()
        self.sidebar_status.setText(f"TFT Academy\n{status['status']}\nComps: {count}")
        self.data_label.setText(f"Data updated: {status.get('finished_at', '') or 'unknown'}")
        self.patch_label.setText(f"Patch {self._current_patch_label()}")
        self.dashboard_page.update_data_status(status)
        self.settings_page.update_data_status(status, count)

    def _update_comp_pages(self) -> None:
        self.dashboard_page.update_comps(self.cached_comps)
        self.comps_page.update_comps(self.cached_comps)
        self.tier_page.update_comps(self.cached_comps)
        units = self._all_units()
        items = self._all_items()
        augments = self._all_augments()
        self.units_page.update_units(units)
        self.team_builder_page.update_units(units)
        self.items_page.update_items(items)
        self.augments_page.update_augments(augments)

    def _render_analysis(self, lightweight: bool = False) -> None:
        if not self.current_state:
            self.dashboard_page.update_state(None)
            self.dashboard_page.update_candidates([])
            self.comps_page.update_candidates([])
            return
        comps = self.cached_comps if self.settings_page else []
        candidates = self.analyzer.score_comps(self.current_state, comps) if comps else []
        self.current_candidates = candidates
        self.overlay.update_state(self.current_state, candidates)
        now = time.monotonic()
        if lightweight and now - self.last_panel_update < 1.0:
            self.dashboard_page.update_state(self.current_state)
            self.dashboard_page.update_candidates(candidates)
            return
        self.last_panel_update = now
        self.dashboard_page.update_state(self.current_state)
        self.dashboard_page.update_candidates(candidates)
        self.comps_page.update_candidates(candidates)

    def _select_comp_by_name(self, name: str) -> None:
        comp = next((item for item in self.cached_comps if item.name == name), None)
        if comp:
            self._select_comp(comp)

    def _select_comp(self, comp: NormalizedComp) -> None:
        self.comp_details_page.update_comp(comp)
        self.team_builder_page.update_comp(comp)
        self.navigate("Comp Details")

    def _toggle_overlay(self, enabled: bool) -> None:
        if enabled:
            self.overlay.update_state(self.current_state, self.current_candidates)
            self.overlay.show()
            self.overlay.raise_()
        else:
            self.overlay.hide()
        self.dashboard_page.set_overlay_checked(enabled)
        self.settings_page.set_overlay_checked(enabled)

    def export_json(self) -> None:
        if not self.current_state:
            QMessageBox.information(self, "No state", "Capture a screen before exporting.")
            return
        Path("exports").mkdir(exist_ok=True)
        suggested = Path("exports") / f"game_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", str(suggested), "JSON files (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.current_state.to_dict(), indent=2), encoding="utf-8")

    def export_comp_cache_json(self) -> None:
        Path("exports").mkdir(exist_ok=True)
        suggested = Path("exports") / f"comp_cache_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export Comp Cache JSON", str(suggested), "JSON files (*.json)")
        if path:
            self.comp_repo.export_json(Path(path))

    def save_debug_crops(self) -> None:
        if self.current_image_bgr is None:
            QMessageBox.information(self, "No screenshot", "Capture a screen before saving debug crops.")
            return
        debug_dir = Path("debug") / datetime.now().strftime("crops_%Y%m%d_%H%M%S")
        self.extractor.save_debug_crops(self.current_image_bgr, debug_dir)
        QMessageBox.information(self, "Debug crops saved", str(debug_dir))

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.timer.stop()
        self.overlay.close()
        super().closeEvent(event)

    @staticmethod
    def _carry_forward_ocr(previous: GameState, current: GameState) -> None:
        current.stage = previous.stage
        current.hp = previous.hp
        current.gold = previous.gold
        current.level = previous.level
        current.augments = previous.augments

    def _all_units(self) -> list[str]:
        values: list[str] = []
        for comp in self.cached_comps:
            values.extend(comp.core_units)
            values.extend(comp.optional_units)
        return sorted({value for value in values if value and not value.lower().startswith("lv")})

    def _all_items(self) -> list[str]:
        values: list[str] = []
        for comp in self.cached_comps:
            values.extend(comp.carry_items)
            values.extend(comp.tank_items)
        return sorted({value for value in values if value})

    def _all_augments(self) -> list[str]:
        values: list[str] = []
        for comp in self.cached_comps:
            values.extend(comp.augment_suggestions)
        return sorted({value for value in values if value})

    def _current_patch_label(self) -> str:
        counts: dict[str, int] = {}
        for comp in self.cached_comps:
            patch = comp.patch_label.strip()
            if patch:
                counts[patch] = counts.get(patch, 0) + 1
        if not counts:
            return "unknown"
        return max(counts.items(), key=lambda item: item[1])[0]
