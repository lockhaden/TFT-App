from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tft_analyzer.ui.components import CalibrationPreview, Card


class SettingsPage(QWidget):
    capture_requested = Signal()
    export_requested = Signal()
    export_comps_requested = Signal()
    save_debug_requested = Signal()
    refresh_requested = Signal()
    overlay_toggled = Signal(bool)
    click_through_toggled = Signal(bool)
    opacity_changed = Signal(int)
    calibration_changed = Signal(bool)
    calibration_target_changed = Signal(str)

    def __init__(self, config: dict) -> None:
        super().__init__()
        capture = config.get("capture", {})
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(12)
        root.addLayout(grid)

        general = Card("General")
        self.start_windows = QCheckBox("Start with Windows")
        self.minimize_tray = QCheckBox("Minimize to tray")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Darker", "High Contrast"])
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English"])
        form = QFormLayout()
        form.addRow(self.start_windows)
        form.addRow(self.minimize_tray)
        form.addRow("Theme", self.theme_combo)
        form.addRow("Language", self.language_combo)
        general.layout.addLayout(form)

        overlay = Card("Overlay")
        self.overlay_enabled = QCheckBox("Enable overlay")
        self.overlay_enabled.toggled.connect(self.overlay_toggled)
        self.click_through = QCheckBox("Click-through")
        self.click_through.toggled.connect(self.click_through_toggled)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(35, 100)
        self.opacity_slider.setValue(88)
        self.opacity_slider.valueChanged.connect(self.opacity_changed)
        overlay_form = QFormLayout()
        overlay_form.addRow(self.overlay_enabled)
        overlay_form.addRow(self.click_through)
        overlay_form.addRow("Opacity", self.opacity_slider)
        overlay_form.addRow("Hotkey", QLabel("CTRL + X"))
        overlay.layout.addLayout(overlay_form)

        data = Card("Data & Updates")
        self.data_status = QLabel("TFT Academy: unknown")
        self.data_status.setObjectName("Muted")
        self.comp_count = QLabel("Comps: 0")
        self.comp_count.setObjectName("Muted")
        refresh = QPushButton("Refresh Data")
        refresh.clicked.connect(self.refresh_requested)
        export_comps = QPushButton("Export Comp Cache JSON")
        export_comps.clicked.connect(self.export_comps_requested)
        data.layout.addWidget(self.data_status)
        data.layout.addWidget(self.comp_count)
        data.layout.addWidget(refresh)
        data.layout.addWidget(export_comps)

        capture_card = Card("Capture & Calibration")
        self.mode = QComboBox()
        self.mode.addItems(["window", "full_screen", "region"])
        self.mode.setCurrentText(capture.get("mode", "window"))
        self.window_title = QLineEdit(capture.get("window_title_contains", "League of Legends (TM) Client"))
        self.region_inputs = [QSpinBox() for _ in range(4)]
        for spin, value in zip(self.region_inputs, capture.get("region", [0, 0, 1920, 1080]), strict=False):
            spin.setRange(0, 10000)
            spin.setValue(int(value))
        region_row = QHBoxLayout()
        for label, spin in zip(("x", "y", "w", "h"), self.region_inputs, strict=False):
            region_row.addWidget(QLabel(label))
            region_row.addWidget(spin)
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(250, 10000)
        self.refresh_interval.setSingleStep(250)
        self.refresh_interval.setSuffix(" ms")
        self.refresh_interval.setValue(int(capture.get("auto_refresh_ms", 500)))
        self.ocr_every = QSpinBox()
        self.ocr_every.setRange(1, 20)
        self.ocr_every.setSuffix(" frames")
        self.ocr_every.setValue(int(capture.get("ocr_every_n_frames", 4)))
        self.live_fast_mode = QCheckBox("Live fast mode")
        self.live_fast_mode.setChecked(True)
        self.preview_live = QCheckBox("Preview during auto-refresh")
        self.preview_live.setChecked(False)
        self.calibration = QCheckBox("Calibration mode")
        self.calibration.toggled.connect(self.calibration_changed)
        self.calibration_target = QComboBox()
        self.calibration_target.addItems(["stage", "hp", "gold", "level", "board_slots", "bench_slots", "item_slots"])
        self.calibration_target.currentTextChanged.connect(self.calibration_target_changed)
        cap_form = QFormLayout()
        cap_form.addRow("Mode", self.mode)
        cap_form.addRow("Window title", self.window_title)
        cap_form.addRow("Region", region_row)
        cap_form.addRow("Refresh interval", self.refresh_interval)
        cap_form.addRow("OCR cadence", self.ocr_every)
        cap_form.addRow(self.live_fast_mode)
        cap_form.addRow(self.preview_live)
        cap_form.addRow(self.calibration)
        cap_form.addRow("Target", self.calibration_target)
        capture_card.layout.addLayout(cap_form)
        button_row = QHBoxLayout()
        capture_once = QPushButton("Capture Once")
        capture_once.setObjectName("PrimaryButton")
        capture_once.clicked.connect(self.capture_requested)
        export = QPushButton("Export JSON")
        export.clicked.connect(self.export_requested)
        debug = QPushButton("Save Debug Crops")
        debug.clicked.connect(self.save_debug_requested)
        button_row.addWidget(capture_once)
        button_row.addWidget(export)
        button_row.addWidget(debug)
        capture_card.layout.addLayout(button_row)

        about = Card("About")
        about.layout.addWidget(QLabel("TFT Compass"))
        about.layout.addWidget(QLabel("v0.1.0"))
        note = QLabel("Made for local screen-state summaries. No automation or live prescriptive coaching.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        about.layout.addWidget(note)

        grid.addWidget(general, 0, 0)
        grid.addWidget(overlay, 0, 1)
        grid.addWidget(data, 0, 2)
        grid.addWidget(capture_card, 1, 0, 1, 2)
        grid.addWidget(about, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        preview_card = Card("Calibration Preview")
        self.preview = CalibrationPreview()
        preview_card.layout.addWidget(self.preview)
        root.addWidget(preview_card, stretch=1)

    def capture_config(self) -> dict:
        return {
            "mode": self.mode.currentText(),
            "window_title_contains": self.window_title.text(),
            "region": [spin.value() for spin in self.region_inputs],
            "auto_refresh_ms": self.refresh_interval.value(),
            "ocr_every_n_frames": self.ocr_every.value(),
        }

    def update_data_status(self, status: dict, comp_count: int) -> None:
        self.data_status.setText(f"TFT Academy: {status.get('status', 'unknown')}\nLast update: {status.get('finished_at', '') or 'unknown'}")
        self.comp_count.setText(f"Comps: {comp_count}")

    def set_overlay_checked(self, checked: bool) -> None:
        self.overlay_enabled.blockSignals(True)
        self.overlay_enabled.setChecked(checked)
        self.overlay_enabled.blockSignals(False)
