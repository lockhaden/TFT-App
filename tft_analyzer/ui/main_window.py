from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import cv2
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from tft_analyzer.analysis.analyzer import NeutralAnalyzer
from tft_analyzer.capture.window_capture import capture_screen_region, capture_window
from tft_analyzer.config.config_manager import ConfigManager
from tft_analyzer.models.game_state import GameState
from tft_analyzer.sources.scrape_service import ScrapeService
from tft_analyzer.storage.comp_repository import CompRepository
from tft_analyzer.vision.state_extractor import StateExtractor

LOGGER = logging.getLogger(__name__)


class PreviewLabel(QLabel):
    region_drawn = Signal(QRect)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setStyleSheet("background:#111; color:#bbb;")
        self._start: tuple[int, int] | None = None
        self._current: QRect | None = None
        self.calibration_enabled = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.calibration_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._start = (event.position().toPoint().x(), event.position().toPoint().y())
            self._current = QRect(event.position().toPoint(), event.position().toPoint())
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.calibration_enabled and self._start:
            self._current = QRect(*self._start, event.position().toPoint().x() - self._start[0], event.position().toPoint().y() - self._start[1]).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.calibration_enabled and self._current and event.button() == Qt.MouseButton.LeftButton:
            self.region_drawn.emit(self._current.normalized())
            self._start = None
            self._current = None
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().paintEvent(event)
        if self._current:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.cyan, 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._current)


class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager) -> None:
        super().__init__()
        self.config_manager = config_manager
        self.extractor = StateExtractor(config_manager.data)
        self.analyzer = NeutralAnalyzer()
        self.comp_repo = CompRepository(Path("cache/tft_comps.sqlite3"))
        self.scrape_service = ScrapeService(self.comp_repo, Path("config/tft_academy_scraper.json"))
        self.current_image_bgr = None
        self.current_state: GameState | None = None
        self.current_pixmap: QPixmap | None = None

        self.setWindowTitle("TFT Screen State Analyzer")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture_once)

        self.preview = PreviewLabel()
        self.preview.region_drawn.connect(self._save_calibrated_region)
        self.state_text = QPlainTextEdit()
        self.state_text.setReadOnly(True)
        self.analysis_text = QPlainTextEdit()
        self.analysis_text.setReadOnly(True)
        self.candidates_text = QPlainTextEdit()
        self.candidates_text.setReadOnly(True)

        self._build_ui()
        self._refresh_cache_status()

    def _build_ui(self) -> None:
        capture_button = QPushButton("Capture Once")
        capture_button.clicked.connect(self.capture_once)
        self.auto_refresh = QCheckBox("Auto-refresh")
        self.auto_refresh.toggled.connect(self._toggle_auto_refresh)
        self.calibration = QCheckBox("Calibration Mode")
        self.calibration.toggled.connect(self._toggle_calibration)
        export_button = QPushButton("Export JSON")
        export_button.clicked.connect(self.export_json)
        crops_button = QPushButton("Save Debug Crops")
        crops_button.clicked.connect(self.save_debug_crops)
        refresh_academy_button = QPushButton("Refresh TFT Academy Data")
        refresh_academy_button.clicked.connect(self.refresh_tft_academy_data)
        export_comps_button = QPushButton("Export Comp Cache JSON")
        export_comps_button.clicked.connect(self.export_comp_cache_json)
        self.use_cached_comps = QCheckBox("Use cached comp data")
        self.use_cached_comps.setChecked(True)
        self.use_cached_comps.toggled.connect(self._render_analysis)
        self.scrape_status = QLabel("Last scrape: unknown")
        self.comp_count_label = QLabel("Cached comps: 0")

        self.mode = QComboBox()
        self.mode.addItems(["full_screen", "region", "window"])
        self.mode.setCurrentText(self.config_manager.data.get("capture", {}).get("mode", "full_screen"))
        self.window_title = QLineEdit(self.config_manager.data.get("capture", {}).get("window_title_contains", "Teamfight Tactics"))
        self.region_inputs = [QSpinBox() for _ in range(4)]
        for spin, value in zip(self.region_inputs, self.config_manager.data.get("capture", {}).get("region", [0, 0, 1920, 1080]), strict=False):
            spin.setRange(0, 10000)
            spin.setValue(int(value))

        self.calibration_target = QComboBox()
        self.calibration_target.addItems(["stage", "hp", "gold", "level"])

        controls = QGroupBox("Capture")
        form = QFormLayout(controls)
        form.addRow("Mode", self.mode)
        form.addRow("Window title contains", self.window_title)
        region_row = QHBoxLayout()
        for label, spin in zip(("x", "y", "w", "h"), self.region_inputs, strict=False):
            region_row.addWidget(QLabel(label))
            region_row.addWidget(spin)
        form.addRow("Region", region_row)
        form.addRow("Calibration target", self.calibration_target)

        button_row = QHBoxLayout()
        for widget in (capture_button, self.auto_refresh, self.calibration, export_button, crops_button):
            button_row.addWidget(widget)
        cache_row = QHBoxLayout()
        for widget in (refresh_academy_button, export_comps_button, self.use_cached_comps):
            cache_row.addWidget(widget)
        cache_status_row = QHBoxLayout()
        cache_status_row.addWidget(self.scrape_status)
        cache_status_row.addWidget(self.comp_count_label)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(controls)
        left_layout.addLayout(button_row)
        left_layout.addLayout(cache_row)
        left_layout.addLayout(cache_status_row)
        left_layout.addWidget(self.preview, stretch=1)

        right = QSplitter(Qt.Orientation.Vertical)
        state_group = QGroupBox("Parsed State")
        state_layout = QVBoxLayout(state_group)
        state_layout.addWidget(self.state_text)
        analysis_group = QGroupBox("Analyzer Output")
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.addWidget(self.analysis_text)
        candidates_group = QGroupBox("Top Candidate Comps")
        candidates_layout = QVBoxLayout(candidates_group)
        candidates_layout.addWidget(self.candidates_text)
        right.addWidget(state_group)
        right.addWidget(analysis_group)
        right.addWidget(candidates_group)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

    def capture_once(self) -> None:
        self._sync_capture_config()
        try:
            capture = self._capture()
        except Exception as exc:
            LOGGER.exception("Capture failed")
            QMessageBox.warning(self, "Capture failed", str(exc))
            return

        self.current_image_bgr = capture.image_bgr
        self._show_preview(capture.image_bgr)
        Path("debug").mkdir(exist_ok=True)
        cv2.imwrite(str(Path("debug") / "latest_capture.png"), capture.image_bgr)
        self.current_state = self.extractor.extract(capture.image_bgr, capture.source, debug_dir=None)
        self.state_text.setPlainText(json.dumps(self.current_state.to_dict(), indent=2))
        self._render_analysis()

    def _capture(self):
        capture_cfg = self.config_manager.data.setdefault("capture", {})
        mode = capture_cfg.get("mode", "full_screen")
        if mode == "window":
            return capture_window(capture_cfg.get("window_title_contains", "Teamfight Tactics"))
        if mode == "region":
            x, y, w, h = capture_cfg.get("region", [0, 0, 1920, 1080])
            return capture_screen_region([x, y, x + w, y + h])
        return capture_screen_region()

    def _show_preview(self, image_bgr) -> None:  # type: ignore[no-untyped-def]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.current_pixmap = QPixmap.fromImage(image)
        self.preview.setPixmap(self.current_pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        if self.current_pixmap:
            self.preview.setPixmap(self.current_pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _toggle_auto_refresh(self, enabled: bool) -> None:
        interval = int(self.config_manager.data.get("capture", {}).get("auto_refresh_ms", 2500))
        self.timer.start(interval) if enabled else self.timer.stop()

    def _toggle_calibration(self, enabled: bool) -> None:
        self.preview.calibration_enabled = enabled

    def _sync_capture_config(self) -> None:
        capture_cfg = self.config_manager.data.setdefault("capture", {})
        capture_cfg["mode"] = self.mode.currentText()
        capture_cfg["window_title_contains"] = self.window_title.text()
        capture_cfg["region"] = [spin.value() for spin in self.region_inputs]
        self.config_manager.save()

    def _save_calibrated_region(self, rect: QRect) -> None:
        if self.current_image_bgr is None or self.current_pixmap is None:
            return
        label_size = self.preview.size()
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
        self.config_manager.data["base_resolution"] = [self.current_image_bgr.shape[1], self.current_image_bgr.shape[0]]
        self.config_manager.set_region(self.calibration_target.currentText(), bbox)
        self.extractor = StateExtractor(self.config_manager.data)
        QMessageBox.information(self, "Calibration saved", f"Saved {self.calibration_target.currentText()} region: {bbox}")

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

    def refresh_tft_academy_data(self) -> None:
        try:
            result = self.scrape_service.refresh_tft_academy()
        except Exception as exc:
            LOGGER.exception("TFT Academy refresh failed")
            QMessageBox.warning(self, "Scrape failed", str(exc))
            self.comp_repo.record_scrape_run("tft_academy", "failed", str(exc), 0, datetime.now().isoformat())
        self._refresh_cache_status()
        self._render_analysis()

    def save_debug_crops(self) -> None:
        if self.current_image_bgr is None:
            QMessageBox.information(self, "No screenshot", "Capture a screen before saving debug crops.")
            return
        debug_dir = Path("debug") / datetime.now().strftime("crops_%Y%m%d_%H%M%S")
        self.extractor.save_debug_crops(self.current_image_bgr, debug_dir)
        QMessageBox.information(self, "Debug crops saved", str(debug_dir))

    def _cached_comps_for_analysis(self):
        if not self.use_cached_comps.isChecked():
            return []
        return self.comp_repo.list_comps()

    def _render_analysis(self) -> None:
        if not self.current_state:
            self.analysis_text.setPlainText("")
            self.candidates_text.setPlainText("")
            return
        comps = self._cached_comps_for_analysis()
        self.analysis_text.setPlainText("\n".join(self.analyzer.analyze(self.current_state, comps)))
        candidates = self.analyzer.score_comps(self.current_state, comps) if comps else []
        self.candidates_text.setPlainText(self._format_candidates(candidates))

    def _refresh_cache_status(self) -> None:
        status = self.comp_repo.last_scrape_status()
        self.scrape_status.setText(f"Last scrape: {status['status']} {status['finished_at']}")
        self.comp_count_label.setText(f"Cached comps: {self.comp_repo.count_comps()}")

    @staticmethod
    def _format_candidates(candidates) -> str:  # type: ignore[no-untyped-def]
        if not candidates:
            return "No cached candidate comps available."
        lines: list[str] = []
        for index, candidate in enumerate(candidates, start=1):
            lines.append(f"{index}. {candidate.name}")
            lines.append(f"   Source: {candidate.source}")
            lines.append(f"   Score: {candidate.score:.1f} | Confidence: {candidate.confidence:.2f}")
            lines.append("   Fit reasons: " + ("; ".join(candidate.fit_reasons) if candidate.fit_reasons else "none detected"))
            lines.append("   Missing pieces: " + ("; ".join(candidate.missing_pieces) if candidate.missing_pieces else "none"))
            lines.append(f"   URL: {candidate.source_url}")
        return "\n".join(lines)
